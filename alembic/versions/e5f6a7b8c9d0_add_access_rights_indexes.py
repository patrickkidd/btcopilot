"""Add indexes to access_rights diagram_id and user_id

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-01 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_access_rights_diagram_id", "access_rights", ["diagram_id"])
    op.create_index("ix_access_rights_user_id", "access_rights", ["user_id"])


def downgrade():
    op.drop_index("ix_access_rights_user_id", table_name="access_rights")
    op.drop_index("ix_access_rights_diagram_id", table_name="access_rights")
