"""A session's words can go while the record keeps its edits: deleting a
statement empties the link to it on change rows and interactions, where before
Postgres refused the delete.

Revision ID: 1b00000000ac
Revises: 1b00000000ab
"""

from alembic import op

revision = "1b00000000ac"
down_revision = "1b00000000ab"
branch_labels = None
depends_on = None

TABLES = ("diagram_changes", "diagram_interactions")
# Postgres's own name for an unnamed foreign key; SQLite reflects none, so its
# batch copy is given the same one.
NAMES = {"fk": "%(table_name)s_%(column_0_name)s_fkey"}


def relink(ondelete: str | None):
    for table in TABLES:
        name = f"{table}_statement_id_fkey"
        with op.batch_alter_table(table, naming_convention=NAMES) as batch_op:
            batch_op.drop_constraint(name, type_="foreignkey")
            batch_op.create_foreign_key(
                name, "statements", ["statement_id"], ["id"], ondelete=ondelete
            )


def upgrade():
    relink("SET NULL")


def downgrade():
    relink(None)
