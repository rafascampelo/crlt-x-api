"""Distinguish refusal, cancellation and revocation without deleting link history."""

import sqlalchemy as sa

from alembic import op

revision = "0006_link_decisions"
down_revision = "0005_professional_crefito"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_link_status", "professional_links", type_="check")
    op.alter_column("professional_links", "status", existing_type=sa.String(7), type_=sa.String(9),
                    existing_nullable=False)
    op.create_check_constraint(
        "ck_link_status", "professional_links",
        "status IN ('pending', 'active', 'revoked', 'rejected', 'cancelled')",
    )
    op.add_column("professional_links", sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE professional_links SET closed_at = revoked_at WHERE status = 'revoked'")


def downgrade() -> None:
    op.drop_constraint("ck_link_status", "professional_links", type_="check")
    op.execute("UPDATE professional_links SET status = 'revoked', revoked_at = closed_at "
               "WHERE status IN ('rejected', 'cancelled')")
    op.drop_column("professional_links", "closed_at")
    op.alter_column("professional_links", "status", existing_type=sa.String(9), type_=sa.String(7),
                    existing_nullable=False)
    op.create_check_constraint(
        "ck_link_status", "professional_links", "status IN ('pending', 'active', 'revoked')",
    )
