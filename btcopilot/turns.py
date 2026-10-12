"""A coach turn runs in the worker, not in the request.

Five tool rounds and a naming call take longer than a request may sit open, so
the route stores the user's words, hands the turn to the worker and answers at
once. Everything the turn does goes into the turn's log as it happens, and the
page follows that log. A page that reloads reads the log from the start.
"""

import dataclasses
import datetime
import json
import logging
import uuid

import btcopilot
from btcopilot import attachments, extensions
from btcopilot.extensions import db
from btcopilot import (
    chips,
    coverage,
    fdafter,
    fdimport,
    fdledger,
    fdnotice,
    observer,
    record,
    shadow,
    turnlog,
    turnstore,
)
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Refusal, model_for
from btcopilot.coachturn import CoachTurn, Stopped, record_of
from btcopilot.discussions import session_payload
from btcopilot.models import (
    Author,
    Change,
    Discussion,
    Observation,
    ObservationKind,
    Purpose,
    Statement,
    StatementKind,
    TokenMeter,
)
from btcopilot.metered import Metered
from btcopilot.models.preferences import PrefKey
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


class Idle(Exception):
    """A stop for a turn that is not running."""


def start(
    discussion: Discussion,
    statement: str,
    zone: str | None = None,
    attached: attachments.File | None = None,
) -> dict:
    """Store what the user said, reserve the turn, and hand it over, with the
    person's time zone so the coach's day is theirs. A text file's words are
    stored with the message; a PDF or a photo is left in Redis for the worker,
    which reads it before the coach's turn, so the statement goes in with its
    file's name and no text yet (R-0828, R-0829). A busy session holds nothing."""
    turn_id = uuid.uuid4().hex
    text = chips.validate(statement, record_of(discussion), discussion.diagram_id)
    if not turnlog.start(discussion.id, turn_id):
        raise Busy(BUSY)
    if attached and not attached.ready:
        try:
            attachments.hold(turn_id, attached.data)
        except Exception:
            turnlog.clear(discussion.id)
            raise
    said = Statement(
        discussion_id=discussion.id,
        text=text,
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
        kind=StatementKind.Turn,
        turn_id=turn_id,
        attachment_name=attached.name if attached else None,
        attachment_text=attached.text if attached and attached.ready else None,
    )
    db.session.add(said)
    db.session.commit()
    enqueue(turn_id, discussion.id, said.id, zone=zone)
    return {
        "turn_id": turn_id,
        "discussion_id": discussion.id,
        "statement_id": said.id,
        "attachment_name": said.attachment_name,
        "attachment_text": said.attachment_text,
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
    """Ask the running turn to end at its next model or tool call; the turn
    itself takes its edits back and says so in its last event (R-0636)."""
    if turnlog.running(discussion.id) != turn_id:
        raise Idle(f"turn {turn_id} is not running")
    turnlog.halt(turn_id)
    return {"turn_id": turn_id}


def enqueue(
    turn_id: str,
    discussion_id: int,
    statement_id: int,
    resume: bool = False,
    zone: str | None = None,
) -> None:
    extensions.celery.send_task(
        TASK,
        args=[turn_id, discussion_id, statement_id],
        kwargs={"resume": resume, "zone": zone},
    )


def written(turn_id: str, discussion_id: int, event: dict) -> None:
    """Everything the turn does, written down and told at once. Each one also
    pushes out the session's hold, so a turn still working keeps it and a turn
    whose worker died lets go of it within minutes."""
    turnlog.append(turn_id, event)
    turnlog.keep(discussion_id)


def run(
    turn_id: str,
    discussion_id: int,
    statement_id: int,
    resume: bool = False,
    zone: str | None = None,
) -> dict:
    """The task itself. It ends in one of two events, always: the reply, or a
    sentence saying it did not finish. A resumed turn carries no zone, so its
    day is in the zone kept on the person's row. A message whose file is not
    yet read has it read first, here on the worker; the coach never starts
    without the text (R-0829)."""
    _log.info(f"coach_turn {turn_id} discussion={discussion_id}")
    discussion = db.session.get(Discussion, discussion_id)
    said = db.session.get(Statement, statement_id)
    if said.attachment_name is not None and said.attachment_text is None:
        if attachments.kind(said.attachment_name) is attachments.Kind.Fd:
            return _import(turn_id, discussion, said)
        failed = _read(turn_id, discussion, said)
        if failed is not None:
            return failed
    # a resumed turn's record already holds its first attempt's edits, so it
    # has no clean copy to run a shadow on
    on = not resume and shadow.expiry(discussion.user, said.created_at, statement_id)
    shadows = discussion.user.pref(PrefKey.ShadowModels) if on else ()
    before = discussion.diagram.data
    covered = coverage.counts(record_of(discussion))
    turn = CoachTurn(
        discussion,
        said.spoken,
        purpose=Purpose.Coach,
        model=model_for(setting.read(SettingKey.CoachModel, discussion.user_id)),
        statement_id=statement_id,
        turn_id=turn_id,
        sink=lambda event: written(turn_id, discussion_id, event),
        resume=resume,
        zone=zone,
    )
    try:
        if turnlog.halted(turn_id):
            raise Stopped(f"turn {turn_id} was stopped while its file was read")
        reply = turn.run()
    except Stopped:
        db.session.rollback()
        return _stopped(discussion, turn_id, statement_id, turn.kept)
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


def _held(turn_id: str, discussion_id: int) -> None:
    """Before each part of a file: a stopped turn reads no further part."""
    if turnlog.halted(turn_id):
        raise Stopped(f"turn {turn_id} was stopped while its file was read")
    turnlog.keep(discussion_id)


def _read(turn_id: str, discussion: Discussion, said: Statement) -> dict | None:
    """The file left for this turn, read into the statement's text with the
    same calls, ledger rows and charge as the request once made, holding the
    session through every part. A read that fails ends the turn here, before
    the coach: nothing is kept as text, the thread is told why in the same
    words a refused read always had, and the session takes the next message.
    The file stays held for the hour, so trying the turn again reads it again.
    None when the text is in or the person stopped the turn, which the coach
    then ends as stopped; else the event that ended the turn. A read the
    model declined, cut off, or could not find is its own ending; anything
    else goes on to be logged like a turn that broke."""
    try:
        said.attachment_text = attachments.read_held(
            turn_id,
            said.attachment_name,
            discussion.user_id,
            discussion.diagram_id,
            keep=lambda: _held(turn_id, discussion.id),
        )
    except Stopped:
        # the parts already read are charged; the coach ends it as stopped
        return None
    except Exception as error:
        # no rollback: the parts already read are charged whatever came after
        own = attachments.why(error)
        failed = _untaken(turn_id, discussion, error, own or attachments.REFUSED)
        if own is None:
            raise
        return failed
    db.session.commit()
    attachments.drop(turn_id)
    return None


def _untaken(
    turn_id: str, discussion: Discussion, error: Exception, message: str
) -> dict:
    """A file the turn could not take ends it before the coach: the thread is
    told why, the session takes the next message, and the file stays held for
    the hour, so trying the turn again takes it again."""
    _log.warning(f"coach_turn {turn_id} could not take its file: {error}")
    db.session.add(
        Observation(
            diagram_id=discussion.diagram_id,
            turn_id=turn_id,
            kind=ObservationKind.TurnFailed,
            detail={
                "error": f"{type(error).__name__}: {error}",
                "reason": type(error).__name__,
            },
        )
    )
    failed = {"type": TurnEventKind.Failed.value, "message": message}
    turnstore.save(turn_id, discussion.id, [failed])
    db.session.commit()
    turnlog.clear(discussion.id)
    turnlog.append(turn_id, failed)
    return failed


def _import(turn_id: str, discussion: Discussion, said: Statement) -> dict:
    """A desktop file attached in the chat, brought into the chat's diagram
    [Oracle: R-0880]. Its model calls are charged to the person like the
    coach's own, however the import ends. One the person stopped writes
    nothing; one the import cannot write ends the turn saying why, the file
    kept for the hour to try again."""
    model = fdimport.meter(discussion.user_id, discussion.diagram, turn_id)
    try:
        return _brought(turn_id, discussion, said, model)
    except Stopped:
        db.session.rollback()
        TokenMeter.charge(discussion.user_id, model.spent)
        return _stopped(discussion, turn_id, said.id)
    except attachments.Gone as gone:
        return _refused(turn_id, discussion, model, gone, str(gone))
    except record.Invalid as invalid:
        said_why = f"{attachments.NOT_BROUGHT} {invalid.plain}"
        return _refused(turn_id, discussion, model, invalid, said_why)
    except ValueError as error:
        return _refused(turn_id, discussion, model, error, attachments.NOT_BROUGHT)
    # The import's router: whatever else went wrong, the page is told the turn
    # ended, and the error goes on to be logged and retried as usual.
    except Exception as error:
        _refused(turn_id, discussion, model, error, attachments.NOT_BROUGHT)
        raise


def _refused(
    turn_id: str,
    discussion: Discussion,
    model: Metered,
    error: Exception,
    message: str,
) -> dict:
    db.session.rollback()
    TokenMeter.charge(discussion.user_id, model.spent)
    return _untaken(turn_id, discussion, error, message)


def _brought(
    turn_id: str, discussion: Discussion, said: Statement, model: Metered
) -> dict:
    """The import as every import runs, written once: trying the turn again
    after the import's change-log turn is in runs only the steps after the
    write that did not finish [Oracle: R-0880]."""
    diagram = discussion.diagram
    if not Change.query.filter_by(diagram_id=diagram.id, turn_id=model.turn_id).first():
        _written(turn_id, discussion, said, model)
    held = attachments.held(_landing(turn_id))
    if held is None:
        raise attachments.Gone(attachments.GONE)
    landing = json.loads(held)
    done = {fdafter.Step(step) for step in landing["done"]}
    try:
        sent = fdafter.land(
            diagram.id,
            discussion.user_id,
            fdnotice.Summary(**landing["summary"]),
            landing["mail"],
            done,
        )
    finally:
        landing["done"] = sorted(done)
        attachments.hold(_landing(turn_id), json.dumps(landing).encode())
    # what the chip on the message shows the file became
    said.attachment_text = sent.question
    TokenMeter.charge(discussion.user_id, model.spent)
    turnstore.save(turn_id, discussion.id, [turnstore.done(sent.statement.id)])
    db.session.commit()
    attachments.drop(turn_id)
    attachments.drop(_landing(turn_id))
    turnlog.clear(discussion.id)
    reply = {
        "statement": sent.question,
        "statement_id": sent.statement.id,
        "views": [],
        "events": [],
        "turn_id": turn_id,
        "kind": StatementKind.Turn.value,
        "discussion_id": discussion.id,
        "session": session_payload(discussion),
        "imported": True,
    }
    turnlog.append(turn_id, dict(reply, type=TurnEventKind.Done.value))
    return reply


def _landing(turn_id: str) -> str:
    """Where what the steps after the write need waits beside the file."""
    return f"{turn_id}:landing"


def _written(
    turn_id: str, discussion: Discussion, said: Statement, model: Metered
) -> None:
    """The file brought into the diagram as one change-log turn, what the steps
    after it need left beside the file first. Each model call holds the session
    and stops at the person's stop."""
    user = discussion.user
    diagram = discussion.diagram

    def heard(*args):
        _held(turn_id, discussion.id)
        return model.structured(*args)

    data = attachments.held(turn_id)
    if data is None:
        raise attachments.Gone(attachments.GONE)
    fd = attachments.File(said.attachment_name, data).fd
    out = fdimport.build(fd, heard, into=diagram)
    summary = fdnotice.Summary(
        model.turn_id, **out.brought, primaries=tuple(out.primaries)
    )
    ledger = fdledger.text(
        said.attachment_name,
        fd,
        fdimport.became(out),
        out.decisions,
        datetime.date.today(),
    )
    landing = {
        "summary": dataclasses.asdict(summary),
        "mail": {
            "email": user.username,
            "file": said.attachment_name,
            "name": diagram.name,
            "ledger": ledger,
        },
        "done": [],
    }
    attachments.hold(_landing(turn_id), json.dumps(landing).encode())
    fdimport.save(user.id, diagram.name, out, yes=True, turn=model.turn_id)


def _stopped(
    discussion: Discussion, turn_id: str, statement_id: int, done: list[dict] = ()
) -> dict:
    """A turn the person stopped: no reply is kept and its edits are taken back
    as one, so the record is as it was before the words were sent; edits that
    were changed since stay with the tool calls `done` that made them, and the
    last event says why (R-0636)."""
    diagram = discussion.diagram
    ending = dict(
        turnstore.done(statement_id, release=btcopilot.__version__), stopped=True
    )
    kept = []
    if Change.query.filter_by(diagram_id=diagram.id, turn_id=turn_id).first():
        try:
            record.undo(
                diagram.id,
                turn_id,
                author=Author.Coach,
                user_id=discussion.user_id,
                session_id=discussion.id,
            )
        except (record.Conflict, record.Invalid) as conflict:
            _log.warning(f"coach_turn {turn_id} stopped, edits kept: {conflict}")
            ending["conflict"] = str(conflict)
            kept = list(done)
    db.session.refresh(diagram)
    ending["version"] = diagram.version
    Change.query.filter(
        Change.diagram_id == diagram.id,
        Change.turn_id.in_([turn_id, f"undo:{turn_id}"]),
    ).update({"statement_id": statement_id})
    turnstore.save(turn_id, discussion.id, kept + [ending])
    db.session.commit()
    turnlog.clear(discussion.id)
    event = dict(
        ending,
        statement=None,
        views=[],
        events=[],
        turn_id=turn_id,
        kind=StatementKind.Turn.value,
        discussion_id=discussion.id,
        session=session_payload(discussion),
    )
    turnlog.append(turn_id, event)
    return event


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
