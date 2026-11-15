from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.security import current_user, require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import ErrorResponse
from app.schemas.care import LinkPage, LinkRequest, LinkResponse, ProfileResponse, ProfileUpdate
from app.services import care as service

router = APIRouter(tags=["care"], responses={
    code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422)
})
Database = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[User, Depends(current_user)]
PatientUser = Annotated[User, Depends(require_role(Role.PATIENT))]
ProfessionalUser = Annotated[User, Depends(require_role(Role.PROFESSIONAL))]


@router.get("/me", response_model=ProfileResponse)
def me(response: Response, user: Authenticated, db: Database):
    response.headers["Cache-Control"] = "no-store"
    return service.read_profile(db, user)


@router.patch("/me", response_model=ProfileResponse)
def update_me(data: ProfileUpdate, response: Response, user: Authenticated, db: Database):
    response.headers["Cache-Control"] = "no-store"
    return service.update_profile(db, user, data.full_name)


@router.get("/me/professional-links", response_model=LinkPage)
def links(response: Response, user: Authenticated, db: Database,
          cursor: UUID | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    response.headers["Cache-Control"] = "no-store"
    return service.list_links(db, user, str(cursor) if cursor else None, limit)


@router.post("/me/professional-links", response_model=LinkResponse, status_code=201)
def request_link(data: LinkRequest, response: Response, user: PatientUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    return service.request_link(db, user, str(data.professional_id))


@router.post("/me/professional-links/{link_id}/accept", response_model=LinkResponse)
def accept_link(link_id: UUID, response: Response, user: ProfessionalUser, db: Database):
    response.headers["Cache-Control"] = "no-store"
    return service.transition_link(db, user, str(link_id), accept=True)


@router.post("/me/professional-links/{link_id}/revoke", status_code=204)
def revoke_link(link_id: UUID, user: Authenticated, db: Database):
    service.transition_link(db, user, str(link_id), accept=False)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/patients/{patient_id}", response_model=ProfileResponse)
def patient(patient_id: UUID, response: Response, user: Authenticated, db: Database):
    response.headers["Cache-Control"] = "no-store"
    return service.read_patient(db, user, str(patient_id))
