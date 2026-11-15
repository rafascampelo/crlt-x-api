from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import Role, User

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("not-a-real-password-for-timing")
COOKIE_NAME = "ctrlx_access"


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": user.id, "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
         "iat": now, "exp": now + timedelta(minutes=15)},
        settings.secret_key.get_secret_value(), algorithm="HS256",
    )


def current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    token = request.cookies.get(COOKIE_NAME)
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not token:
        raise error
    settings = get_settings()
    try:
        claims = jwt.decode(
            token, settings.secret_key.get_secret_value(), algorithms=["HS256"],
            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        user_id = str(UUID(claims["sub"]))
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise error from None
    user = db.get(User, user_id)
    if user is None:
        raise error
    return user


def require_role(role: Role):
    def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency


def require_trusted_origin(request: Request) -> None:
    if request.headers.get("origin") not in get_settings().origins:
        raise HTTPException(status_code=403, detail="Untrusted origin")
