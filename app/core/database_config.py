"""Shared database configuration for the API and migration entry points."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None

    @model_validator(mode="after")
    def resolve_database_url(self):
        parts = (self.db_user, self.db_password, self.db_host, self.db_port, self.db_name)
        if any(value is not None for value in parts):
            if any(value is None or value == "" for value in parts):
                raise ValueError("All DB_USER, DB_PASSWORD, DB_HOST, DB_PORT and DB_NAME are required")
            if not self.db_password.get_secret_value() or not 1 <= self.db_port <= 65535:
                raise ValueError("DB_PASSWORD must be nonempty and DB_PORT must be valid")
            url = URL.create(
                drivername="mysql+pymysql", username=self.db_user,
                password=self.db_password.get_secret_value(), host=self.db_host,
                port=self.db_port, database=self.db_name,
            )
            self.database_url = SecretStr(url.render_as_string(hide_password=False))
        elif self.database_url is None or not self.database_url.get_secret_value():
            raise ValueError("Configure DATABASE_URL or all five DB_* variables")
        return self
