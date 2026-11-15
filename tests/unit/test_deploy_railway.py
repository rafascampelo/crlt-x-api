import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from scripts.deploy_railway import (
    check_health,
    deployment_id_from_upload,
    main,
    railway,
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
