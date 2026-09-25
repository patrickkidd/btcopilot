"""The questions and impressions the coach keeps in the record: what the page
may show of them, and the one pass back over past sessions that fills each kind
in (R-0006)."""

import logging
from dataclasses import dataclass
from typing import Callable

from btcopilot import prompts, record
from btcopilot.coachmodel import CoachModel
from btcopilot.coachturn import MAX_STEPS, Metered, drain, run_call
from btcopilot.extensions import db
from btcopilot.models import Author, Diagram, Discussion, Statement
from btcopilot.recordtext import outline
from btcopilot.schema import DiagramData, EvidenceKind, ItemKind
from btcopilot.toolbox import READS, ToolName, Toolbox, schemas
from btcopilot.toolnames import evidence_label

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Kind:
    """One kind the backfill fills in: its prompt, the tools it may call (the
    coach's reads, so it can see what the record already holds, and that
    kind's writes, so nothing else can change), and where the record marks a
    session gone through."""

    prompt: Callable[..., str]
    tools: tuple
    done: str
    turn: str


QUESTIONS = Kind(
    prompts.question_backfill,
    (*READS, ToolName.AddQuestion, ToolName.SetQuestion),
    "questions_backfilled",
    "backfill",
)
IMPRESSIONS = Kind(
    prompts.impression_backfill,
    (*READS, ToolName.AddImpression, ToolName.SetImpression),
    "impressions_backfilled",
    "impression-backfill",
)
START = "Go through the session."
# About one call to read, one round of adds, and sometimes one more.
CALLS_PER_SESSION = 3


def asked(diagram_id: int, data: DiagramData) -> list[dict]:
    """Every question ever asked and every impression ever raised, for the
    page. One the coach only keeps for later never leaves the server."""
    where = record.asked_in(diagram_id)
    return [
        {
            "id": q["id"],
            "text": q["text"],
            "kind": q["kind"],
            "open": q["state"] in record.SHOWN,
            "asked_at": q["asked_at"],
            "asked_in": where.get(q["id"]),
            "evidence": [_shown(data, one) for one in q.get("evidence") or []],
            "pushback": q.get("pushback"),
        }
        for q in data.questions
        if q["asked_at"] is not None
    ]


def _shown(data: DiagramData, one: dict) -> dict:
    """One piece of evidence with its label; a message also says which session
    it is in and on which day, or nothing once its session is gone."""
    out = {"kind": one["kind"], "id": one["id"], "label": evidence_label(data, one)}
    if one["kind"] == EvidenceKind.Statement:
        statement = db.session.get(Statement, one["id"])
        out["discussion_id"] = statement and statement.discussion_id
        out["at"] = statement and statement.created_at.date().isoformat()
    return out


def sessions(diagram: Diagram) -> list[Discussion]:
    """A family's chat sessions the coach spoke in, oldest first."""
    return (
        Discussion.query.filter(
            Discussion.diagram_id == diagram.id,
            Discussion.chat_ai_speaker_id.isnot(None),
            Discussion.statements.any(
                Statement.speaker_id == Discussion.chat_ai_speaker_id
            ),
        )
        .order_by(Discussion.created_at, Discussion.id)
        .all()
    )


def pending(diagram: Diagram, kind: Kind) -> tuple[list[Discussion], list[Discussion]]:
    """The sessions still to go through, and the ones already gone through."""
    done = set(getattr(diagram.get_diagram_data(), kind.done))
    found = sessions(diagram)
    return [s for s in found if s.id not in done], [s for s in found if s.id in done]


def transcript(discussion: Discussion) -> str:
    """The session as the backfill reads it, each coach message numbered by
    its statement id."""
    lines = []
    for statement in sorted(discussion.statements, key=lambda s: (s.order or 0, s.id)):
        if not statement.text:
            continue
        if statement.speaker_id == discussion.chat_ai_speaker_id:
            lines.append(f"[coach message {statement.id}] {statement.text}")
        else:
            lines.append(f"[person] {statement.text}")
    return "\n\n".join(lines)


def backfill(diagram: Diagram, discussion: Discussion, model, kind: Kind) -> int:
    """Go through one past session once, then mark it gone through. Returns
    how many model calls it made."""
    last = max(
        (
            s
            for s in discussion.statements
            if s.speaker_id == discussion.chat_ai_speaker_id
        ),
        key=lambda s: (s.order or 0, s.id),
    )
    turn_id = f"{kind.turn}:{discussion.id}"
    toolbox = Toolbox(
        diagram.id,
        turn_id,
        user_id=discussion.user_id,
        session_id=str(discussion.id),
        author=Author.Coach,
        statement_id=last.id,
    )
    metered = Metered(model, discussion.user_id, diagram.id, turn_id)
    system = kind.prompt(
        map=outline(toolbox.data, toolbox.diagram.version),
        transcript=transcript(discussion),
    )
    tools = [schema for schema in schemas() if schema["name"] in kind.tools]
    messages = [{"role": "user", "content": START}]
    calls = 0
    for _ in range(MAX_STEPS):
        turn = drain(metered.turn(system, messages, tools, turn_id))
        calls += 1
        if not turn.calls:
            break
        results = []
        for call in turn.calls:
            if call.name in kind.tools:
                text, _, refusal = run_call(toolbox, call)
                refused = refusal is not None
            else:
                text, refused = f"There is no tool called {call.name} here", True
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": text,
                    "is_error": refused,
                }
            )
        messages.append({"role": "assistant", "content": turn.blocks})
        messages.append({"role": "user", "content": results})
    else:
        _log.warning(f"Backfill of session {discussion.id} used all {MAX_STEPS} steps")
    record.apply(
        diagram.id,
        [
            {
                "item_kind": ItemKind.Diagram.value,
                "item_id": None,
                "field": kind.done,
                "after": [*getattr(toolbox.data, kind.done), discussion.id],
            }
        ],
        author=Author.Coach,
        turn_id=turn_id,
        user_id=discussion.user_id,
        session_id=str(discussion.id),
        statement_id=last.id,
    )
    return calls


def run(diagrams: list[Diagram], kind: Kind, model=None) -> list[dict]:
    """Every session of these families not yet gone through, oldest first."""
    model = model or CoachModel()
    done = []
    for diagram in diagrams:
        todo, _ = pending(diagram, kind)
        for discussion in todo:
            calls = backfill(diagram, discussion, model, kind)
            done.append({"diagram": diagram.id, "session": discussion.id, "model_calls": calls})
    return done
