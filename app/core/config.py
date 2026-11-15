from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database_config import DatabaseSettings


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: str = "http://localhost:3000"

    @property
    def origins(self) -> list[str]:
        values = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if not values or "*" in values:
            raise ValueError("CORS_ORIGINS must contain explicit origins")
        for value in values:
            origin = urlsplit(value)
            if (origin.scheme not in {"http", "https"} or not origin.hostname
                    or origin.username or origin.password or origin.path
                    or origin.query or origin.fragment or "*" in value):
                raise ValueError("CORS_ORIGINS must contain HTTP(S) origins without paths")
            # Accessing port rejects invalid/out-of-range ports during startup.
            _ = origin.port
        return values


class Settings(DatabaseSettings, CorsSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    secret_key: SecretStr
    jwt_issuer: str = "ctrl-x-api"
    jwt_audience: str = "ctrl-x-web"
    app_env: str = "development"

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or "REPLACE" in secret or "CHANGE" in secret:
            raise ValueError("SECRET_KEY must be a unique random secret of at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
