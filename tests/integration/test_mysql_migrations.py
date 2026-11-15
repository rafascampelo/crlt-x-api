import os

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from scripts.ci_database import validate_ci_database


def test_mysql_is_isolated_and_at_migration_head():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail("TEST_DATABASE_URL is mandatory in CI")
        pytest.skip("requires the disposable MySQL service; see CI-CD.md")
    validate_ci_database(url)
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "ctrlx_ci"
            assert connection.scalar(text("SELECT VERSION()")).startswith("8.4.")
            heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
            assert len(heads) == 1
            assert MigrationContext.configure(connection).get_current_heads() == tuple(heads)
    finally:
        engine.dispose()
