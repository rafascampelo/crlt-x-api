from unittest.mock import patch

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database_config import DatabaseSettings
from scripts.migrate_production import production_engine


@pytest.fixture
def database_environment(monkeypatch):
    for key in ("DATABASE_URL", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME",
                "MYSQLHOST", "MYSQLPORT", "MYSQLUSER", "MYSQLPASSWORD", "MYSQLDATABASE",
                "MYSQL_URL"):
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


def test_native_railway_parts_preserve_password(database_environment, monkeypatch):
    for key, value in {"MYSQLHOST": "mysql.railway.internal", "MYSQLPORT": "3306",
                       "MYSQLUSER": "test", "MYSQLPASSWORD": "fake@:/%#pass",
                       "MYSQLDATABASE": "test"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MYSQL_URL", "mysql://ignored:ignored@ignored:3306/ignored")
    url = make_url(DatabaseSettings().database_url.get_secret_value())
    assert url.password == "fake@:/%#pass"
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql.railway.internal"


def test_native_partial_fails(database_environment, monkeypatch):
    monkeypatch.setenv("MYSQLHOST", "mysql.railway.internal")
    with pytest.raises(ValueError, match="All MYSQLUSER"):
        DatabaseSettings()


@pytest.mark.parametrize("key", ["DATABASE_URL", "MYSQL_URL"])
def test_mysql_url_uses_pymysql(database_environment, monkeypatch, key):
    monkeypatch.setenv(key, "mysql://test:p%40ss@mysql.railway.internal:3306/test")
    url = make_url(DatabaseSettings().database_url.get_secret_value())
    assert url.drivername == "mysql+pymysql"
    assert url.password == "p@ss"


def test_explicit_url_precedes_native_parts(database_environment, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://test:pass@chosen.railway.internal:3306/test")
    monkeypatch.setenv("MYSQLHOST", "ignored.railway.internal")
    assert make_url(DatabaseSettings().database_url.get_secret_value()).host == (
        "chosen.railway.internal"
    )
