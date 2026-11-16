"""Legacy separate-service publisher; NOT a one-off task runner.

The current workflow uses the API's native pre-deploy hook instead. Never remove
the equal-service guard: this uploader replaces the destination with a sentinel.
"""

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from scripts.deploy_railway import (
    UUID,
    deployment_id_from_upload,
    railway,
    verify_api_target,
    wait_for_deployment,
)


def prepare_release(source: Path, destination: Path):
    # Explicit allowlist: never copy .env, git metadata, local data or credentials.
    for name in ("Dockerfile", ".dockerignore", ".railwayignore", "requirements.lock",
                 "app", "alembic", "alembic.ini", "scripts"):
        entry = source / name
        if entry.is_dir():
            shutil.copytree(entry, destination / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(entry, destination / name)
    config = {
        "build": {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"},
        "deploy": {
            "preDeployCommand": ["python -m scripts.db db:migrate"],
            "startCommand": "python -m scripts.migration_sentinel",
            "healthcheckPath": "/health", "healthcheckTimeout": 300,
            "restartPolicyType": "NEVER", "numReplicas": 1,
        },
    }
    (destination / "railway.json").write_text(json.dumps(config), encoding="utf-8")


def main():
    if (os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_REF") != "refs/heads/prod"):
        raise RuntimeError("Database release is restricted to a GitHub push on prod")
    for name in ("RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_MIGRATIONS_SERVICE_ID",
                 "RAILWAY_ENVIRONMENT_ID", "RAILWAY_SERVICE_ID"):
        if not os.environ.get(name):
            raise RuntimeError(f"Missing production configuration: {name}")
    project = os.environ["RAILWAY_PROJECT_ID"]
    service = os.environ["RAILWAY_MIGRATIONS_SERVICE_ID"]
    environment = os.environ["RAILWAY_ENVIRONMENT_ID"]
    if any(not re.fullmatch(UUID, value) for value in (
        project, service, environment, os.environ["RAILWAY_SERVICE_ID"],
    )):
        raise ValueError("Railway identifiers must be UUIDs")
    if service == os.environ["RAILWAY_SERVICE_ID"]:
        raise ValueError("Migration service must be separate from API")
    verify_api_target(project, service, environment, expected_name="ctrl-x-migrations")
    source = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="ctrlx-migrations-") as directory:
        release = Path(directory)
        prepare_release(source, release)
        try:
            os.chdir(release)
            railway("link", "--project", project, "--environment", environment,
                    "--service", service)
            output = railway("up", "--detach", "--json", "--service", service,
                             "--environment", environment)
            deployment = deployment_id_from_upload(output)
            wait_for_deployment(deployment, service, environment)
        finally:
            os.chdir(source)
    print(f"Database migration deployment verified: {deployment}", flush=True)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"Database migrations verified: `{os.environ['GITHUB_SHA']}`\n\n"
                         f"Railway deployment: `{deployment}`\n")


if __name__ == "__main__":
    main()
