"""Bugs and feedback get their own table: a row per fault per person, release
and day, counted rather than repeated, whether the page, the server or the
page's service worker caught it. The observations table goes back to what the
coach and the app do; its bug and feedback rows, sandbox data only, go.

Revision ID: 1b00000000bc
Revises: 1b00000000bb
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000bc"
down_revision = "1b00000000bb"
branch_labels = None
depends_on = None

KIND = sa.Enum("bug", "feedback", name="reportkind")
STATUS = sa.Enum("sent", "declined", name="reportstatus")
SOURCE = sa.Enum("page", "server", "worker", name="reportsource")
OBSERVATION_KINDS = (
    "duplicate_person",
    "duplicate_event",
    "add_without_read",
    "question_unsaid",
    "tool_refused",
    "step_cap",
    "turn_failed",
    "turn_declined",
    "play_refused",
    "play_failed",
    "earlier_edit",
    "proactive_sent",
    "proactive_opened",
    "proactive_replied",
    "proactive_returned",
    "proactive_refused",
)


def upgrade():
    op.create_table(
        "reports",
        sa.Column("kind", KIND, nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("diagram_id", sa.Integer(), nullable=True),
        sa.Column("turn_id", sa.String(length=64), nullable=True),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("release", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("source", SOURCE, nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("frames", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("request_id", sa.String(length=32), nullable=True),
        sa.Column("words", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind = 'bug' OR (source IS NULL AND signature IS NULL AND error IS NULL"
            " AND frames IS NULL AND request_id IS NULL)",
            name="report_feedback_carries_no_fault",
        ),
    )
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reports_id"), ["id"])
        batch_op.create_index(batch_op.f("ix_reports_user_id"), ["user_id"])
        batch_op.create_index(batch_op.f("ix_reports_diagram_id"), ["diagram_id"])
        batch_op.create_index(batch_op.f("ix_reports_signature"), ["signature"])
        batch_op.create_index(batch_op.f("ix_reports_request_id"), ["request_id"])
    op.execute("DELETE FROM observations WHERE kind IN ('bug', 'feedback')")
    # SQLite stores these enums as plain strings with no list to change.
    if op.get_bind().dialect.name != "postgresql":
        return
    kinds = ", ".join(f"'{kind}'" for kind in OBSERVATION_KINDS)
    op.execute("ALTER TYPE observationkind RENAME TO observationkind_old")
    op.execute(f"CREATE TYPE observationkind AS ENUM ({kinds})")
    op.execute(
        "ALTER TABLE observations ALTER COLUMN kind TYPE observationkind"
        " USING kind::text::observationkind"
    )
    op.execute("DROP TYPE observationkind_old")


def downgrade():
    raise NotImplementedError("roll forward instead")
