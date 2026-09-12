"""The Personal chat app: preferences and birthdate on users, session titles, the
change log and the learning-data taps, passwordless sign-in, statement views and
kinds, and the diagram a user is currently on. One revision: no database ever ran
the seven it replaces.

Revision ID: e1f2a3b4c5d6
Revises: c8f1a2d3e4b5
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e1f2a3b4c5d6"
down_revision = "c8f1a2d3e4b5"
branch_labels = None
depends_on = None

AUTHOR = sa.Enum("user", "coach", "pro", "review", name="author")
INTERACTION_KIND = sa.Enum("look", "say", "chip_tap", "play", name="interactionkind")
ITEM_KIND = sa.Enum(
    "person", "event", "pair_bond", "emotion", "cluster", "diagram", name="itemkind"
)
KIND = sa.Enum("turn", "play", name="statementkind")
DISCUSSION_KIND = sa.Enum("chat", "recording", "note", name="discussionkind")
REVIEW_STATUS = sa.Enum(
    "agreed", "disputed", "settled", "unresolved", name="reviewstatus"
)
VOTE_CHOICE = sa.Enum("take", "change", "drop", name="votechoice")
RULE_SOURCE = sa.Enum("ai", "migration", "human", name="rulesource")


def _json():
    return JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    op.add_column(
        "users",
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("users", sa.Column("birthdate", sa.Date(), nullable=True))
    op.add_column("discussions", sa.Column("title", sa.Text(), nullable=True))

    op.create_table(
        "diagram_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "diagram_id",
            sa.Integer(),
            sa.ForeignKey("diagrams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "statement_id", sa.Integer(), sa.ForeignKey("statements.id"), nullable=True
        ),
        sa.Column("turn_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("author", AUTHOR, nullable=False),
        sa.Column("deltas", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
    )
    op.create_table(
        "diagram_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "diagram_id",
            sa.Integer(),
            sa.ForeignKey("diagrams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column(
            "statement_id", sa.Integer(), sa.ForeignKey("statements.id"), nullable=True
        ),
        sa.Column("kind", INTERACTION_KIND, nullable=False),
        sa.Column("item_kind", ITEM_KIND, nullable=False),
        sa.Column("item_id", sa.String(64), nullable=True),
    )

    op.create_table(
        "web_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=255), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_sessions_id", "web_sessions", ["id"])
    op.create_index("ix_web_sessions_user_id", "web_sessions", ["user_id"])
    op.create_index("ix_web_sessions_token", "web_sessions", ["token"], unique=True)

    op.create_table(
        "passkeys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transports", sa.JSON(), nullable=False),
        sa.Column("name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_passkeys_id", "passkeys", ["id"])
    op.create_index("ix_passkeys_user_id", "passkeys", ["user_id"])
    op.create_index(
        "ix_passkeys_credential_id", "passkeys", ["credential_id"], unique=True
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitations_id", "invitations", ["id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)

    op.create_table(
        "login_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("tries", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_codes_id", "login_codes", ["id"])
    op.create_index("ix_login_codes_email", "login_codes", ["email"])

    op.add_column("statements", sa.Column("views", sa.JSON(), nullable=True))

    op.add_column(
        "discussions",
        sa.Column(
            "title_set_by_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("current_diagram_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_users_current_diagram_id", "diagrams", ["current_diagram_id"], ["id"]
        )

    KIND.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "statements",
        sa.Column("kind", KIND, nullable=False, server_default="turn"),
    )
    op.add_column("statements", sa.Column("cluster_id", sa.String(64), nullable=True))

    DISCUSSION_KIND.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "discussions",
        sa.Column("kind", DISCUSSION_KIND, nullable=False, server_default="chat"),
    )

    op.create_table(
        "review_cuts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "discussion_id",
            sa.Integer(),
            sa.ForeignKey("discussions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "start_statement_id",
            sa.Integer(),
            sa.ForeignKey("statements.id"),
            nullable=False,
        ),
        sa.Column(
            "end_statement_id",
            sa.Integer(),
            sa.ForeignKey("statements.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=True),
        sa.Column("vote_opened_at", sa.DateTime(), nullable=True),
        sa.Column("nudged_at", sa.DateTime(), nullable=True),
        sa.Column("ratified_at", sa.DateTime(), nullable=True),
        sa.Column("agreement", _json(), nullable=True),
    )

    op.create_table(
        "review_codings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "cut_id",
            sa.Integer(),
            sa.ForeignKey("review_cuts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "diagram_id", sa.Integer(), sa.ForeignKey("diagrams.id"), nullable=False
        ),
        sa.Column("agent", _json(), nullable=True),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("cut_id", "user_id", name="uq_review_codings_cut_user"),
    )

    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "cut_id",
            sa.Integer(),
            sa.ForeignKey("review_cuts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("item_kind", ITEM_KIND, nullable=False),
        sa.Column("item_id", sa.String(64), nullable=True),
        sa.Column("takes", _json(), nullable=False),
        sa.Column("status", REVIEW_STATUS, nullable=False),
        sa.Column(
            "settle_change_id",
            sa.Integer(),
            sa.ForeignKey("diagram_changes.id"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "review_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "review_item_id",
            sa.Integer(),
            sa.ForeignKey("review_items.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("choice", VOTE_CHOICE, nullable=False),
        sa.Column("value", _json(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "review_item_id", "user_id", name="uq_review_votes_item_user"
        ),
    )

    op.create_table(
        "review_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", _json(), nullable=False),
        sa.Column("drafted_by", RULE_SOURCE, nullable=False),
        sa.Column("flags", _json(), nullable=False),
        sa.Column("ratified_at", sa.DateTime(), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("review_rules")
    op.drop_table("review_votes")
    op.drop_table("review_items")
    op.drop_table("review_codings")
    op.drop_table("review_cuts")
    bind = op.get_bind()
    RULE_SOURCE.drop(bind, checkfirst=True)
    VOTE_CHOICE.drop(bind, checkfirst=True)
    REVIEW_STATUS.drop(bind, checkfirst=True)

    op.drop_column("discussions", "kind")
    DISCUSSION_KIND.drop(bind, checkfirst=True)

    op.drop_column("statements", "cluster_id")
    op.drop_column("statements", "kind")
    KIND.drop(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_current_diagram_id", type_="foreignkey")
        batch.drop_column("current_diagram_id")

    op.drop_column("discussions", "title_set_by_user")

    op.drop_column("statements", "views")

    op.drop_table("login_codes")
    op.drop_table("invitations")
    op.drop_table("passkeys")
    op.drop_table("web_sessions")

    op.drop_table("diagram_interactions")
    op.drop_table("diagram_changes")
    bind = op.get_bind()
    ITEM_KIND.drop(bind, checkfirst=True)
    INTERACTION_KIND.drop(bind, checkfirst=True)
    AUTHOR.drop(bind, checkfirst=True)

    op.drop_column("discussions", "title")
    op.drop_column("users", "birthdate")
    op.drop_column("users", "preferences")
