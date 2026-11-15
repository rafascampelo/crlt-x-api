import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.user import Role
from app.schemas.professional import CrefitoFields


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", value):
            raise ValueError("Invalid email")
        return value


class Registration(Credentials, CrefitoFields):
    role: Role
    full_name: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_role_registration(self):
        if self.role == Role.PROFESSIONAL and self.crefito_number is None:
            raise ValueError("CREFITO is required for professionals")
        if self.role == Role.PATIENT and (
            {"crefito_region", "crefito_number"} & self.model_fields_set
        ):
            raise ValueError("CREFITO is only allowed for professionals")
        return self

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role: Role


class ErrorResponse(BaseModel):
    detail: str
