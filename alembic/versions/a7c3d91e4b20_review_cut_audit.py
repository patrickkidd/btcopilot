"""Where the coach read a ratified cut differently from the room, written once
when the cut is ratified and read by the result screen afterwards.

Revision ID: a7c3d91e4b20
Revises: e1f2a3b4c5d6
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a7c3d91e4b20"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "review_cuts",
        sa.Column("audit", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
    )


def downgrade():
    op.drop_column("review_cuts", "audit")
