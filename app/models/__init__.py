"""Register ORM models for Alembic."""

from app.models.user import Patient, Professional, Role, User

__all__ = ["Patient", "Professional", "Role", "User"]
