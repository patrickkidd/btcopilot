"""A desktop file brought into a diagram: the model-call purpose for the
import's coding pass and merge pass, the reason the coach writes first after
an import, and the observations kind counting how an import's items were
placed.

Revision ID: 1b00000000c4
Revises: 1b00000000c3
"""

from alembic import op

revision = "1b00000000c4"
down_revision = "1b00000000c3"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE purpose ADD VALUE IF NOT EXISTS 'import'")
            op.execute("ALTER TYPE proactivetrigger ADD VALUE IF NOT EXISTS 'import'")
            op.execute("ALTER TYPE observationkind ADD VALUE IF NOT EXISTS 'import'")


def downgrade():
    # Postgres cannot drop an enum label; all three stay, unused.
    pass
