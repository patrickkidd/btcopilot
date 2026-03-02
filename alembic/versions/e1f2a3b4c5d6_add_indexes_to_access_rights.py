"""Add indexes to access_rights

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-02 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
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
