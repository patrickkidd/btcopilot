"""A browser can be reached by web push once its person asks the coach to
message first, and every pointer sent to a coach message, by push or by email,
is kept with when its person opened it.

Revision ID: 1b00000000b7
Revises: 1b00000000b6
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b7"
down_revision = "1b00000000b6"
branch_labels = None
depends_on = None

CHANNEL = sa.Enum("push", "email", name="notificationchannel")


def upgrade():
    op.create_table(
        "push_subscriptions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    with op.batch_alter_table("push_subscriptions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_push_subscriptions_id"), ["id"])
        batch_op.create_index(batch_op.f("ix_push_subscriptions_user_id"), ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("channel", CHANNEL, nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_id"), ["id"])
        batch_op.create_index(batch_op.f("ix_notifications_user_id"), ["user_id"])


def downgrade():
    op.drop_table("notifications")
    CHANNEL.drop(op.get_bind(), checkfirst=True)
    op.drop_table("push_subscriptions")
