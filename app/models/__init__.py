"""Register ORM models for Alembic."""

from app.models.auth import AuthEvent, AuthSession, LoginLimit
from app.models.user import Patient, Professional, Role, User

__all__ = ["AuthEvent", "AuthSession", "LoginLimit", "Patient", "Professional", "Role", "User"]
