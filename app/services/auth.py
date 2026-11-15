from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, password_hash
from app.models.user import Patient, Professional, Role, User
from app.repositories.users import by_email
from app.schemas.auth import Credentials, Registration


def register(db: Session, data: Registration) -> User:
    user = User(email=data.email, password_hash=password_hash.hash(data.password), role=data.role)
    profile = Patient(full_name=data.full_name) if data.role == Role.PATIENT else Professional(
        full_name=data.full_name
    )
    profile.user = user
    try:
        db.add(profile)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to register with this email") from None
    return user


def authenticate(db: Session, data: Credentials) -> User:
    user = by_email(db, data.email)
    valid = password_hash.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user
