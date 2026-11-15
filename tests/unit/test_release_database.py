from unittest.mock import MagicMock, patch

import pytest

from scripts import migrate_production, start_api


@pytest.mark.parametrize('changes', [
    {'APP_ENV': 'development'}, {'CI': 'true'},
    {'DATABASE_URL': 'sqlite:///production.db'},
    {'DATABASE_URL': 'mysql+pymysql://user:password@public.example.test:3306/ctrlx'},
    {'DATABASE_URL': 'mysql+pymysql://user:password@mysql.railway.internal:3307/ctrlx'},
    {'DATABASE_URL': 'mysql+pymysql://user@mysql.railway.internal:3306/ctrlx'},
])
def test_release_refuses_wrong_environment_or_database(monkeypatch, changes):
    for key, value in {'APP_ENV': 'production', 'CI': 'false',
                       'DATABASE_URL': 'mysql+pymysql://user:password@mysql.railway.internal:3306/ctrlx',
                       **changes}.items():
        monkeypatch.setenv(key, value)
    with patch('scripts.migrate_production.create_engine') as connect:
        with pytest.raises((ValueError, RuntimeError)):
            migrate_production.production_engine()
        connect.assert_not_called()


def test_pending_migrations_prevent_activation():
    with (
        patch('scripts.migrate_production.ScriptDirectory') as scripts,
        patch('scripts.migrate_production.MigrationContext') as context,
    ):
        scripts.from_config.return_value.get_heads.return_value = ['new']
        context.configure.return_value.get_current_heads.return_value = ('old',)
        with pytest.raises(RuntimeError, match='pending'):
            migrate_production.verify_revision(MagicMock(), MagicMock())


def test_migration_failure_releases_lock_and_hides_connection_details(capsys):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = ['8.4.13', 1]
    with (
        patch('scripts.migrate_production.production_engine', return_value=engine),
        patch('scripts.migrate_production.ScriptDirectory') as scripts,
        patch('scripts.migrate_production.command.upgrade', side_effect=RuntimeError('secret-url')),
    ):
        scripts.from_config.return_value.get_heads.return_value = ['head']
        assert migrate_production.main() == 1
    assert 'secret-url' not in capsys.readouterr().err
    assert 'RELEASE_LOCK' in str(connection.execute.call_args.args[0])
    engine.dispose.assert_called_once()


def test_migration_lock_failure_never_runs_upgrade():
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.scalar.side_effect = ['8.4.13', 0]
    with (
        patch('scripts.migrate_production.production_engine', return_value=engine),
        patch('scripts.migrate_production.command.upgrade') as upgrade,
        pytest.raises(RuntimeError, match='lock'),
    ):
        migrate_production.migrate()
    upgrade.assert_not_called()


def test_api_replaces_itself_without_running_migrations(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('PORT', '8080')
    with patch('scripts.start_api.os.execvp') as execute, patch('scripts.start_api.check_schema') as db:
        assert start_api.main() == 0
        db.assert_not_called()
    args = execute.call_args.args[1]
    assert args[-3:] == ['--port', '8080', '--no-access-log']
    assert '--reload' not in args


def test_production_api_does_not_start_when_schema_is_not_ready(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    with (
        patch('app.core.config.get_settings') as settings,
        patch('scripts.start_api.check_schema', side_effect=RuntimeError('pending')),
        patch('scripts.start_api.os.execvp') as execute,
    ):
        settings.return_value.origins = ['https://frontend.example.test']
        assert start_api.main() == 1
        execute.assert_not_called()


@pytest.mark.parametrize('environment', ['Production', 'development'])
def test_railway_cannot_skip_production_startup_guards(monkeypatch, environment):
    monkeypatch.setenv('APP_ENV', environment)
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID', 'synthetic-environment')
    with patch('scripts.start_api.os.execvp') as execute:
        assert start_api.main() == 1
        execute.assert_not_called()
