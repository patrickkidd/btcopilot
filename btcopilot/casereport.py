"""The case report against the diagram as it stands: whether something has
changed since the coach wrote its cards (R-0827), and the rewrite of every card
the coach writes at once, from the diagram, in one coach turn (R-0825).

Out of date is a rule on the command log, no model: after the newest card
was written, an event a card rests on changed its date or kind, or a death, a
marriage, a separation, a divorce or a shift with a symptom was added. The
rewrite runs in the worker like a coach turn and ends in a done or failed
event on the turn log; the page polls its state.
"""

import enum
import logging
import time
import uuid

from btcopilot import clock, coverage, extensions, profile, record, turnlog
from btcopilot.admin import setting
from btcopilot.admin.casereport import closed
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Refusal, model_for
from btcopilot.coachturn import drain, run_call
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Observation,
    ObservationKind,
    Purpose,
    TokenMeter,
    User,
)
from btcopilot.prompts import get_agent_prompt
from btcopilot.questions import sessions
from btcopilot.recordtext import outline
from btcopilot.schema import (
    CaseReportCard,
    DiagramData,
    EventKind,
    EvidenceKind,
    ItemKind,
    QuestionState,
    enum_val,
    parse_date,
)
from btcopilot.toolbox import LOOKUPS, ToolName, Toolbox, schemas
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

TASK = "case_report_rewrite"
CARD = record.CARD
# What a later added event must be to put the report out of date.
MARKED = {EventKind.Death: "death", EventKind.Married: "marriage",
          EventKind.Separated: "separation", EventKind.Divorced: "divorce"}
MOVED = ("dateTime", "kind")
SINCE = "after the coach wrote this report."
FIELDS = ("text", "evidence", "state", CARD)
# Model calls in one rewrite: its reads, then five cards a few guesses a call.
STEPS = 8
# The longest a rewrite may run, in seconds: past it, it ends failed before
# its next model call, so the page never waits on it for good.
LIMIT = 300
START = (
    "This is not a chat; nobody reads your words. Write the person's case "
    "report again from the diagram as it stands now: every card you write, all "
    "at once, by the same rules you follow in a chat. Read what you need "
    "first; the map gives no event's words. Then give each card its "
    "guesses with add_impression, in state raised, with its case_report_card "
    "and the events it rests on: main_guess, coach_guess, own_part, choice and "
    "work_on. What you write replaces what is on that card now. Write all "
    "five; leave a card out only when nothing on the diagram could rest under "
    "it, and ask nothing: there is no one to answer. When every card is "
    "written, stop calling tools."
)
BROKE = "The case report could not be written again just now."
REFUSED = "The case report could not be written again from this diagram."


class State(enum.StrEnum):
    Running = "running"
    Done = "done"
    Failed = "failed"


class Overdue(Exception):
    """A rewrite past its time limit."""


class Busy(Exception):
    """A second rewrite of one family's report while the first is running."""


class Sessionless(Exception):
    """A family with no session has no case report to write again."""


def _carded(delta: dict) -> bool:
    """A delta that put an entry on a case report card."""
    if delta["item_kind"] != ItemKind.Question.value:
        return False
    if delta["field"] == CARD:
        return delta["after"] is not None
    whole = delta["field"] is None and delta.get("before") is None and delta["after"]
    return bool(whole and whole.get(CARD))


def _name(people: dict, pid) -> str | None:
    found = people.get(str(pid)) if pid is not None else None
    return found.get("name") if found else None


def _label(event: dict, people: dict) -> str:
    """The event as the person would name it, with its year."""
    kind = EventKind(enum_val(event.get("kind")) or EventKind.Shift.value)
    who = _name(people, event.get("child") if kind in (EventKind.Birth, EventKind.Adopted) else event.get("person"))
    if kind in MARKED or kind is EventKind.Bonded:
        partner = _name(people, event.get("spouse"))
        what = MARKED.get(kind, "getting together")
        label = f"{who} and {partner}'s {what}" if who and partner else f"{who}'s {what}" if who else f"a {what}"
    elif kind in (EventKind.Birth, EventKind.Adopted):
        label = f"{who}'s {kind.value}" if who else f"a {kind.value}"
    else:
        title = event.get("title") or event.get("description") or kind.value
        label = f"{who}'s “{title}”" if who else f"“{title}”"
    when = parse_date(event.get("dateTime"))
    return f"{label} in {when.year}" if when else label


def _why(delta: dict, cited: set[str], events: dict, people: dict) -> str | None:
    """The sentence a delta puts the report out of date with, or None."""
    if delta["item_kind"] != ItemKind.Event.value:
        return None
    eid = str(delta["item_id"])
    if delta["field"] is None and delta.get("before") is None and delta["after"]:
        added = delta["after"]
        kind = enum_val(added.get("kind"))
        if kind in {k.value for k in MARKED} or (kind == EventKind.Shift.value and added.get("symptom")):
            label = _label(events.get(eid, added), people)
            return f"{label[0].upper()}{label[1:]} was added {SINCE}"
        return None
    if delta["field"] in MOVED and eid in cited and delta.get("before") != delta["after"]:
        label = _label(events[eid], people) if eid in events else "an event the report rests on"
        if delta["field"] == "dateTime":
            return f"The date of {label} changed {SINCE}"
        return f"What kind of event {label} is changed {SINCE}"
    return None


def stale(diagram_id: int, data: DiagramData) -> dict | None:
    """The newest change since the coach last wrote a card that puts the case
    report out of date, or None: its change row id, when, and one sentence
    naming it. A change taken back, and the undo itself, count for nothing."""
    taken = record.undone(diagram_id)
    rows = [
        c
        for c in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id)
        if c.id not in taken and not c.turn_id.startswith("undo:")
    ]
    written = [i for i, c in enumerate(rows) if any(_carded(d) for d in c.deltas)]
    if not written:
        return None
    cited = {
        str(one["id"])
        for q in data.questions
        if q.get(CARD)
        for one in q.get("evidence") or []
        if one["kind"] == EvidenceKind.Event.value
    }
    events = {str(e["id"]): e for e in data.events}
    people = {str(p["id"]): p for p in data.people}
    for change in reversed(rows[written[-1] + 1 :]):
        for delta in reversed(change.deltas):
            said = _why(delta, cited, events, people)
            if said:
                return {"change_id": change.id, "at": change.created_at.isoformat(), "sentence": said}
    return None


def start(diagram: Diagram, user: User) -> dict:
    """Hold the family's report for one rewrite and hand it to the worker."""
    if not sessions(diagram):
        raise Sessionless("the family has no session, so no case report to write again")
    turn_id = uuid.uuid4().hex
    if not turnlog.claim(diagram.id, turn_id):
        raise Busy("the case report is already being written again")
    enqueue(turn_id, diagram.id, user.id)
    return {"id": turn_id, "state": State.Running.value}


def state(turn_id: str, diagram_id: int) -> State:
    """Running while the family's report is held for it; done or failed by its
    last event; failed when the hold ran out with no last event, as when the
    worker died."""
    ended = [e for _, e in turnlog.read_from(turn_id, 0) if turnlog.ended(e)]
    if ended:
        return State.Done if ended[-1]["type"] == TurnEventKind.Done.value else State.Failed
    return State.Running if turnlog.rewriting(diagram_id) == turn_id else State.Failed


def enqueue(turn_id: str, diagram_id: int, user_id: int) -> None:
    extensions.celery.send_task(TASK, args=[turn_id, diagram_id, user_id])


def offered() -> list[dict]:
    """The coach's reads as they are, and add_impression with only the fields
    a card's guess gives."""
    reads = {name.value for name in LOOKUPS}
    out = [s for s in schemas() if s["name"] in reads]
    (schema,) = [s for s in schemas() if s["name"] == ToolName.AddImpression.value]
    given = schema["input_schema"]
    return out + [
        {
            **schema,
            "input_schema": {
                "type": "object",
                "properties": {k: v for k, v in given["properties"].items() if k in FIELDS},
                "required": [*given["required"], CARD],
            },
        }
    ]


def checked(call) -> str | None:
    """Why the rewrite may not make a call, or None."""
    if call.name in {name.value for name in LOOKUPS}:
        return None
    if call.name != ToolName.AddImpression.value:
        return f"{call.name} is not part of a case report rewrite"
    extra = sorted(set(call.args) - set(FIELDS))
    if extra:
        return f"add_impression may not give {', '.join(extra)} here"
    if call.args.get("state") != QuestionState.Raised.value:
        return "a guess on the case report is raised"
    if call.args.get(CARD) not in {c.value for c in CaseReportCard}:
        return f"no case report card {call.args.get(CARD)!r}"
    return None


def rewrite(diagram: Diagram, meter: Metered, user: User, turn_id: str) -> list[str]:
    """The coach writes every card again, a guess at a time through its own
    tool, told what each call did, until it stops calling; what was on a card
    it wrote comes off. The cards written, in order."""
    data = diagram.get_diagram_data()
    own = profile.own(data)
    system = get_agent_prompt(
        record=outline(data, diagram.version, own and own["id"]) + closed(data),
        today=clock.today(user.timezone).isoformat(),
        coverage=coverage.block(data),
    )
    toolbox = Toolbox(
        diagram.id,
        turn_id,
        user_id=user.id,
        session_id=sessions(diagram)[-1].id,
        author=Author.Coach,
        zone=user.timezone,
    )
    before = {q["id"] for q in data.questions}
    messages = [{"role": "user", "content": START}]
    began = time.monotonic()
    for _ in range(STEPS):
        if time.monotonic() - began > LIMIT:
            raise Overdue(f"case report rewrite {turn_id} ran past {LIMIT} seconds")
        turnlog.hold(diagram.id)
        turn = drain(meter.turn(system, messages, offered(), turn_id))
        if not turn.calls:
            break
        results = []
        for call in turn.calls:
            refusal = checked(call)
            text = f"That did not work: {refusal}"
            if refusal is None:
                text, _, refusal = run_call(toolbox, call)
            if refusal:
                _observe(diagram.id, turn_id, ObservationKind.ToolRefused,
                         {"tool": call.name, "refusal": refusal, "retried": False,
                          "reason": f"case report rewrite: {call.name}: {refusal}"})
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": text,
                            "is_error": refusal is not None})
        messages += [{"role": "assistant", "content": turn.blocks}, {"role": "user", "content": results}]
    after = toolbox.data.questions
    new = [q for q in after if q["id"] not in before and q.get(CARD)]
    cards = list(dict.fromkeys(q[CARD] for q in new))
    off = [
        {"item_kind": ItemKind.Question.value, "item_id": q["id"], "field": CARD, "after": None}
        for q in after
        if q.get(CARD) in cards and q["id"] not in {n["id"] for n in new}
        and record.note(q) is record.IMPRESSION
    ]
    if off:
        record.apply(diagram.id, off, author=Author.Coach, turn_id=turn_id, user_id=user.id)
    return cards


def _observe(diagram_id: int, turn_id: str, kind: ObservationKind, detail: dict) -> None:
    db.session.add(Observation(diagram_id=diagram_id, turn_id=turn_id, kind=kind, detail=detail))
    db.session.commit()


def run(turn_id: str, diagram_id: int, user_id: int) -> dict:
    """The task. It ends in one event, always: done with the cards written and
    the record's version, or failed with a sentence for the page."""
    _log.info(f"{TASK} {turn_id} diagram={diagram_id}")
    diagram = db.session.get(Diagram, diagram_id)
    user = db.session.get(User, user_id)
    meter = Metered(
        user_id,
        diagram_id,
        turn_id,
        Purpose.Coach,
        model=model_for(setting.read(SettingKey.CoachModel, user_id)),
    )
    try:
        cards = rewrite(diagram, meter, user, turn_id)
    except Refusal as refused:
        db.session.rollback()
        _observe(diagram_id, turn_id, ObservationKind.TurnDeclined,
                 {"category": refused.category, "reason": f"case report rewrite: {refused.category}"})
        return _end(diagram_id, turn_id, {"type": TurnEventKind.Refused.value, "message": REFUSED})
    # The one router in this task: the page is told it ended, and the error goes on.
    except Exception as error:
        db.session.rollback()
        _observe(diagram_id, turn_id, ObservationKind.TurnFailed,
                 {"error": f"{type(error).__name__}: {error}",
                  "reason": f"case report rewrite: {type(error).__name__}"})
        _end(diagram_id, turn_id, {"type": TurnEventKind.Failed.value, "message": BROKE})
        raise
    TokenMeter.charge(user_id, meter.spent)
    db.session.commit()
    db.session.refresh(diagram)
    return _end(
        diagram_id,
        turn_id,
        {"type": TurnEventKind.Done.value, "turn_id": turn_id, "cards": cards, "version": diagram.version},
    )


def _end(diagram_id: int, turn_id: str, event: dict) -> dict:
    turnlog.append(turn_id, event)
    turnlog.release(diagram_id)
    return event
