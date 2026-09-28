"""A real turn run again on a second model, for comparison only [R-0596].

The shadow gets the same words, the chat as it stood and a copy of the record
as the real turn found it. It writes onto a scratch record that is thrown away
when it ends; what it said, the tools it called and what it spent are kept on
the real turn's row. The user never sees it and is never charged for it.
"""

import logging
import time

from sqlalchemy import func

from btcopilot import diagramjson, extensions
from btcopilot.coachmodel import model_for
from btcopilot.coachturn import RECENT_INTERACTIONS, CoachTurn
from btcopilot.extensions import db
from btcopilot.models import (
    AccessRight,
    Change,
    Diagram,
    Discussion,
    Interaction,
    ModelCall,
    Observation,
    ProductEvent,
    ShadowTurn,
    Speaker,
    Statement,
)
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

TASK = "coach_shadow"
QUEUE = "shadow"

# What a scratch record leaves behind, all thrown away with it. The model calls
# are not: they move to the real record so the spend stays visible.
SCRATCH_ROWS = (AccessRight, Change, Interaction, Observation, ProductEvent)


def start(turn: CoachTurn, statement_id: int, model: str, before: bytes | None):
    """Keep the record as the real turn found it and hand the shadow over."""
    db.session.add(
        ShadowTurn(
            turn_id=turn.turn_id,
            user_id=turn.discussion.user_id,
            diagram_id=turn.diagram.id,
            discussion_id=turn.discussion.id,
            statement_id=statement_id,
            model=model,
            snapshot=diagramjson.store(before).decode("utf-8"),
        )
    )
    db.session.commit()
    enqueue(turn.turn_id)


def enqueue(turn_id: str) -> None:
    extensions.celery.send_task(TASK, args=[turn_id])


def run(turn_id: str) -> None:
    row = ShadowTurn.query.filter_by(turn_id=turn_id).one()
    said = db.session.get(Statement, row.statement_id)
    diagram = Diagram(
        user_id=row.user_id,
        name=f"shadow {turn_id}",
        data=row.snapshot.encode("utf-8"),
        scratch=True,
    )
    db.session.add(diagram)
    db.session.flush()
    copy = _copy(said, diagram)
    _interactions(row, diagram)
    db.session.commit()
    shadow_id = f"shadow-{turn_id}"
    started = time.monotonic()
    try:
        turn = CoachTurn(
            copy,
            said.text,
            model=model_for(row.model),
            turn_id=shadow_id,
            scratch=True,
        )
        row.text = turn.run()["statement"]
        row.tool_calls = [
            {"name": e["name"], "args": e["args"], "refusal": e["refusal"]}
            for e in turn.kept
            if e["type"] == TurnEventKind.ToolCall.value
        ]
        spent = turn.model.spent
        row.input_tokens = spent.input
        row.output_tokens = spent.output
        row.cache_creation_tokens = spent.cache_creation
        row.cache_read_tokens = spent.cache_read
    # Stored on the row so the comparison shows the shadow broke, then raised.
    except Exception as error:
        db.session.rollback()
        row.error = f"{type(error).__name__}: {error}"
        raise
    finally:
        row.duration_ms = round((time.monotonic() - started) * 1000)
        ModelCall.query.filter_by(diagram_id=diagram.id).update(
            {"diagram_id": row.diagram_id}
        )
        row.cost_usd = (
            db.session.query(func.sum(ModelCall.cost_usd))
            .filter_by(turn_id=shadow_id)
            .scalar()
        )
        _drop(diagram, copy)
        row.snapshot = None
        db.session.commit()
        _log.info(f"coach_shadow {turn_id} on {row.model}: {row.cost_usd} USD")


def _copy(said: Statement, diagram: Diagram) -> Discussion:
    """The session as it stood before the user's words, on the scratch record.
    The title is copied so the scratch turn does not name the session again."""
    real = said.discussion
    copy = Discussion(
        user_id=real.user_id,
        diagram_id=diagram.id,
        title=real.title,
        title_set_by_user=True,
        kind=real.kind,
        discussion_date=real.discussion_date,
    )
    speakers = {
        s.id: Speaker(name=s.name, type=s.type, person_id=s.person_id)
        for s in real.speakers
    }
    copy.speakers = list(speakers.values())
    db.session.add(copy)
    db.session.flush()
    copy.chat_user_speaker_id = speakers[real.chat_user_speaker_id].id
    copy.chat_ai_speaker_id = speakers[real.chat_ai_speaker_id].id
    for s in real.statements:
        if s.order < said.order:
            db.session.add(
                Statement(
                    discussion_id=copy.id,
                    text=s.text,
                    speaker_id=speakers[s.speaker_id].id,
                    order=s.order,
                    kind=s.kind,
                    turn_id=s.turn_id,
                )
            )
    db.session.flush()
    db.session.refresh(copy)
    return copy


def _interactions(row: ShadowTurn, diagram: Diagram) -> None:
    """What the user had been looking at when the real turn ran, so the scratch
    turn's prompt carries the same block."""
    for seen in (
        Interaction.query.filter(
            Interaction.diagram_id == row.diagram_id,
            Interaction.created_at <= row.created_at,
        )
        .order_by(Interaction.id.desc())
        .limit(RECENT_INTERACTIONS)
    ):
        db.session.add(
            Interaction(
                diagram_id=diagram.id,
                user_id=seen.user_id,
                session_id=seen.session_id,
                kind=seen.kind,
                item_kind=seen.item_kind,
                item_id=seen.item_id,
                created_at=seen.created_at,
            )
        )


def _drop(diagram: Diagram, copy: Discussion) -> None:
    for rows in SCRATCH_ROWS:
        rows.query.filter_by(diagram_id=diagram.id).delete()
    # the session and its speakers point at each other
    copy.chat_user_speaker_id = None
    copy.chat_ai_speaker_id = None
    db.session.flush()
    db.session.delete(copy)
    db.session.delete(diagram)
