import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from scripts.deploy_railway import (
    check_health,
    deployment_id_from_upload,
    main,
    railway,
    validate_base_url,
    validate_release_config,
    verify_api_target,
    wait_for_deployment,
)

DEPLOYMENT = "12345678-1234-1234-1234-123456789abc"


def test_extracts_exact_uploaded_deployment():
    output = json.dumps({"deploymentId": DEPLOYMENT, "logsUrl": "https://railway.com/logs"})
    assert deployment_id_from_upload(output) == DEPLOYMENT


def test_missing_deployment_id_fails_closed():
    with pytest.raises(RuntimeError):
        deployment_id_from_upload('{"logsUrl":"https://railway.com/logs"}')


@pytest.mark.parametrize("status", ["FAILED", "CRASHED", "REMOVED", "CANCELED", "UNKNOWN"])
def test_unsuccessful_publication_fails(status):
    with patch(
        "scripts.deploy_railway.railway",
        return_value=json.dumps([{"id": DEPLOYMENT, "status": status}]),
    ), pytest.raises(RuntimeError, match="Publication failed"):
        wait_for_deployment(DEPLOYMENT, "service", "environment")


def test_does_not_accept_previous_successful_deployment():
    with (
        patch("scripts.deploy_railway.railway", return_value='[{"id":"old","status":"SUCCESS"}]'),
        patch("scripts.deploy_railway.time.monotonic", side_effect=[0, 1, 901]),
        patch("scripts.deploy_railway.time.sleep"),
        pytest.raises(TimeoutError),
    ):
        wait_for_deployment(DEPLOYMENT, "service", "environment")


def test_waits_until_uploaded_deployment_succeeds():
    responses = [
        json.dumps([{"id": DEPLOYMENT, "status": status}])
        for status in ("BUILDING", "DEPLOYING", "SUCCESS")
    ]
    with (
        patch("scripts.deploy_railway.railway", side_effect=responses) as cli,
        patch("scripts.deploy_railway.time.sleep"),
    ):
        wait_for_deployment(DEPLOYMENT, "service", "environment")
        assert cli.call_count == 3


def test_cli_nonzero_is_a_publication_failure():
    with (
        patch("scripts.deploy_railway.subprocess.run", return_value=CompletedProcess([], 1)),
        pytest.raises(RuntimeError, match="exit 1"),
    ):
        railway("up", "--detach")


def test_failing_public_health_is_not_accepted():
    with (
        patch("scripts.deploy_railway.urlopen", side_effect=TimeoutError),
        patch("scripts.deploy_railway.time.sleep"),
        pytest.raises(RuntimeError, match="/health failed"),
    ):
        check_health("https://api.example.test")


@pytest.mark.parametrize(
    ("event", "ref"),
    [("pull_request", "refs/heads/prod"), ("push", "refs/heads/develop")],
)
def test_nonproduction_events_cannot_publish(monkeypatch, event, ref):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    with patch("scripts.deploy_railway.railway") as cli:
        with pytest.raises(RuntimeError, match="restricted"):
            main()
        cli.assert_not_called()


@pytest.mark.parametrize('url', ['http://api.example.test', 'https://api.example.test/path',
                               'https://api.example.test/#secret', 'https://user@api.example.test'])
def test_invalid_public_url_is_rejected_before_deploy(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_mysql_service_id_cannot_be_deployed_to():
    metadata = {'id': 'project', 'services': {'edges': [
        {'node': {'id': 'mysql', 'name': 'ctrl-x-mysql'}},
    ]}, 'environments': {'edges': [{'node': {'id': 'production', 'name': 'production'}}]}}
    with (
        patch('scripts.deploy_railway.railway', return_value=json.dumps(metadata)),
        pytest.raises(RuntimeError, match='Refusing deploy'),
    ):
        verify_api_target('project', 'mysql', 'production')


def test_api_service_in_selected_environment_is_accepted():
    metadata = {'id': 'project', 'services': {'edges': [
        {'node': {'id': 'api', 'name': 'ctrl-x-api'}},
    ]}, 'environments': {'edges': [{'node': {'id': 'environment', 'name': 'production'}}]}}
    with patch('scripts.deploy_railway.railway', return_value=json.dumps(metadata)):
        verify_api_target('project', 'api', 'environment')


def test_release_without_migration_hook_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'railway.json').write_text(json.dumps({
        'build': {'builder': 'DOCKERFILE'}, 'deploy': {'healthcheckPath': '/health'},
    }), encoding='utf-8')
    with pytest.raises(ValueError, match='controlled migration'):
        validate_release_config()
