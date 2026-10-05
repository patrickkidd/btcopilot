"""The questions and impressions the coach keeps in the record: what the page
may show of them, and the one pass back over past sessions that fills each kind
in (R-0006)."""

import logging
from dataclasses import dataclass
from typing import Callable

from btcopilot import prompts, record
from btcopilot.coachmodel import CoachModel
from btcopilot.coachturn import MAX_STEPS, drain, run_call
from btcopilot.metered import Metered
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram, Discussion, Purpose, Statement
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
            "case_report_card": q.get(record.CARD),
            "answer": q.get("answer") and _answer(data, q["answer"]),
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


def _answer(data: DiagramData, one: dict) -> dict:
    """The person's message that answered a question, in their own words, or
    with no words once its session is gone (R-0708)."""
    statement = db.session.get(Statement, one["id"])
    return {**_shown(data, one), "text": statement and statement.text}


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


def order(statement: Statement) -> tuple[int, int]:
    return statement.order or 0, statement.id


def unread(discussion: Discussion, kind: Kind, done: list[int]) -> list[Statement]:
    """The session's statements the backfill has not gone through: all of
    them, or, once gone through, those after the last message the newest pass
    read, as the change that marked it gone through links it; a marking taken
    back since does not count."""
    said = sorted(discussion.statements, key=order)
    if discussion.id not in done:
        return said
    taken = record.undone(discussion.diagram_id)
    passes = [
        change
        for change in Change.query.filter_by(
            diagram_id=discussion.diagram_id, turn_id=f"{kind.turn}:{discussion.id}"
        ).order_by(Change.id.desc())
        if any(delta["field"] == kind.done for delta in change.deltas)
    ]
    # a pass taken back while a later one stays: read again from before it
    first = min((c.id for c in passes if c.id in taken), default=None)
    marked = next(
        (c for c in passes if c.id not in taken and (first is None or c.id < first)),
        None,
    )
    if marked is None and first is not None:
        return said
    if marked is None or marked.statement is None:
        raise ValueError(f"No change links the last message read in session {discussion.id}")
    return [s for s in said if order(s) > order(marked.statement)]


def pending(diagram: Diagram, kind: Kind) -> tuple[list[Discussion], list[Discussion]]:
    """The sessions with a coach message still to go through, and the ones
    gone through to their end."""
    done = getattr(diagram.get_diagram_data(), kind.done)
    todo, finished = [], []
    for discussion in sessions(diagram):
        coach = discussion.chat_ai_speaker_id
        later = any(s.speaker_id == coach for s in unread(discussion, kind, done))
        (todo if later else finished).append(discussion)
    return todo, finished


READ = "Already gone through, for context only; act on none of it:"
NEW = "New since then; go through only these:"


def lines(discussion: Discussion, said: list[Statement], numbered: bool) -> str:
    out = []
    for statement in said:
        if not statement.text:
            continue
        if statement.speaker_id != discussion.chat_ai_speaker_id:
            out.append(f"[person] {statement.text}")
        elif numbered:
            out.append(f"[coach message {statement.id}] {statement.text}")
        else:
            out.append(f"[coach] {statement.text}")
    return "\n\n".join(out)


def transcript(discussion: Discussion, said: list[Statement]) -> str:
    """The statements as the backfill reads them, each coach message to go
    through numbered by its statement id. When only later statements are to
    be gone through, the earlier ones come first, marked as context."""
    new = lines(discussion, said, numbered=True)
    earlier = [s for s in sorted(discussion.statements, key=order) if s not in said]
    if not earlier:
        return new
    return f"{READ}\n\n{lines(discussion, earlier, numbered=False)}\n\n{NEW}\n\n{new}"


def backfill(diagram: Diagram, discussion: Discussion, model, kind: Kind) -> int:
    """Go through what one past session holds that was not gone through yet,
    then mark it gone through. Returns how many model calls it made."""
    done = getattr(diagram.get_diagram_data(), kind.done)
    said = unread(discussion, kind, done)
    last = max((s for s in said if s.speaker_id == discussion.chat_ai_speaker_id), key=order)
    turn_id = f"{kind.turn}:{discussion.id}"
    toolbox = Toolbox(
        diagram.id,
        turn_id,
        user_id=discussion.user_id,
        session_id=discussion.id,
        author=Author.Coach,
        statement_id=last.id,
    )
    metered = Metered(
        discussion.user_id, diagram.id, turn_id, Purpose.Backfill, model=model
    )
    system = kind.prompt(
        map=outline(toolbox.data, toolbox.diagram.version),
        transcript=transcript(discussion, said),
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
                "after": done if discussion.id in done else [*done, discussion.id],
            }
        ],
        author=Author.Coach,
        turn_id=turn_id,
        user_id=discussion.user_id,
        session_id=discussion.id,
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
