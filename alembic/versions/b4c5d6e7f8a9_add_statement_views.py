"""Add the coach statement's views

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("statements", sa.Column("views", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("statements", "views")
