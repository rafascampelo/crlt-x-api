import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, Computed, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LinkStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ProfessionalLink(Base):
    __tablename__ = "professional_links"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked', 'rejected', 'cancelled')",
            name="ck_link_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    professional_id: Mapped[str] = mapped_column(ForeignKey("professionals.id"), index=True)
    status: Mapped[LinkStatus] = mapped_column(
        Enum(LinkStatus, values_callable=lambda values: [v.value for v in values],
             native_enum=False, length=9), default=LinkStatus.PENDING,
    )
    # MySQL permits multiple NULL values in a unique index, preserving revoked links.
    active_patient_id: Mapped[str | None] = mapped_column(
        String(36), Computed("CASE WHEN status = 'active' THEN patient_id ELSE NULL END"),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareAuditEvent(Base):
    __tablename__ = "care_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), index=True)
    resource_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
