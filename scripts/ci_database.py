import os

from sqlalchemy.engine import make_url


def validate_ci_database(value: str) -> None:
    """Fail closed before any CI migration or database test touches a server."""
    url = make_url(value)
    if (
        url.drivername != "mysql+pymysql"
        or url.host != "127.0.0.1"
        or url.port != 3306
        or url.database != "ctrlx_ci"
        or url.username != "ctrlx_ci"
        or url.query
    ):
        raise ValueError("CI permits only the isolated local ctrlx_ci MySQL service")


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    validate_ci_database(database_url)
    if database_url != os.environ["TEST_DATABASE_URL"]:
        raise ValueError("DATABASE_URL and TEST_DATABASE_URL must match in CI")
    print("Isolated CI database configuration verified")


if __name__ == "__main__":
    main()
