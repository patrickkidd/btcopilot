"""A desktop file made into a new diagram: the model-call purpose for an
import, the observations kind counting what an import brought, and the time a
diagram was deleted, which hides it and removes nothing.

Revision ID: 1b00000000c6
Revises: 1b00000000c5
"""

import sqlalchemy as sa
from alembic import op

revision = "1b00000000c6"
down_revision = "1b00000000c5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("diagrams", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE purpose ADD VALUE IF NOT EXISTS 'import'")
            op.execute("ALTER TYPE observationkind ADD VALUE IF NOT EXISTS 'import'")


def downgrade():
    op.drop_column("diagrams", "deleted_at")
    # Postgres cannot drop an enum label; both stay, unused.
