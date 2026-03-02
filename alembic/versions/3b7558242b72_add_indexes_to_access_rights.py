"""add_indexes_to_access_rights

Revision ID: 3b7558242b72
Revises: d4e5f6a7b8c9
Create Date: 2026-03-01 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3b7558242b72"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_access_rights_diagram_id"),
        "access_rights",
        ["diagram_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_rights_user_id"),
        "access_rights",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_access_rights_user_id"), table_name="access_rights")
    op.drop_index(op.f("ix_access_rights_diagram_id"), table_name="access_rights")
