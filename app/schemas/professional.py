import re

from pydantic import BaseModel, Field, field_validator, model_validator


class CrefitoFields(BaseModel):
    crefito_region: int | None = Field(default=None, strict=True, ge=1, le=22)
    crefito_number: str | None = Field(default=None, max_length=20)

    @field_validator("crefito_number")
    @classmethod
    def normalize_registration(cls, value: str | None) -> str | None:
        if value is None:
            return None
        match = re.fullmatch(r"([0-9]{1,7})(?:-F)?", value.strip().upper())
        if not match or int(match[1]) == 0:
            raise ValueError("Invalid physiotherapist registration format")
        return f"{int(match[1])}-F"

    @model_validator(mode="after")
    def require_registration_pair(self):
        if (self.crefito_region is None) != (self.crefito_number is None):
            raise ValueError("CREFITO region and number must be supplied together")
        return self
