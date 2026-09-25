"""A coach turn runs in the worker, not in the request.

Five tool rounds and a naming call take longer than a request may sit open, so
the route stores the user's words, hands the turn to the worker and answers at
once. Everything the turn does goes into the turn's log as it happens, and the
page follows that log. A page that reloads reads the log from the start.
"""

import logging
import uuid

from btcopilot import extensions
from btcopilot.extensions import db
from btcopilot import chips, observer, turnlog, turnstore
from btcopilot.coachmodel import Refusal
from btcopilot.coachturn import CoachTurn, record_of
from btcopilot.discussions import session_payload
from btcopilot.models import Change, Discussion, Statement, StatementKind
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

TASK = "coach_turn"

BUSY = "the coach is still answering the last message"
BROKE = "The coach did not finish that turn."
REFUSED = (
    "I can't take that one up here. Say it another way, or tell me what "
    "happened next."
)


class Unfinished(Exception):
    """Only the last message of a session, left unanswered by a turn that
    failed, can be picked up again."""


class Busy(Exception):
    """A second message while the coach is still on the last one. Two turns on
    one session would write over each other's record."""


def start(discussion: Discussion, statement: str) -> dict:
    """Store what the user said, reserve the turn, and hand it over."""
    turn_id = uuid.uuid4().hex
    if not turnlog.start(discussion.id, turn_id):
        raise Busy(BUSY)
    said = Statement(
        discussion_id=discussion.id,
        text=chips.validate(statement, record_of(discussion)),
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
        kind=StatementKind.Turn,
        turn_id=turn_id,
    )
    db.session.add(said)
    db.session.commit()
    enqueue(turn_id, discussion.id, said.id)
    return {
        "turn_id": turn_id,
        "discussion_id": discussion.id,
        "statement_id": said.id,
    }


def resume(discussion: Discussion, turn_id: str) -> dict:
    """Pick a failed turn up where it stopped. Nothing new is stored: the same
    words, the same turn, and the tool calls it already made stay made."""
    said = Statement.query.filter_by(
        discussion_id=discussion.id,
        turn_id=turn_id,
        speaker_id=discussion.chat_user_speaker_id,
    ).one_or_none()
    last = max(discussion.statements, key=lambda s: (s.order or 0, s.id))
    if said is None or said.id != last.id:
        raise Unfinished(f"turn {turn_id} is not the last message of this session")
    if not turnstore.failed(turnstore.kept({turn_id}).get(turn_id, [])):
        raise Unfinished(f"turn {turn_id} did not fail")
    if not turnlog.start(discussion.id, turn_id):
        raise Busy(BUSY)
    turnlog.forget(turn_id)
    enqueue(turn_id, discussion.id, said.id, resume=True)
    return {"turn_id": turn_id, "discussion_id": discussion.id, "statement_id": said.id}


def enqueue(
    turn_id: str, discussion_id: int, statement_id: int, resume: bool = False
) -> None:
    extensions.celery.send_task(
        TASK, args=[turn_id, discussion_id, statement_id], kwargs={"resume": resume}
    )


def written(turn_id: str, discussion_id: int, event: dict) -> None:
    """Everything the turn does, written down and told at once. Each one also
    pushes out the session's hold, so a turn still working keeps it and a turn
    whose worker died lets go of it within minutes."""
    turnlog.append(turn_id, event)
    turnlog.keep(discussion_id)


def run(
    turn_id: str, discussion_id: int, statement_id: int, resume: bool = False
) -> dict:
    """The task itself. It ends in one of two events, always: the reply, or a
    sentence saying it did not finish."""
    _log.info(f"coach_turn {turn_id} discussion={discussion_id}")
    discussion = db.session.get(Discussion, discussion_id)
    said = db.session.get(Statement, statement_id)
    turn = CoachTurn(
        discussion,
        said.text,
        session_id=str(discussion_id),
        statement_id=statement_id,
        turn_id=turn_id,
        sink=lambda event: written(turn_id, discussion_id, event),
        resume=resume,
    )
    try:
        reply = turn.run()
    # A refusal is not a fault to retry: the same words would be declined
    # again. The page gets the coach's sentence and the category stays here.
    except Refusal as refused:
        db.session.rollback()
        _unanswered(turn, statement_id, {"type": TurnEventKind.Refused.value})
        turnlog.clear(discussion_id)
        _log.warning(f"coach_turn {turn_id} refused: {refused.category}")
        event = {"type": TurnEventKind.Refused.value, "message": REFUSED}
        turnlog.append(turn_id, event)
        return event
    # The one router in this file: whatever went wrong, the page is told the
    # turn ended, and the error goes on to be logged and retried as usual.
    except Exception:
        db.session.rollback()
        failed = {"type": TurnEventKind.Failed.value, "message": BROKE}
        _unanswered(turn, statement_id, failed)
        turnlog.clear(discussion_id)
        turnlog.append(turn_id, failed)
        raise
    _keep(
        turn, {"type": TurnEventKind.Done.value, "statement_id": reply["statement_id"]}
    )
    reply["kind"] = StatementKind.Turn.value
    reply["discussion_id"] = discussion_id
    turnlog.clear(discussion_id)
    reply["session"] = session_payload(discussion)
    turnlog.append(turn_id, dict(reply, type=TurnEventKind.Done.value))
    return reply


def _unanswered(turn: CoachTurn, statement_id: int, ending: dict) -> None:
    """A turn that ended without a reply keeps what it did: its edits are
    already in the record, so they are tied to the words that asked for them,
    and its tool calls are kept for the thread and for picking it up."""
    Change.query.filter_by(diagram_id=turn.diagram.id, turn_id=turn.turn_id).update(
        {"statement_id": statement_id}
    )
    _keep(turn, ending)


def _keep(turn: CoachTurn, ending: dict) -> None:
    turnstore.save(turn.turn_id, turn.discussion.id, turn.kept + [ending])
    observer.observe(turn.diagram.id, turn.turn_id, turn.data)
    db.session.commit()
