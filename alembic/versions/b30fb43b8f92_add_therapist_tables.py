"""Add discussions, statements, speakers, and feedbacks tables

Revision ID: 123abc456def
Revises:
Create Date: 2023-11-15 15:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from btcopilot.personal.models import SpeakerType

# revision identifiers, used by Alembic.
revision = "b30fb43b8f92"
down_revision = "7c9e805e2b21"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discussions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("diagram_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("chat_user_speaker_id", sa.Integer(), nullable=True),
        sa.Column("chat_ai_speaker_id", sa.Integer(), nullable=True),
        sa.Column(
            "last_topic",
            sa.Text(),
            nullable=True,
            comment="The topic that the model should follow the user on, e.g. presenting problem, new issue",
        ),
        sa.Column(
            "extracting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether background extraction job should run for this discussion's statements",
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_discussions_user_id"), "discussions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_discussions_diagram_id"), "discussions", ["diagram_id"], unique=False
    )

    op.create_table(
        "speakers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discussion_id", sa.Integer(), nullable=True),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "type",
            ENUM(SpeakerType, name="speakertype"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_speakers_discussion_id"), "speakers", ["discussion_id"], unique=False
    )
    op.create_index(
        op.f("ix_speakers_person_id"), "speakers", ["person_id"], unique=False
    )

    # No foreign key constraints - rely on application-level integrity

    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("discussion_id", sa.Integer(), nullable=False),
        sa.Column("speaker_id", sa.Integer(), nullable=True),
        sa.Column("pdp_deltas", sa.JSON(), nullable=True),
        sa.Column("custom_prompts", sa.JSON(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column(
            "approved",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="Whether the extraction has been approved by an admin",
        ),
        sa.Column(
            "approved_by",
            sa.String(length=100),
            nullable=True,
            comment="User ID who approved the extraction",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(),
            nullable=True,
            comment="When the extraction was approved",
        ),
        sa.Column(
            "exported_at",
            sa.DateTime(),
            nullable=True,
            comment="When this statement was exported as a test case",
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on foreign keys for better query performance
    op.create_index(
        op.f("ix_statements_discussion_id"),
        "statements",
        ["discussion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_statements_speaker_id"), "statements", ["speaker_id"], unique=False
    )

    # Create feedbacks table
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("auditor_id", sa.String(length=100), nullable=False),
        sa.Column("feedback_type", sa.String(length=20), nullable=False),
        sa.Column(
            "thumbs_down", sa.Boolean(), nullable=True, server_default=sa.text("false")
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("edited_extraction", sa.JSON(), nullable=True),
        sa.Column(
            "approved",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="Whether the feedback is approved as ground truth",
        ),
        sa.Column(
            "approved_by",
            sa.String(length=100),
            nullable=True,
            comment="User ID who approved the feedback",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(),
            nullable=True,
            comment="When the feedback was approved",
        ),
        sa.Column(
            "exported_at",
            sa.DateTime(),
            nullable=True,
            comment="When this feedback was exported as a test case",
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
            comment="Admin notes on why feedback wasn't approved",
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for feedbacks table
    op.create_index(
        op.f("ix_feedbacks_statement_id"),
        "feedbacks",
        ["statement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedbacks_auditor_id"),
        "feedbacks",
        ["auditor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedbacks_feedback_type"),
        "feedbacks",
        ["feedback_type"],
        unique=False,
    )

    # Create unique constraint to prevent duplicate feedback from same auditor for same statement/type
    op.create_index(
        "ix_feedbacks_unique_auditor_statement_type",
        "feedbacks",
        ["statement_id", "auditor_id", "feedback_type"],
        unique=True,
    )


def downgrade():
    # Drop tables in reverse order due to foreign key constraints

    # Drop feedbacks table and its indexes
    op.drop_index("ix_feedbacks_unique_auditor_statement_type", table_name="feedbacks")
    op.drop_index(op.f("ix_feedbacks_feedback_type"), table_name="feedbacks")
    op.drop_index(op.f("ix_feedbacks_auditor_id"), table_name="feedbacks")
    op.drop_index(op.f("ix_feedbacks_statement_id"), table_name="feedbacks")
    op.drop_table("feedbacks")

    # Drop statements table
    op.drop_index(op.f("ix_statements_speaker_id"), table_name="statements")
    op.drop_index(op.f("ix_statements_discussion_id"), table_name="statements")
    op.drop_table("statements")

    # No foreign key constraints to drop

    # Drop speakers table
    op.drop_index(op.f("ix_speakers_person_id"), table_name="speakers")
    op.drop_index(op.f("ix_speakers_discussion_id"), table_name="speakers")
    op.drop_table("speakers")

    # Drop discussions table
    op.drop_index(op.f("ix_discussions_diagram_id"), table_name="discussions")
    op.drop_index(op.f("ix_discussions_user_id"), table_name="discussions")
    op.drop_table("discussions")

    # Drop the SpeakerType ENUM
    connection = op.get_bind()
    speaker_type_enum = ENUM(name="speakertype")
    speaker_type_enum.drop(connection)
