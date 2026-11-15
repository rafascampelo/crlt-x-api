"""Add consent-based professional links and clinical access audit."""

import sqlalchemy as sa

from alembic import op

revision = "0004_professional_links"
down_revision = "0003_auth_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "professional_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("professional_id", sa.String(36), sa.ForeignKey("professionals.id"), nullable=False),
        sa.Column("status", sa.String(7), nullable=False),
        sa.Column("active_patient_id", sa.String(36), sa.Computed(
            "CASE WHEN status = 'active' THEN patient_id ELSE NULL END")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending', 'active', 'revoked')", name="ck_link_status"),
        sa.UniqueConstraint("active_patient_id"),
    )
    op.create_index("ix_professional_links_patient_id", "professional_links", ["patient_id"])
    op.create_index("ix_professional_links_professional_id", "professional_links", ["professional_id"])
    op.create_table(
        "care_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id")),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("actor_id", "patient_id"):
        op.create_index(f"ix_care_audit_events_{column}", "care_audit_events", [column])


def downgrade() -> None:
    op.drop_table("care_audit_events")
    op.drop_table("professional_links")
