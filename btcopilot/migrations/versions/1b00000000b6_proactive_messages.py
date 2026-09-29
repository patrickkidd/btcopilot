"""The coach may write first: when the record makes a pattern visible, or when
the person agreed to be asked something later. Each such message is kept with
what triggered it, so a pattern is written once, and with when it was sent
and answered, so ignored ones hold back the next and none is sent twice. An edit the coach makes to
something the record held from an earlier turn is observed as well.

Revision ID: 1b00000000b6
Revises: 1b00000000b5
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b6"
down_revision = "1b00000000b5"
branch_labels = None
depends_on = None

TRIGGER = sa.Enum("correlation", "follow_up", name="proactivetrigger")
KINDS = (
    "proactive_sent",
    "proactive_opened",
    "proactive_replied",
    "proactive_returned",
    "proactive_refused",
    "earlier_edit",
)


def upgrade():
    op.create_table(
        "proactive_messages",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("diagram_id", sa.Integer(), nullable=False),
        sa.Column("trigger", TRIGGER, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("replied_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagram_id", "key", name="one_message_a_pattern"),
    )
    with op.batch_alter_table("proactive_messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_proactive_messages_id"), ["id"])
        batch_op.create_index(batch_op.f("ix_proactive_messages_user_id"), ["user_id"])
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
