"""add_discussion_date

Revision ID: fc24860407c0
Revises: b30fb43b8f92
Create Date: 2025-10-31 12:20:29.180150

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fc24860407c0'
down_revision = 'b30fb43b8f92'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discussions", sa.Column("discussion_date", sa.Date(), nullable=True)
    )


def downgrade():
    op.drop_column("discussions", "discussion_date")
