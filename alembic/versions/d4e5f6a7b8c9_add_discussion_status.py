"""Add discussion status enum column

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-02-20 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None

STATUS_ENUM = sa.Enum(
    "pending",
    "generating",
    "failed",
    "pending_extraction",
    "extracting",
    "ready",
    name="discussionstatus",
)


def upgrade():
    STATUS_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "discussions",
        sa.Column(
            "status",
            STATUS_ENUM,
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade():
    op.drop_column("discussions", "status")
    STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
