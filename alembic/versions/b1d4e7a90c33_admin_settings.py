"""The table the admin command line writes: token caps and the nudge switch.

Revision ID: b1d4e7a90c33
Revises: a7c3d91e4b20
"""

import sqlalchemy as sa
from alembic import op

revision = "b1d4e7a90c33"
down_revision = "a7c3d91e4b20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "scope_id", name="uq_admin_settings_key_scope"),
    )
    op.create_index("ix_admin_settings_key", "admin_settings", ["key"])
    op.create_index("ix_admin_settings_id", "admin_settings", ["id"])


def downgrade():
    op.drop_index("ix_admin_settings_id", table_name="admin_settings")
    op.drop_index("ix_admin_settings_key", table_name="admin_settings")
    op.drop_table("admin_settings")
