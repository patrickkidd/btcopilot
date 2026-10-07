"""The observations kind for a turn whose notes say the person corrected the
coach.

Revision ID: 1b00000000c3
Revises: 1b00000000c2
"""

from alembic import op

revision = "1b00000000c3"
down_revision = "1b00000000c2"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE observationkind ADD VALUE IF NOT EXISTS 'person_corrected'"
            )


def downgrade():
    # Postgres cannot drop an enum label; the kind stays, unused.
    pass
