import os

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 -- registers ORM models in shared metadata
from alembic import context
from app.core.database_config import DatabaseSettings
from app.db.base import Base
from scripts.ci_database import validate_ci_database

url = DatabaseSettings().database_url.get_secret_value()
if os.environ.get("CI") == "true":
    validate_ci_database(url)

def run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    run_migrations(context.config.attributes["connection"])
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()
