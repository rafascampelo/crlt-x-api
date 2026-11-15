"""Validate production prerequisites, then replace PID 1 with Uvicorn."""

import os
import sys

from scripts.migrate_production import check_schema


def main():
    try:
        environment = os.environ.get("APP_ENV", "development")
        if environment not in {"development", "test", "production"}:
            raise ValueError("Invalid APP_ENV")
        if os.environ.get("RAILWAY_ENVIRONMENT_ID") and environment != "production":
            raise ValueError("Railway API requires APP_ENV=production")
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("Invalid PORT")
        if environment == "production":
            from app.core.config import get_settings

            settings = get_settings()
            if any(not origin.startswith("https://") for origin in settings.origins):
                raise ValueError("Production CORS origins require HTTPS")
            check_schema()
    except Exception as error:  # noqa: BLE001 -- Fail closed without exposing connection credentials.
        print(f"API startup prerequisites failed ({type(error).__name__})", file=sys.stderr)
        return 1
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app",
                             "--host", "0.0.0.0", "--port", str(port), "--no-access-log"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
