"""Every coach turn's tool calls are kept, and a failed turn can be picked up.

Adds the turn events table, each statement's turn id, each change row's diagram
version, and the observations the watcher after a turn writes. Then it fills
the turn events for the turns that ran before this table existed, from the only
record of them there is, the change log:

- a coach statement gets its turn id and one tool call per item each of its
  change rows touched, worded as the tool would have answered and named the
  way a live call is: from the record as it stood at that change, which the
  change log rewinds to from the record now, so a thing removed since keeps
  the name it had;
- change rows the coach wrote in a turn that never answered are attached to the
  user's words that started that turn, which get the turn id, those tool calls
  and a closing "did not finish".

Read calls made before this revision were never written anywhere and cannot be
recovered.

Revision ID: 1b00000000ab
Revises: 1b00000000aa
"""

import copy
import itertools

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

from btcopilot import diagramjson, record
from btcopilot.models.diagram import diagram_data
from btcopilot.schema import DiagramData
from btcopilot.toolnames import names

revision = "1b00000000ab"
down_revision = "1b00000000aa"
branch_labels = None
depends_on = None

JSON = postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite")

TOOLS = {
    "person": "edit_person",
    "pair_bond": "edit_pair_bond",
    "event": "edit_event",
    "cluster": "edit_cluster",
}
# The record field a tool argument writes, for the arguments the thread's line
# is worded from.
ARGS = {
    "person": {"name": "name", "last_name": "last_name"},
    "event": {"kind": "kind", "description": "description", "dateTime": "date"},
    "cluster": {"title": "title"},
    "pair_bond": {},
}
FAILED = "The coach did not finish that turn."

changes = sa.table(
    "diagram_changes",
    sa.column("id", sa.Integer),
    sa.column("diagram_id", sa.Integer),
    sa.column("statement_id", sa.Integer),
    sa.column("turn_id", sa.String),
    sa.column("session_id", sa.String),
    sa.column("author", sa.String),
    sa.column("deltas", JSON),
    sa.column("created_at", sa.DateTime),
)
statements = sa.table(
    "statements",
    sa.column("id", sa.Integer),
    sa.column("discussion_id", sa.Integer),
    sa.column("speaker_id", sa.Integer),
    sa.column("turn_id", sa.String),
    sa.column("created_at", sa.DateTime),
)
diagrams = sa.table(
    "diagrams",
    sa.column("id", sa.Integer),
    sa.column("data", sa.LargeBinary),
)
discussions = sa.table(
    "discussions",
    sa.column("id", sa.Integer),
    sa.column("chat_user_speaker_id", sa.Integer),
)
events = sa.table(
    "turn_events",
    sa.column("turn_id", sa.String),
    sa.column("discussion_id", sa.Integer),
    sa.column("seq", sa.Integer),
    sa.column("kind", sa.String),
    sa.column("payload", JSON),
    sa.column("created_at", sa.DateTime),
)


def upgrade():
    op.create_table(
        "turn_events",
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("discussion_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["discussion_id"], ["discussions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id", "seq", name="uq_turn_events_seq"),
    )
    with op.batch_alter_table("turn_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_turn_events_turn_id"), ["turn_id"])
        batch_op.create_index(
            batch_op.f("ix_turn_events_discussion_id"), ["discussion_id"]
        )
        batch_op.create_index(batch_op.f("ix_turn_events_id"), ["id"])

    op.create_table(
        "observations",
        sa.Column("diagram_id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "duplicate_person",
                "duplicate_event",
                "add_without_read",
                name="observationkind",
            ),
            nullable=False,
        ),
        sa.Column("detail", JSON, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("observations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_observations_diagram_id"), ["diagram_id"])
        batch_op.create_index(batch_op.f("ix_observations_turn_id"), ["turn_id"])
        batch_op.create_index(batch_op.f("ix_observations_id"), ["id"])

    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("turn_id", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_statements_turn_id"), ["turn_id"])

    with op.batch_alter_table("diagram_changes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=True))

    backfill(op.get_bind())


def downgrade():
    with op.batch_alter_table("diagram_changes", schema=None) as batch_op:
        batch_op.drop_column("version")
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_statements_turn_id"))
        batch_op.drop_column("turn_id")
    op.drop_table("observations")
    op.drop_table("turn_events")
    sa.Enum(name="observationkind").drop(op.get_bind(), checkfirst=True)


def calls(deltas: list[dict], before: DiagramData, after: DiagramData) -> list[dict]:
    """One tool call per item a change row touched, in the order it touched them,
    named from the record before the row, or after it for a thing the row added."""
    made = {
        str(d["after"])
        for d in deltas
        if d["item_kind"] == "diagram" and d["field"] == "lastItemId"
    }
    touched = [d for d in deltas if d["item_kind"] in TOOLS]
    out = []
    for (kind, item_id), group in itertools.groupby(
        touched, key=lambda d: (d["item_kind"], str(d["item_id"]))
    ):
        group = list(group)
        if any(d["field"] is None and d["after"] is None for d in group):
            args = {"item_kind": kind, "item_id": group[0]["item_id"]}
            out.append(
                {
                    "type": "tool_call",
                    "name": "remove",
                    "args": args,
                    "names": names(before, "remove", args),
                    "result": f"Removed {kind} {item_id}.",
                }
            )
            continue
        new = (
            all(d["before"] is None for d in group)
            if kind == "cluster"
            else item_id in made
        )
        # A row logs a thing it made as one add holding it whole, or, before
        # adds were logged whole, as field sets on its new id.
        fields = {
            field: value
            for d in group
            for field, value in (
                d["after"].items() if d["field"] is None else [(d["field"], d["after"])]
            )
        }
        args = {
            arg: fields[field]
            for field, arg in ARGS[kind].items()
            if isinstance(fields.get(field), str)
        }
        if not new:
            args["id"] = group[0]["item_id"]
        out.append(
            {
                "type": "tool_call",
                "name": TOOLS[kind],
                "args": args,
                "names": names(
                    after if new else before,
                    TOOLS[kind],
                    {"id": group[0]["item_id"]},
                ),
                "result": f"{'Added' if new else 'Changed'} {kind} {item_id}.",
            }
        )
    return out


def named(conn, rows) -> dict[int, list[dict]]:
    """Each change row's tool calls, by rewinding each diagram's record from
    now through its whole change log, newest first."""
    wanted = {r.id for r in rows}
    out = {}
    for diagram_id, blob in conn.execute(
        sa.select(diagrams.c.id, diagrams.c.data).where(
            diagrams.c.id.in_({r.diagram_id for r in rows})
        )
    ).all():
        data = diagramjson.loads(blob)
        for change_id, deltas in conn.execute(
            sa.select(changes.c.id, changes.c.deltas)
            .where(changes.c.diagram_id == diagram_id)
            .order_by(changes.c.id.desc())
        ).all():
            after = copy.deepcopy(data) if change_id in wanted else None
            record.rewind(data, deltas)
            if after is not None:
                out[change_id] = calls(
                    deltas, diagram_data(data), diagram_data(after)
                )
    return out


def backfill(conn):
    rows = conn.execute(
        sa.select(changes)
        .where(changes.c.author == "coach", ~changes.c.turn_id.like("undo:%"))
        .order_by(changes.c.id)
    ).all()
    kept = named(conn, rows)
    answered = [r for r in rows if r.statement_id is not None]
    orphaned = [r for r in rows if r.statement_id is None]

    said = {
        s.id: s
        for s in conn.execute(
            sa.select(statements).where(
                statements.c.id.in_({r.statement_id for r in answered})
            )
        ).all()
    }
    turns: dict[str, dict] = {}
    for row in answered:
        turn = turns.setdefault(
            row.turn_id,
            {
                "statement_id": row.statement_id,
                "discussion_id": said[row.statement_id].discussion_id,
                "rows": [],
                "failed": False,
            },
        )
        turn["rows"].append(row)

    unanswered: dict[str, list] = {}
    for row in orphaned:
        unanswered.setdefault(row.turn_id, []).append(row)
    for turn_id, group in unanswered.items():
        discussion_id = int(group[0].session_id)
        speaker = conn.execute(
            sa.select(discussions.c.chat_user_speaker_id).where(
                discussions.c.id == discussion_id
            )
        ).scalar_one()
        words = conn.execute(
            sa.select(statements.c.id)
            .where(
                statements.c.discussion_id == discussion_id,
                statements.c.speaker_id == speaker,
                statements.c.created_at <= group[0].created_at,
            )
            .order_by(statements.c.created_at.desc(), statements.c.id.desc())
            .limit(1)
        ).scalar_one()
        conn.execute(
            changes.update()
            .where(changes.c.id.in_([r.id for r in group]))
            .values(statement_id=words)
        )
        turns[turn_id] = {
            "statement_id": words,
            "discussion_id": discussion_id,
            "rows": group,
            "failed": True,
        }

    for turn_id, turn in turns.items():
        conn.execute(
            statements.update()
            .where(statements.c.id == turn["statement_id"])
            .values(turn_id=turn_id)
        )
        written = [
            (row.created_at, call)
            for row in turn["rows"]
            for call in kept[row.id]
        ]
        if turn["failed"]:
            written.append(
                (turn["rows"][-1].created_at, {"type": "failed", "message": FAILED})
            )
        if written:
            conn.execute(
                events.insert(),
                [
                    {
                        "turn_id": turn_id,
                        "discussion_id": turn["discussion_id"],
                        "seq": seq,
                        "kind": event["type"],
                        "payload": event,
                        "created_at": at,
                    }
                    for seq, (at, event) in enumerate(written, start=1)
                ],
            )
