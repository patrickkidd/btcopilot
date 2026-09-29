"""A product notice is written once with who it is for; each person it reaches
gets a notification row pointing at it when they next open the app, one per
person and notice. A notification that went nowhere but the app's own list is
marked so.

Revision ID: 1b00000000b9
Revises: 1b00000000b8
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b9"
down_revision = "1b00000000b8"
branch_labels = None
depends_on = None

AUDIENCE = sa.Enum("everyone", "role", "people", name="audience")
LINK = sa.Enum("account", "coach_settings", "task", "agenda", name="noticelink")
POINTS = "notification_points_at_its_kind"
NOTICE = "notifications_notice_id_fkey"


def upgrade():
    op.create_table(
        "notices",
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("body", sa.String(length=300), nullable=False),
        sa.Column("link", LINK, nullable=True),
        sa.Column("audience", AUDIENCE, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("user_ids", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(audience = 'role') = (role IS NOT NULL)"
            " AND (audience = 'people') = (user_ids IS NOT NULL)",
            name="notice_names_its_audience",
        ),
    )
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notices_id"), ["id"])
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notice_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            NOTICE, "notices", ["notice_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_unique_constraint(
            "notification_one_per_notice", ["user_id", "notice_id"]
        )
        batch_op.drop_constraint(POINTS, type_="check")
        batch_op.create_check_constraint(
            POINTS,
            "(kind = 'coach') = (statement_id IS NOT NULL)"
            " AND (kind IN ('task', 'reminder')) = (cut_id IS NOT NULL)"
            " AND (kind = 'notice') = (notice_id IS NOT NULL)",
        )
    # SQLite stores these enums as plain strings with no list to extend.
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notificationchannel ADD VALUE IF NOT EXISTS 'app'")


def downgrade():
    raise NotImplementedError(
        "Postgres cannot drop an enum label: roll forward instead"
    )
