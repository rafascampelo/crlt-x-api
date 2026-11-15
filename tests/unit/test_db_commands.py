import json
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.config import Config
from sqlalchemy import create_engine

from scripts import db, deploy_migrations, migration_sentinel


@pytest.mark.parametrize("command", ["db:rollback", "db:create"])
def test_production_disallows_rollback_and_generation(monkeypatch, command):
    monkeypatch.setenv("APP_ENV", "production")
    args = [command] + (["--message", "synthetic"] if command == "db:create" else [])
    with patch("scripts.db.command.downgrade") as downgrade:
        assert db.main(args) == 1
        downgrade.assert_not_called()


def test_railway_cannot_bypass_guard_by_changing_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "synthetic")
    assert db.main(["db:rollback", "--allow-local-rollback"]) == 1


def test_production_uses_locked_migration_path(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "production")
    with patch("scripts.db.migrate", side_effect=RuntimeError("synthetic-secret")):
        assert db.main(["db:migrate"]) == 1
    assert "synthetic-secret" not in capsys.readouterr().err


def test_local_rollback_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_ID", raising=False)
    with patch("scripts.db.local_engine") as engine:
        assert db.main(["db:rollback"]) == 1
        engine.assert_not_called()


def test_status_detects_pending_schema_without_modifying_database(capsys):
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        db.status(connection, Config("alembic.ini"))
        assert "current=base; head=" in capsys.readouterr().out
        with pytest.raises(RuntimeError, match="pending"):
            db.status(connection, Config("alembic.ini"), require_current=True)
    engine.dispose()


@pytest.mark.parametrize("event,ref", [
    ("pull_request", "refs/heads/prod"), ("push", "refs/heads/develop"),
])
def test_migration_release_rejects_prs_and_develop(monkeypatch, event, ref):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    with patch("scripts.deploy_migrations.railway") as cli:
        with pytest.raises(RuntimeError, match="restricted"):
            deploy_migrations.main()
        cli.assert_not_called()


def test_migration_package_is_private_and_does_not_change_api_config(tmp_path):
    source = Path.cwd()
    original = (source / "railway.json").read_bytes()
    deploy_migrations.prepare_release(source, tmp_path)
    config = json.loads((tmp_path / "railway.json").read_text())
    assert config["deploy"]["preDeployCommand"] == ["python -m scripts.db db:migrate"]
    assert config["deploy"]["startCommand"] == "python -m scripts.migration_sentinel"
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".git").exists()
    assert (source / "railway.json").read_bytes() == original


def test_failed_remote_migrations_propagate_and_restore_working_directory(monkeypatch):
    source = Path.cwd()
    for key, value in {
        "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/prod",
        "RAILWAY_TOKEN": "synthetic", "RAILWAY_PROJECT_ID": "11111111-1111-1111-1111-111111111111",
        "RAILWAY_ENVIRONMENT_ID": "22222222-2222-2222-2222-222222222222",
        "RAILWAY_MIGRATIONS_SERVICE_ID": "33333333-3333-3333-3333-333333333333",
        "RAILWAY_SERVICE_ID": "44444444-4444-4444-4444-444444444444",
    }.items():
        monkeypatch.setenv(key, value)
    with (
        patch("scripts.deploy_migrations.verify_api_target"),
        patch("scripts.deploy_migrations.railway", return_value=json.dumps({
            "deploymentId": "55555555-5555-5555-5555-555555555555",
        })),
        patch("scripts.deploy_migrations.wait_for_deployment", side_effect=RuntimeError("failed")),
        pytest.raises(RuntimeError, match="failed"),
    ):
        deploy_migrations.main()
    assert Path.cwd() == source


def test_workflow_blocks_api_until_migrations_succeed():
    # YAML is optional locally; CI additionally validates with actionlint.
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load(Path(".github/workflows/deploy-production.yml").read_text())
    jobs = workflow["jobs"]
    assert jobs["database-migrations"]["needs"] == "validate"
    assert jobs["production"]["needs"] == "database-migrations"
    assert "if" not in jobs["production"]  # default success() prevents deploy on failed migration
    assert workflow["concurrency"]["cancel-in-progress"] is False


def test_api_predeploy_only_checks_schema():
    config = json.loads(Path("railway.json").read_text())
    assert config["deploy"]["preDeployCommand"] == [
        "python -m scripts.db db:status --require-current",
    ]


def test_sentinel_does_not_accept_pending_schema_or_expose_errors(capsys):
    with (
        patch("scripts.migration_sentinel.check_schema", side_effect=RuntimeError("synthetic-secret")),
        patch("scripts.migration_sentinel.HTTPServer") as server,
    ):
        assert migration_sentinel.main() == 1
        server.assert_not_called()
    assert "synthetic-secret" not in capsys.readouterr().err
