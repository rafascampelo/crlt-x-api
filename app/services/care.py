from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.professional_link import LinkStatus, ProfessionalLink
from app.models.user import Role, User
from app.repositories import care
from app.schemas.care import ProfileResponse


def own_profile(db: Session, user: User):
    result = care.profile(db, user)
    if result is None:
        raise HTTPException(404, "Profile not found")
    return result


def profile_response(profile, role: Role):
    return ProfileResponse(id=profile.id, user_id=profile.user_id,
                           full_name=profile.full_name, role=role)


def read_profile(db: Session, user: User):
    profile = own_profile(db, user)
    care.audit(db, user, "profile_viewed", profile.id,
               profile.id if user.role == Role.PATIENT else None)
    db.commit()
    return profile_response(profile, user.role)


def update_profile(db: Session, user: User, full_name: str):
    profile = own_profile(db, user)
    profile.full_name = full_name
    care.audit(db, user, "profile_updated", profile.id,
               profile.id if user.role == Role.PATIENT else None)
    db.commit()
    return profile_response(profile, user.role)


def list_links(db: Session, user: User, cursor: str | None, limit: int):
    identity = own_profile(db, user)
    items = care.list_links(db, identity.id, user.role, cursor, limit)
    next_cursor = items[limit - 1].id if len(items) > limit else None
    care.audit(db, user, "links_viewed", identity.id,
               identity.id if user.role == Role.PATIENT else None)
    db.commit()
    return {"items": items[:limit], "next_cursor": next_cursor}


def read_patient(db: Session, user: User, patient_id: str):
    profile = authorize_patient(db, user, patient_id)
    care.audit(db, user, "patient_viewed", profile.id, profile.id)
    db.commit()
    return profile_response(profile, Role.PATIENT)


def authorize_patient(db: Session, user: User, patient_id: str):
    identity = own_profile(db, user)
    if user.role == Role.PATIENT:
        allowed = identity.id == patient_id
    else:
        allowed = care.active_link(db, patient_id, identity.id) is not None
    if not allowed:
        raise HTTPException(404, "Patient not found")
    patient = care.patient(db, patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return patient


def request_link(db: Session, user: User, professional_id: str):
    patient = own_profile(db, user)
    # Serialize requests and transitions for the same patient.
    care.lock_patient(db, patient.id)
    if care.professional(db, professional_id) is None:
        raise HTTPException(404, "Professional not found")
    existing = care.open_link(db, patient.id, professional_id)
    if existing:
        raise HTTPException(409, "Link already pending or active")
    link = ProfessionalLink(patient_id=patient.id, professional_id=professional_id)
    db.add(link)
    db.flush()
    care.audit(db, user, "link_requested", link.id, patient.id)
    db.commit()
    return link


def transition_link(db: Session, user: User, link_id: str, accept: bool):
    identity = own_profile(db, user)
    link = care.participant_link(db, link_id, identity.id, user.role)
    if link is None:
        raise HTTPException(404, "Link not found")
    care.lock_patient(db, link.patient_id)
    care.lock_link(db, link)
    if accept:
        if link.status != LinkStatus.PENDING:
            raise HTTPException(409, "Link is not pending")
        active = care.patient_active_link(db, link.patient_id)
        if active:
            raise HTTPException(409, "Patient already has an active professional")
        link.status = LinkStatus.ACTIVE
        link.accepted_at = datetime.now(UTC)
        action = "link_accepted"
    else:
        if link.status == LinkStatus.REVOKED:
            return
        link.status = LinkStatus.REVOKED
        link.revoked_at = datetime.now(UTC)
        action = "link_revoked"
    care.audit(db, user, action, link.id, link.patient_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Patient already has an active professional") from None
    return link
