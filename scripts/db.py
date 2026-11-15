"""Alembic commands shared by local development and Railway production."""

import argparse
import os
import sys

from alembic.config import Config
from sqlalchemy import create_engine

from alembic import command
from app.core.database_config import DatabaseSettings
from scripts.ci_database import validate_ci_database
from scripts.migrate_production import (
    check_connection,
    migrate,
    migration_status as status,
    production_engine,
    verify_revision,
)


def is_production():
    return os.environ.get("APP_ENV") == "production" or bool(os.environ.get("RAILWAY_ENVIRONMENT_ID"))


def local_engine():
    url = DatabaseSettings().database_url.get_secret_value()
    if os.environ.get("CI") == "true":
        validate_ci_database(url)
    return create_engine(url, hide_parameters=True, pool_pre_ping=True)


def execute(args):
    config = Config("alembic.ini")
    production = is_production()
    if args.operation in {"db:rollback", "db:create"} and production:
        raise RuntimeError("Production rollback and revision generation are disabled; use a reviewed PR")
    if args.operation == "db:create":
        command.revision(config, message=args.message, autogenerate=args.autogenerate)
        return
    if args.operation == "db:migrate" and production:
        migrate()
        return
    if args.operation == "db:rollback" and not args.allow_local_rollback:
        raise RuntimeError("Local rollback requires --allow-local-rollback on a disposable database")
    engine = production_engine() if production else local_engine()
    try:
        with engine.connect() as connection:
            if production:
                check_connection(connection)
            if args.operation == "db:status":
                status(connection, config, args.require_current)
            else:
                config.attributes["connection"] = connection
                if args.operation == "db:migrate":
                    command.upgrade(config, "head")
                    verify_revision(connection, config)
                else:
                    command.downgrade(config, "-1")
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("db:migrate")
    commands.add_parser("db:status").add_argument("--require-current", action="store_true")
    commands.add_parser("db:rollback").add_argument("--allow-local-rollback", action="store_true")
    create = commands.add_parser("db:create")
    create.add_argument("--message", required=True)
    create.add_argument("--autogenerate", action="store_true")
    args = parser.parse_args(argv)
    try:
        execute(args)
    except Exception as error:  # noqa: BLE001 -- Never expose URLs, SQL or migration contents.
        print(f"Database command failed ({type(error).__name__}); inspect schema/release plan",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
