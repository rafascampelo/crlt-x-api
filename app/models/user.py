import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(str, enum.Enum):
    PATIENT = "PATIENT"
    PROFESSIONAL = "PROFESSIONAL"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    patient: Mapped["Patient | None"] = relationship(back_populates="user", uselist=False)
    professional: Mapped["Professional | None"] = relationship(back_populates="user", uselist=False)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    user: Mapped[User] = relationship(back_populates="patient")


class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = (
        UniqueConstraint("crefito_region", "crefito_number", name="uq_professional_crefito"),
        CheckConstraint(
            "(crefito_region IS NULL AND crefito_number IS NULL) OR "
            "(crefito_region IS NOT NULL AND crefito_number IS NOT NULL "
            "AND crefito_region BETWEEN 1 AND 22)", name="ck_professional_crefito_pair",
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified') AND "
            "(verification_status != 'verified' OR (verified_at IS NOT NULL "
            "AND verification_reference IS NOT NULL))", name="ck_professional_verification",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # NULL is reserved for accounts created before CREFITO became mandatory.
    crefito_region: Mapped[int | None] = mapped_column(Integer)
    crefito_number: Mapped[str | None] = mapped_column(String(9))
    verification_status: Mapped[str] = mapped_column(
        String(20), default="unverified", server_default="unverified", nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_reference: Mapped[str | None] = mapped_column(String(255))
    user: Mapped[User] = relationship(back_populates="professional")
