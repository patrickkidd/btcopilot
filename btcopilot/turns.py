"""A coach turn runs in the worker, not in the request.

Five tool rounds and a naming call take longer than a request may sit open, so
the route stores the user's words, hands the turn to the worker and answers at
once. Everything the turn does goes into the turn's log as it happens, and the
page follows that log. A page that reloads reads the log from the start.
"""

import logging
import re
import uuid

import btcopilot
from btcopilot import extensions
from btcopilot.extensions import db
from btcopilot import chips, coverage, observer, shadow, turnlog, turnstore
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Refusal, model_for
from btcopilot.coachturn import CoachTurn, record_of
from btcopilot.discussions import session_payload
from btcopilot.models import (
    Change,
    Discussion,
    Observation,
    ObservationKind,
    Purpose,
    Statement,
    StatementKind,
)
from btcopilot.models.preferences import PrefKey
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

# A chip the stop cut off before its closing brackets.
CUT = re.compile(r"\[\[[^\]]*$")

# What the thread never shows again: the words are the reply itself, and the
# record's own edits are in the change log.
UNKEPT = (
    TurnEventKind.Text.value,
    TurnEventKind.TextReset.value,
    TurnEventKind.RecordPatch.value,
)

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


class Idle(Exception):
    """A stop for a turn that is not running."""


def start(discussion: Discussion, statement: str) -> dict:
    """Store what the user said, reserve the turn, and hand it over."""
    turn_id = uuid.uuid4().hex
    if not turnlog.start(discussion.id, turn_id):
        raise Busy(BUSY)
    said = Statement(
        discussion_id=discussion.id,
        text=chips.validate(statement, record_of(discussion), discussion.diagram_id),
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


def stop(discussion: Discussion, turn_id: str) -> dict:
    """End a running turn at the person's word. Its worker is killed where it
    stands; the words it had typed out so far are kept as its reply, and with
    none it ends as a turn that did not finish. Its edits stay made either way."""
    if turnlog.running(discussion.id) != turn_id:
        raise Idle(f"turn {turn_id} is not running")
    kill(turn_id)
    live = [event for _, event in turnlog.read_from(turn_id, 0)]
    text = ""
    for event in live:
        if event["type"] == TurnEventKind.Text.value:
            text += event["text"]
        elif event["type"] == TurnEventKind.TextReset.value:
            text = ""
    text = chips.validate(
        CUT.sub("", text).strip(), record_of(discussion), discussion.diagram_id
    )
    said = Statement.query.filter_by(
        discussion_id=discussion.id,
        turn_id=turn_id,
        speaker_id=discussion.chat_user_speaker_id,
    ).one()
    reply = said
    if text:
        reply = Statement(
            discussion_id=discussion.id,
            text=text,
            speaker=discussion.chat_ai_speaker,
            order=discussion.next_order(),
            kind=StatementKind.Turn,
            turn_id=turn_id,
        )
        db.session.add(reply)
        db.session.flush()
    Change.query.filter_by(diagram_id=discussion.diagram_id, turn_id=turn_id).update(
        {"statement_id": reply.id}
    )
    # a resumed turn sent the calls it had already kept again, first
    prior = turnstore.kept({turn_id}).get(turn_id, [])
    again = sum(e["type"] == TurnEventKind.ToolCall.value for e in prior)
    shown = [e for e in live if e["type"] not in UNKEPT][again:]
    ending = (
        dict(turnstore.done(reply.id, release=btcopilot.__version__), stopped=True)
        if text
        else {"type": TurnEventKind.Failed.value, "message": BROKE}
    )
    turnstore.save(turn_id, discussion.id, shown + [ending])
    db.session.commit()
    turnlog.clear(discussion.id)
    if text:
        ending.update(
            statement=text,
            views=[],
            events=[],
            turn_id=turn_id,
            kind=StatementKind.Turn.value,
            discussion_id=discussion.id,
            session=session_payload(discussion),
        )
    turnlog.append(turn_id, ending)
    return {"turn_id": turn_id, "statement_id": reply.id}


def kill(turn_id: str) -> None:
    """Revoke the worker's task for this turn, waiting for the worker to say it
    has been signalled, so nothing it writes after lands behind the stop."""
    inspect = extensions.celery.control.inspect()
    for found in (inspect.active() or {}, inspect.reserved() or {}):
        for task in (t for tasks in found.values() for t in tasks):
            if task["name"] == TASK and task["args"][0] == turn_id:
                extensions.celery.control.revoke(task["id"], terminate=True, reply=True)


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
    # a resumed turn's record already holds its first attempt's edits, so it
    # has no clean copy to run a shadow on
    on = not resume and shadow.expiry(discussion.user, said.created_at, statement_id)
    shadows = discussion.user.pref(PrefKey.ShadowModels) if on else ()
    before = discussion.diagram.data
    covered = coverage.counts(record_of(discussion))
    turn = CoachTurn(
        discussion,
        said.text,
        purpose=Purpose.Coach,
        model=model_for(setting.read(SettingKey.CoachModel, discussion.user_id)),
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
        _ended(
            turn,
            ObservationKind.TurnDeclined,
            {"category": refused.category, "reason": str(refused.category)},
        )
        _unanswered(turn, statement_id, {"type": TurnEventKind.Refused.value})
        turnlog.clear(discussion_id)
        _log.warning(f"coach_turn {turn_id} refused: {refused.category}")
        event = {"type": TurnEventKind.Refused.value, "message": REFUSED}
        turnlog.append(turn_id, event)
        return event
    # The one router in this file: whatever went wrong, the page is told the
    # turn ended, and the error goes on to be logged and retried as usual.
    except Exception as error:
        db.session.rollback()
        # the message can quote the record, so only the error's kind groups it
        _ended(
            turn,
            ObservationKind.TurnFailed,
            {
                "error": f"{type(error).__name__}: {error}",
                "reason": type(error).__name__,
            },
        )
        failed = {"type": TurnEventKind.Failed.value, "message": BROKE}
        _unanswered(turn, statement_id, failed)
        turnlog.clear(discussion_id)
        turnlog.append(turn_id, failed)
        raise
    _keep(
        turn,
        turnstore.done(
            reply["statement_id"],
            {"before": covered, "after": coverage.counts(turn.data)},
            btcopilot.__version__,
        ),
    )
    reply["kind"] = StatementKind.Turn.value
    reply["discussion_id"] = discussion_id
    turnlog.clear(discussion_id)
    reply["session"] = session_payload(discussion)
    turnlog.append(turn_id, dict(reply, type=TurnEventKind.Done.value))
    for model in shadows:
        shadow.start(turn, statement_id, model, before)
    return reply


def _unanswered(turn: CoachTurn, statement_id: int, ending: dict) -> None:
    """A turn that ended without a reply keeps what it did: its edits are
    already in the record, so they are tied to the words that asked for them,
    and its tool calls are kept for the thread and for picking it up."""
    Change.query.filter_by(diagram_id=turn.diagram.id, turn_id=turn.turn_id).update(
        {"statement_id": statement_id}
    )
    _keep(turn, ending)


def _ended(turn: CoachTurn, kind: ObservationKind, detail: dict) -> None:
    """How a turn that gave no reply ended, kept for the tuning queue; written
    before the turn's events and kept with them."""
    db.session.add(
        Observation(
            diagram_id=turn.diagram.id, turn_id=turn.turn_id, kind=kind, detail=detail
        )
    )


def _keep(turn: CoachTurn, ending: dict) -> None:
    turnstore.save(turn.turn_id, turn.discussion.id, turn.kept + [ending])
    observer.observe(turn.diagram.id, turn.turn_id, turn.data)
    db.session.commit()
