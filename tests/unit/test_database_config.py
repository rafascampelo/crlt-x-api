from unittest.mock import patch

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database_config import DatabaseSettings
from scripts.migrate_production import production_engine


@pytest.fixture
def database_environment(monkeypatch):
    for key in ("DATABASE_URL", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"):
        monkeypatch.delenv(key, raising=False)


def set_parts(monkeypatch):
    for key, value in {
        "DB_USER": "synthetic-user", "DB_PASSWORD": "fake@:/%#password",
        "DB_HOST": "mysql.railway.internal", "DB_PORT": "3306", "DB_NAME": "ctrlx_test",
    }.items():
        monkeypatch.setenv(key, value)


def test_parts_preserve_password_and_override_legacy_url(database_environment, monkeypatch):
    set_parts(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///old.db")
    settings = Settings(_env_file=None, secret_key="synthetic-test-secret-at-least-32-chars")
    url = make_url(settings.database_url.get_secret_value())
    assert url.password == "fake@:/%#password"
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql.railway.internal"
    assert "fake@:/%#password" not in repr(settings)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CI", raising=False)
    with patch("scripts.migrate_production.create_engine") as connect:
        production_engine()
    assert connect.call_args.args[0] == url


@pytest.mark.parametrize("port", ["invalid", "0", "65536"])
def test_invalid_ports_fail_without_password_disclosure(database_environment, monkeypatch, port):
    set_parts(monkeypatch)
    monkeypatch.setenv("DB_PORT", port)
    with pytest.raises(ValueError) as error:
        DatabaseSettings()
    assert "fake@:/%#password" not in str(error.value)


def test_partial_parts_do_not_fall_back_to_legacy_url(database_environment, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///old.db")
    monkeypatch.setenv("DB_USER", "synthetic-user")
    with pytest.raises(ValueError, match="All DB_USER"):
        DatabaseSettings()


def test_legacy_url_remains_supported(database_environment, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    assert DatabaseSettings().database_url.get_secret_value() == "sqlite:///test.db"
