"""An admin opening another person's diagram once wrote a read-write access
right for himself on it (release 3.2026.10.1.4). Since then the opening is
read-only and grants nothing, but the right it left makes the app take the
diagram for one shared with him: it shows his own conversations on it, none,
instead of the owner's. Every access right an admin holds on a diagram he
does not own is that leftover; production holds one.

Revision ID: 1b00000000c1
Revises: 1b00000000c0
"""

from alembic import op

revision = "1b00000000c1"
down_revision = "1b00000000c0"
branch_labels = None
depends_on = None

LEFTOVERS = (
    "DELETE FROM access_rights WHERE EXISTS (SELECT 1 FROM users, diagrams"
    " WHERE users.id = access_rights.user_id"
    " AND diagrams.id = access_rights.diagram_id"
    " AND diagrams.user_id != users.id"
    " AND ',' || users.roles || ',' LIKE '%,admin,%')"
)


def upgrade():
    op.execute(LEFTOVERS)


def downgrade():
    raise NotImplementedError("roll forward instead")
