"""A notice's link is one of the fixed screens by name or any address in the
app starting with /app/ (R-0055), so the column is text with a check rather
than a list of names.

Revision ID: 1b00000000ba
Revises: 1b00000000b9
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000ba"
down_revision = "1b00000000b9"
branch_labels = None
depends_on = None

LINK = sa.Enum("account", "coach_settings", "task", "agenda", name="noticelink")
CHECK = "notice_link_is_a_screen_or_an_address"


def upgrade():
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.alter_column(
            "link",
            existing_type=LINK,
            type_=sa.String(length=200),
            existing_nullable=True,
            postgresql_using="link::text",
        )
        batch_op.create_check_constraint(
            CHECK,
            "link IN ('account', 'coach_settings', 'task', 'agenda')"
            " OR link LIKE '/app/%'",
        )
    if op.get_bind().dialect.name == "postgresql":
        LINK.drop(op.get_bind(), checkfirst=True)


def downgrade():
    raise NotImplementedError("roll forward instead")
