"""Production-only Railway CLI orchestration. Importing never publishes anything."""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
PENDING = {"INITIALIZING", "QUEUED", "WAITING", "BUILDING", "DEPLOYING"}


def validate_base_url(base_url: str):
    parsed = urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or parsed.port not in (None, 443)):
        raise ValueError("BACKEND_PRODUCTION_URL must be a public HTTPS base URL")


def validate_release_config():
    config = json.loads(Path("railway.json").read_text(encoding="utf-8"))
    if (config.get("build", {}).get("builder") != "DOCKERFILE"
            or config.get("deploy", {}).get("preDeployCommand") != [
                "python -m scripts.db db:migrate"
            ] or config.get("deploy", {}).get("healthcheckPath") != "/health"):
        raise ValueError("Release must include the controlled migration and healthcheck configuration")


def verify_api_target(project: str, service: str, environment: str,
                      expected_name: str = "ctrl-x-api"):
    metadata = json.loads(railway("status", "--project", project,
                                  "--environment", environment, "--json"))
    services = [edge["node"] for edge in metadata["services"]["edges"]]
    environments = [edge["node"] for edge in metadata["environments"]["edges"]]
    if (metadata["id"] != project
            or not any(item["id"] == service and item["name"] == expected_name for item in services)
            or not any(item["id"] == environment and item["name"] == "production"
                       for item in environments)):
        raise RuntimeError(f"Refusing deploy outside {expected_name} in the production environment")


def railway(*args: str) -> str:
    result = subprocess.run(
        ["railway", *args], capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode:
        # Do not dump arbitrary remote output, environment values or runtime logs.
        raise RuntimeError(f"Railway {args[0]} failed (exit {result.returncode}); inspect dashboard")
    return result.stdout


def deployment_id_from_upload(output: str) -> str:
    # CLI 5.74.0 returns this structured result with --detach --json.
    candidate = json.loads(output).get("deploymentId", "")
    if isinstance(candidate, str) and re.fullmatch(UUID, candidate):
        return candidate
    raise RuntimeError("Upload returned no deployment ID; refusing to verify an older deployment")


def wait_for_deployment(deployment_id: str, service: str, environment: str) -> None:
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        deployments = json.loads(
            railway("deployment", "list", "--service", service,
                    "--environment", environment, "--limit", "100", "--json")
        )
        current = next((item for item in deployments if item["id"] == deployment_id), None)
        if current:
            status = current["status"]
            print(f"Deployment {deployment_id}: {status}", flush=True)
            if status == "SUCCESS":
                return
            if status not in PENDING:
                raise RuntimeError(f"Publication failed: deployment status {status}")
        time.sleep(10)
    raise TimeoutError("Railway deployment did not succeed within 15 minutes")


def check_health(base_url: str) -> None:
    validate_base_url(base_url)
    for attempt in range(30):
        try:
            with urlopen(base_url.rstrip("/") + "/health", timeout=5) as response:
                if response.status == 200 and json.load(response) == {"status": "ok"}:
                    print("Production /health verified", flush=True)
                    return
        except (URLError, TimeoutError, ValueError):
            pass
        if attempt < 29:
            time.sleep(5)
    raise RuntimeError("Production /health failed; publication is not accepted")


def main() -> None:
    if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != (
        "refs/heads/prod"
    ):
        raise RuntimeError("Publication is restricted to a GitHub push on prod")
    for name in (
        "RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID",
        "RAILWAY_ENVIRONMENT_ID", "BACKEND_PRODUCTION_URL",
    ):
        if not os.environ.get(name):
            raise RuntimeError(f"Missing production configuration: {name}")
    project = os.environ["RAILWAY_PROJECT_ID"]
    service = os.environ["RAILWAY_SERVICE_ID"]
    environment = os.environ["RAILWAY_ENVIRONMENT_ID"]
    for value in (project, service, environment):
        if not re.fullmatch(UUID, value):
            raise ValueError("Railway project, service and environment must be UUIDs")
    base_url = os.environ["BACKEND_PRODUCTION_URL"]
    # Validate configuration before making any remote change.
    validate_base_url(base_url)
    validate_release_config()
    verify_api_target(project, service, environment)
    railway("link", "--project", project, "--environment", environment, "--service", service)
    output = railway(
        "up", "--detach", "--json", "--service", service, "--environment", environment
    )
    deployment_id = deployment_id_from_upload(output)
    print(f"Uploaded deployment {deployment_id}", flush=True)
    wait_for_deployment(deployment_id, service, environment)
    check_health(base_url)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"Production verified: `{os.environ['GITHUB_SHA']}`\n\n")
            stream.write(f"Railway deployment: `{deployment_id}`\n")


if __name__ == "__main__":
    main()
