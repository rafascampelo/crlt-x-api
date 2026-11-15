import pytest

from scripts.ci_database import validate_ci_database


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


