import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 -- registers ORM models in shared metadata
from alembic import context
from app.db.base import Base
from scripts.ci_database import validate_ci_database


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    database_url: SecretStr


url = MigrationSettings().database_url.get_secret_value()
if os.environ.get("CI") == "true":
    validate_ci_database(url)

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
