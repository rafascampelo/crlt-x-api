import pytest

from scripts.ci_database import validate_ci_database
from scripts.validate_commit_messages import validate


def test_accepts_isolated_mysql():
    validate_ci_database("mysql+pymysql://ctrlx_ci:fake@127.0.0.1:3306/ctrlx_ci")


@pytest.mark.parametrize(
    "url",
    [
        "mysql+pymysql://ctrlx_ci:fake@production.internal:3306/ctrlx_ci",
        "mysql+pymysql://ctrlx_ci:fake@127.0.0.1:3306/ctrlx",
        "mysql+pymysql://root:fake@127.0.0.1:3306/ctrlx_ci",
        "mysql+pymysql://ctrlx_ci:fake@127.0.0.1:3307/ctrlx_ci",
        "sqlite:///ctrlx_ci",
        "mysql+pymysql://ctrlx_ci:fake@127.0.0.1:3306/ctrlx_ci?unix_socket=/tmp/mysql.sock",
    ],
)
def test_rejects_nonisolated_database(url):
    with pytest.raises(ValueError):
        validate_ci_database(url)


@pytest.mark.parametrize(
    "message",
    [
        "feat: add clinical record form",
        "fix: validate patient access",
        "refactor: extract pain record service",
        "tests: cover clinical record permissions",
    ],
)
def test_accepts_allowed_commit_message(message):
    assert validate([("a" * 40, message)]) == []


@pytest.mark.parametrize(
    "message",
    [
        "chore: update dependencies",
        "Feat: add a feature",
        "feat add clinical record form",
        "feat: Add clinical record form",
        "feat: add clinical record form\n\nSigned-off-by: Patient",
        "feat: añadir registro",
    ],
)
def test_rejects_disallowed_commit_message(message):
    assert validate([("b" * 40, message)])
