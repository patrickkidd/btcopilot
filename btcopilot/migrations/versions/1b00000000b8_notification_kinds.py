"""A notification points at a coach message or at a coding task on the agenda,
and says which kind it is, so each kind is held back only by its own. A notice
is reserved for a product notice; nothing sends one yet.

Revision ID: 1b00000000b8
Revises: 1b00000000b7
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b8"
down_revision = "1b00000000b7"
branch_labels = None
depends_on = None

KIND = sa.Enum("coach", "task", "reminder", "notice", name="notificationkind")
POINTS = "notification_points_at_its_kind"
CUT = "notifications_cut_id_fkey"


def upgrade():
    KIND.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        # every row so far points at a coach message
        batch_op.add_column(
            sa.Column("kind", KIND, nullable=False, server_default="coach")
        )
        batch_op.add_column(sa.Column("cut_id", sa.Integer(), nullable=True))
        batch_op.alter_column("statement_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            CUT, "review_cuts", ["cut_id"], ["id"], ondelete="CASCADE"
        )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column("kind", existing_type=KIND, server_default=None)
        batch_op.create_check_constraint(
            POINTS,
            "(kind = 'coach') = (statement_id IS NOT NULL)"
            " AND (kind IN ('task', 'reminder')) = (cut_id IS NOT NULL)",
        )


def downgrade():
    op.execute("DELETE FROM notifications WHERE kind != 'coach'")
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_constraint(POINTS, type_="check")
        batch_op.drop_constraint(CUT, type_="foreignkey")
        batch_op.drop_column("cut_id")
        batch_op.drop_column("kind")
        batch_op.alter_column(
            "statement_id", existing_type=sa.Integer(), nullable=False
        )
    KIND.drop(op.get_bind(), checkfirst=True)
