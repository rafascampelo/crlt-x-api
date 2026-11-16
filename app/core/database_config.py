"""Shared database configuration for the API and migration entry points."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None
    mysqlhost: str | None = None
    mysqlport: int | None = None
    mysqluser: str | None = None
    mysqlpassword: SecretStr | None = None
    mysqldatabase: str | None = None
    mysql_url: SecretStr | None = None

    @model_validator(mode="after")
    def resolve_database_url(self):
        legacy = (self.db_user, self.db_password, self.db_host, self.db_port, self.db_name)
        native = (self.mysqluser, self.mysqlpassword, self.mysqlhost,
                  self.mysqlport, self.mysqldatabase)
        if not any(value is not None for value in legacy):
            if self.database_url is None and any(value is not None for value in native):
                if any(value is None or value == "" for value in native):
                    raise ValueError("All MYSQLUSER, MYSQLPASSWORD, MYSQLHOST, MYSQLPORT "
                                     "and MYSQLDATABASE are required")
                self.db_user, self.db_password, self.db_host, self.db_port, self.db_name = native
            elif self.database_url is None:
                self.database_url = self.mysql_url
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
            raise ValueError("Configure DATABASE_URL, all MYSQL* variables, MYSQL_URL or DB_*")
        try:
            url = make_url(self.database_url.get_secret_value())
            if url.drivername == "mysql":
                self.database_url = SecretStr(
                    url.set(drivername="mysql+pymysql").render_as_string(hide_password=False)
                )
        except (ArgumentError, ValueError, TypeError):
            raise ValueError("Invalid database URL") from None
        return self
