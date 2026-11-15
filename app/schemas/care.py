from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.professional_link import LinkStatus
from app.models.user import Role
from app.repositories.auth import utc


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    professional_id: UUID


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    professional_id: UUID
    status: LinkStatus
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None

    @field_serializer("created_at", "accepted_at", "revoked_at")
    def serialize_time(self, value: datetime | None):
        return utc(value) if value is not None else None


class LinkPage(BaseModel):
    items: list[LinkResponse]
    next_cursor: UUID | None


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    role: Role
    full_name: str


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=1, max_length=200)
