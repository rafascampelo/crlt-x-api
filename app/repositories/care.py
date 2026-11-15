from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.professional_link import CareAuditEvent, LinkStatus, ProfessionalLink
from app.models.user import Patient, Professional, Role, User


def profile(db: Session, user: User):
    model = Patient if user.role == Role.PATIENT else Professional
    return db.scalar(select(model).where(model.user_id == user.id).with_for_update())


def audit(db: Session, actor: User, action: str, resource_id: str,
          patient_id: str | None = None):
    db.add(CareAuditEvent(actor_id=actor.id, action=action, resource_id=resource_id,
                         patient_id=patient_id))


def active_link(db: Session, patient_id: str, professional_id: str):
    return db.scalar(select(ProfessionalLink).where(
        ProfessionalLink.patient_id == patient_id,
        ProfessionalLink.professional_id == professional_id,
        ProfessionalLink.status == LinkStatus.ACTIVE,
    ).with_for_update())


def link_scope(identity_id: str, role: Role):
    return (ProfessionalLink.patient_id == identity_id if role == Role.PATIENT
            else ProfessionalLink.professional_id == identity_id)


def list_links(db: Session, identity_id: str, role: Role, cursor: str | None, limit: int):
    query = select(ProfessionalLink).where(link_scope(identity_id, role))
    if cursor:
        query = query.where(ProfessionalLink.id > cursor)
    return list(db.scalars(query.order_by(ProfessionalLink.id).limit(limit + 1)))


def lock_patient(db: Session, patient_id: str):
    return db.scalar(select(Patient).where(Patient.id == patient_id).with_for_update())


def professional(db: Session, professional_id: str):
    return db.get(Professional, professional_id)


def patient(db: Session, patient_id: str):
    return db.get(Patient, patient_id)


def open_link(db: Session, patient_id: str, professional_id: str):
    return db.scalar(select(ProfessionalLink).where(
        ProfessionalLink.patient_id == patient_id,
        ProfessionalLink.professional_id == professional_id,
        ProfessionalLink.status.in_([LinkStatus.PENDING, LinkStatus.ACTIVE]),
    ).with_for_update())


def participant_link(db: Session, link_id: str, identity_id: str, role: Role):
    return db.scalar(select(ProfessionalLink).where(
        ProfessionalLink.id == link_id, link_scope(identity_id, role),
    ))


def lock_link(db: Session, link: ProfessionalLink):
    db.refresh(link, with_for_update=True)


def patient_active_link(db: Session, patient_id: str):
    return db.scalar(select(ProfessionalLink).where(
        ProfessionalLink.patient_id == patient_id,
        ProfessionalLink.status == LinkStatus.ACTIVE,
    ).with_for_update())


def pending_links(db: Session, patient_id: str, exclude_id: str):
    return list(db.scalars(select(ProfessionalLink).where(
        ProfessionalLink.patient_id == patient_id,
        ProfessionalLink.status == LinkStatus.PENDING,
        ProfessionalLink.id != exclude_id,
    ).order_by(ProfessionalLink.id).with_for_update()))


def linked_patients(db: Session, professional_id: str, cursor: str | None, limit: int):
    query = select(Patient).join(
        ProfessionalLink, ProfessionalLink.patient_id == Patient.id,
    ).where(
        ProfessionalLink.professional_id == professional_id,
        ProfessionalLink.status == LinkStatus.ACTIVE,
    )
    if cursor:
        query = query.where(Patient.id > cursor)
    return list(db.scalars(query.order_by(Patient.id).limit(limit + 1)))
