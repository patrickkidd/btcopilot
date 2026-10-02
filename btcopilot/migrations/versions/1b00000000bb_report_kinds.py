"""A person can send a bug report or feedback from the app; each is one
observation of its own kind.

Revision ID: 1b00000000bb
Revises: 1b00000000ba
"""

from alembic import op

revision = "1b00000000bb"
down_revision = "1b00000000ba"
branch_labels = None
depends_on = None

KINDS = ("bug", "feedback")


def upgrade():
    # SQLite stores these enums as plain strings with no list to extend.
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for kind in KINDS:
            op.execute(f"ALTER TYPE observationkind ADD VALUE IF NOT EXISTS '{kind}'")


def downgrade():
    raise NotImplementedError(
        "Postgres cannot drop an enum label: roll forward instead"
    )
