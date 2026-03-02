"""add_index_to_diagrams_user_id

Revision ID: d2a5320cadc4
Revises: fea616e0fe7d
Create Date: 2026-03-02 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "d2a5320cadc4"
down_revision = "fea616e0fe7d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_diagrams_user_id"), "diagrams", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_diagrams_user_id"), table_name="diagrams")
