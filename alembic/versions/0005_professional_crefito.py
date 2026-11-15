"""Require declared physiotherapist registration for new accounts, preserving legacy users."""

import sqlalchemy as sa

from alembic import op

revision = "0005_professional_crefito"
down_revision = "0004_professional_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("professionals", sa.Column("crefito_region", sa.Integer()))
    op.add_column("professionals", sa.Column("crefito_number", sa.String(9)))
    op.add_column("professionals", sa.Column(
        "verification_status", sa.String(20), nullable=False, server_default="unverified",
    ))
    op.add_column("professionals", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.add_column("professionals", sa.Column("verification_reference", sa.String(255)))
    op.create_unique_constraint(
        "uq_professional_crefito", "professionals", ["crefito_region", "crefito_number"],
    )
    op.create_check_constraint(
        "ck_professional_crefito_pair", "professionals",
        "(crefito_region IS NULL AND crefito_number IS NULL) OR "
        "(crefito_region IS NOT NULL AND crefito_number IS NOT NULL "
        "AND crefito_region BETWEEN 1 AND 22)",
    )
    # Evidence is required for a future trusted backend verification workflow.
    # This release never promotes a professional to verified.
    op.create_check_constraint(
        "ck_professional_verification", "professionals",
        "verification_status IN ('unverified', 'verified') AND "
        "(verification_status != 'verified' OR (verified_at IS NOT NULL "
        "AND verification_reference IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_professional_verification", "professionals", type_="check")
    op.drop_constraint("ck_professional_crefito_pair", "professionals", type_="check")
    op.drop_constraint("uq_professional_crefito", "professionals", type_="unique")
    op.drop_column("professionals", "verification_reference")
    op.drop_column("professionals", "verified_at")
    op.drop_column("professionals", "verification_status")
    op.drop_column("professionals", "crefito_number")
    op.drop_column("professionals", "crefito_region")
