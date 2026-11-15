from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr
    secret_key: SecretStr
    jwt_issuer: str = "ctrl-x-api"
    jwt_audience: str = "ctrl-x-web"
    cors_origins: str = "http://localhost:3000"
    app_env: str = "development"

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or "REPLACE" in secret or "CHANGE" in secret:
            raise ValueError("SECRET_KEY must be a unique random secret of at least 32 characters")
        return value

    @property
    def origins(self) -> list[str]:
        values = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if not values or "*" in values:
            raise ValueError("CORS_ORIGINS must contain explicit origins")
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
