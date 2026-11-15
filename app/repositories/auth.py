"""Authentication persistence shared by all API instances."""

import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import AuthEvent, LoginLimit

LOGIN_WINDOW_SECONDS = 300
LOGIN_ATTEMPTS = 5


def utc(value: datetime) -> datetime:
    # MySQL DATETIME returns naive values, stored here exclusively as UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def audit(db: Session, action: str, user_id: str | None = None) -> None:
    db.add(AuthEvent(id=str(uuid4()), action=action, user_id=user_id, created_at=datetime.now(UTC)))


def reserve_login_attempt(db: Session, email: str) -> int:
    """Atomically reserve an attempt, returning seconds until retry when blocked."""
    key = hmac.new(
        get_settings().secret_key.get_secret_value().encode(), email.encode(), hashlib.sha256,
    ).hexdigest()
    now = datetime.now(UTC)
    # DATETIME(0) may round fractional seconds up, placing the start in the future.
    values = {"key": key, "window_start": now.replace(microsecond=0), "attempts": 0}
    if db.get_bind().dialect.name == "mysql":
        statement = mysql_insert(LoginLimit).values(**values)
        statement = statement.on_duplicate_key_update(key=statement.inserted.key)
    else:
        statement = sqlite_insert(LoginLimit).values(**values).on_conflict_do_nothing()
    db.execute(statement)
    limit = db.scalar(select(LoginLimit).where(LoginLimit.key == key).with_for_update())
    now = datetime.now(UTC)
    reset_at = utc(limit.window_start) + timedelta(seconds=LOGIN_WINDOW_SECONDS)
    if now >= reset_at:
        limit.window_start = now.replace(microsecond=0)
        limit.attempts = 0
        reset_at = limit.window_start + timedelta(seconds=LOGIN_WINDOW_SECONDS)
    if limit.attempts >= LOGIN_ATTEMPTS:
        audit(db, "login_blocked")
        db.commit()
        return min(LOGIN_WINDOW_SECONDS, max(1, math.ceil((reset_at - now).total_seconds())))
    limit.attempts += 1
    db.commit()
    return 0
