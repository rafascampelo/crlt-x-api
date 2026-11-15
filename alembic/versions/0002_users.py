"""Create users and role-specific profiles."""

import sqlalchemy as sa

from alembic import op

revision = "0002_users"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("PATIENT", "PROFESSIONAL", native_enum=False, length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for table in ("patients", "professionals"):
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("full_name", sa.String(200), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("professionals")
    op.drop_table("patients")
    op.drop_table("users")
