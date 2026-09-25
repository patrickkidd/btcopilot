"""Questions the coach keeps become things an interaction can point at, and
the user's dismissal of one becomes a kind of tap. Two enum labels are added;
no row is read or written and no record blob is touched.

Revision ID: 1b00000000ad
Revises: 1b00000000ac
"""

from alembic import op

revision = "1b00000000ad"
down_revision = "1b00000000ac"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite stores these enums as plain strings with no list to extend.
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE itemkind ADD VALUE IF NOT EXISTS 'question'")
        op.execute("ALTER TYPE interactionkind ADD VALUE IF NOT EXISTS 'dismiss'")


def downgrade():
    raise NotImplementedError(
        "Postgres cannot drop an enum label: roll forward instead"
    )
