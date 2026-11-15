from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import COOKIE_NAME, create_access_token, current_user, require_trusted_origin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Credentials, Registration, UserResponse
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: Registration, db: Annotated[Session, Depends(get_db)]):
    return auth.register(db, data)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(require_trusted_origin)])
def login(data: Credentials, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = auth.authenticate(db, data)
    response.set_cookie(
        COOKIE_NAME, create_access_token(user), max_age=900, httponly=True,
        secure=get_settings().app_env != "development", samesite="lax", path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: Annotated[User, Depends(current_user)]):
    response.headers["Cache-Control"] = "no-store"
    return user
