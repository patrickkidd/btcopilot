"""The user saying an impression doesn't fit becomes a kind of tap. One enum
label is added; no row is read or written and no record blob is touched.

Revision ID: 1b00000000ae
Revises: 1b00000000ad
"""

from alembic import op

revision = "1b00000000ae"
down_revision = "1b00000000ad"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite stores these enums as plain strings with no list to extend.
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE interactionkind ADD VALUE IF NOT EXISTS 'doesnt_fit'")


def downgrade():
    raise NotImplementedError(
        "Postgres cannot drop an enum label: roll forward instead"
    )
