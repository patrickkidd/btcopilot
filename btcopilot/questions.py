"""The questions the coach keeps in the record: what the page may show of them,
and the one pass back over past sessions that fills them in (R-0006)."""

import logging

from btcopilot import prompts, record
from btcopilot.coachmodel import CoachModel
from btcopilot.coachturn import MAX_STEPS, Metered, drain, run_call
from btcopilot.models import Author, Diagram, Discussion, Statement
from btcopilot.recordtext import outline
from btcopilot.schema import DiagramData, ItemKind, QuestionState
from btcopilot.toolbox import READS, ToolName, Toolbox, schemas

_log = logging.getLogger(__name__)

# The coach's reads, so it can see what the record already answers, and the
# question writes; nothing else in the record can be changed from here.
TOOLS = (*READS, ToolName.AddQuestion, ToolName.SetQuestion)
START = "Go through the session."
# About one call to read, one round of adds, and sometimes one more.
CALLS_PER_SESSION = 3


def asked(diagram_id: int, data: DiagramData) -> list[dict]:
    """Every question that was ever asked, for the page. A question the coach
    only keeps for later never leaves the server."""
    where = record.asked_in(diagram_id)
    return [
        {
            "id": q["id"],
            "text": q["text"],
            "kind": q["kind"],
            "open": q["state"] == QuestionState.Asked,
            "asked_at": q["asked_at"],
            "asked_in": where.get(q["id"]),
        }
        for q in data.questions
        if q["asked_at"] is not None
    ]


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


def pending(diagram: Diagram) -> tuple[list[Discussion], list[Discussion]]:
    """The sessions still to go through, and the ones already gone through."""
    done = set(diagram.get_diagram_data().questions_backfilled)
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


def backfill(diagram: Diagram, discussion: Discussion, model) -> int:
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
    turn_id = f"backfill:{discussion.id}"
    toolbox = Toolbox(
        diagram.id,
        turn_id,
        user_id=discussion.user_id,
        session_id=str(discussion.id),
        author=Author.Coach,
        statement_id=last.id,
    )
    metered = Metered(model, discussion.user_id, diagram.id, turn_id)
    system = prompts.question_backfill(
        map=outline(toolbox.data, toolbox.diagram.version),
        transcript=transcript(discussion),
    )
    tools = [schema for schema in schemas() if schema["name"] in TOOLS]
    messages = [{"role": "user", "content": START}]
    calls = 0
    for _ in range(MAX_STEPS):
        turn = drain(metered.turn(system, messages, tools, turn_id))
        calls += 1
        if not turn.calls:
            break
        results = []
        for call in turn.calls:
            if call.name in TOOLS:
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
                "field": "questions_backfilled",
                "after": [*toolbox.data.questions_backfilled, discussion.id],
            }
        ],
        author=Author.Coach,
        turn_id=turn_id,
        user_id=discussion.user_id,
        session_id=str(discussion.id),
        statement_id=last.id,
    )
    return calls


def run(diagrams: list[Diagram], model=None) -> list[dict]:
    """Every session of these families not yet gone through, oldest first."""
    model = model or CoachModel()
    done = []
    for diagram in diagrams:
        todo, _ = pending(diagram)
        for discussion in todo:
            calls = backfill(diagram, discussion, model)
            done.append({"diagram": diagram.id, "session": discussion.id, "model_calls": calls})
    return done
