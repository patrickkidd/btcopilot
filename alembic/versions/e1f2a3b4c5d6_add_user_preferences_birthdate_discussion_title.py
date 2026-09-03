"""add user preferences and birthdate, discussion title

Revision ID: e1f2a3b4c5d6
Revises: c8f1a2d3e4b5
Create Date: 2026-09-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "c8f1a2d3e4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("users", sa.Column("birthdate", sa.Date(), nullable=True))
    op.add_column("discussions", sa.Column("title", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("discussions", "title")
    op.drop_column("users", "birthdate")
    op.drop_column("users", "preferences")
