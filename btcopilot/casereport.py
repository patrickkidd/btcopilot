"""The case report against the diagram as it stands: whether something has
changed since the coach wrote its cards (R-0827), and the rewrite of every card
the coach writes at once, from the diagram, in one model call (R-0825).

Out of date is a rule on the command log, no model: a person, an event or a
pair-bond changed after a card on the report was last written. The
rewrite runs in the worker like a coach turn and ends in a done or failed
event on the turn log; the page polls its state.
"""

import enum
import logging
import re
import uuid

from btcopilot import clock, coverage, extensions, profile, record, turnlog
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Refusal, model_for
from btcopilot.coachturn import run_call
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Discussion,
    Observation,
    ObservationKind,
    Purpose,
    TokenMeter,
    User,
)
from btcopilot.prompts import case_report_rewrite, get_agent_prompt
from btcopilot.questions import order, sessions
from btcopilot.recordtext import note_line, on_map, outline, question_order
from btcopilot.schema import (
    CardLine,
    CaseReportCard,
    DiagramData,
    EvidenceKind,
    EventKind,
    ItemKind,
    QuestionState,
    enum_val,
    parse_date,
)
from btcopilot.toolbox import ReadField, ToolName, Toolbox, schemas
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

TASK = "case_report_rewrite"
CARD = record.CARD
# What a couple's event is called in a sentence.
MARKED = {EventKind.Death: "death", EventKind.Married: "marriage",
          EventKind.Separated: "separation", EventKind.Divorced: "divorce"}
# What a change must touch to put the report out of date (R-0825).
FAMILY = {ItemKind.Person.value, ItemKind.Event.value, ItemKind.PairBond.value}
SINCE = "after the coach wrote this report."
FIELDS = ("text", "evidence", "state", CARD)
CLOSED = "CLOSED QUESTIONS"
BROKE = "The case report could not be written again just now."
REFUSED = "The case report could not be written again from this diagram."
MOVED = "The diagram changed while the case report was being written; refresh it again."
SUMMARIES = "ONE SUMMARY PER CONVERSATION (oldest first)"
OPENING = "THE OPENING OF THE FIRST CONVERSATION"
# How much of the first conversation the rewrite reads raw, when no note on
# the what_brought card holds what brought the person in (R-0850).
OPENING_CHARS = 2000
SENTENCE = re.compile(r"(?<=[.?!])\s+")
# A cluster's slot on the coach's guess: "For c3: ..." or "Against c3: ...".
SLOT = re.compile(rf"^({CardLine.For.value}|{CardLine.Against.value}) (\S+):")


class State(enum.StrEnum):
    Running = "running"
    Done = "done"
    Failed = "failed"


class Busy(Exception):
    """A second rewrite of one family's report while the first is running."""


class Sessionless(Exception):
    """A family with no session has no case report to write again."""


def _carded(delta: dict) -> str | None:
    """The case report card a delta put an entry on, or None."""
    if delta["item_kind"] != ItemKind.Question.value:
        return None
    if delta["field"] == CARD:
        return delta["after"]
    whole = delta["field"] is None and delta.get("before") is None and delta["after"]
    return whole.get(CARD) if whole else None


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


def _said(delta: dict, events: dict, people: dict) -> str:
    """The sentence one change to the family puts the report out of date with."""
    iid = str(delta["item_id"])
    whole = delta.get("after") or delta.get("before") or {}
    if delta["item_kind"] == ItemKind.Event.value:
        label = _label(events.get(iid, whole), people)
    elif delta["item_kind"] == ItemKind.Person.value:
        label = _name(people, iid) or whole.get("name") or "a person"
    else:
        label = "a pair-bond"
    if delta["field"] is None:
        done = "added" if delta.get("before") is None else "removed"
        return f"{label[0].upper()}{label[1:]} was {done} {SINCE}"
    if delta["item_kind"] == ItemKind.Event.value and delta["field"] == "dateTime":
        return f"The date of {label} changed {SINCE}"
    if delta["item_kind"] == ItemKind.Event.value and delta["field"] == "kind":
        return f"What kind of event {label} is changed {SINCE}"
    return f"{label[0].upper()}{label[1:]} changed {SINCE}"


def stale(diagram_id: int, data: DiagramData) -> dict | None:
    """The newest change to a person, an event or a pair-bond made after a card
    on the report was last written, or None: its change row id, when, and one
    sentence naming it, or how many when there are several: one item in one
    turn is one change, and a pair-bond written with an event is part of that
    event. The coach writing
    one card again leaves the others older than the change. A change taken
    back, and the undo itself, count for nothing."""
    taken = record.undone(diagram_id)
    rows = [
        c
        for c in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id)
        if c.id not in taken and not c.turn_id.startswith("undo:")
    ]
    shown = {q[CARD] for q in data.questions if q.get(CARD)}
    last = {}
    for i, change in enumerate(rows):
        for card in shown.intersection(map(_carded, change.deltas)):
            last[card] = i
    if not last:
        return None
    since = {}
    for change in rows[min(last.values()) + 1 :]:
        for delta in change.deltas:
            if delta["item_kind"] in FAMILY:
                since.setdefault((change.turn_id, delta["item_kind"], str(delta["item_id"])), (change, delta))
    with_event = {turn for turn, kind, _ in since if kind == ItemKind.Event.value}
    since = [
        found
        for (turn, kind, _), found in since.items()
        if not (kind == ItemKind.PairBond.value and turn in with_event)
    ]
    if not since:
        return None
    change = max((c for c, _ in since), key=lambda c: c.id)
    if len(since) == 1:
        events = {str(e["id"]): e for e in data.events}
        people = {str(p["id"]): p for p in data.people}
        sentence = _said(since[0][1], events, people)
    else:
        sentence = f"{len(since)} changes to the diagram since the coach wrote this report."
    return {"change_id": change.id, "at": change.created_at.isoformat(), "sentence": sentence}


def closed(data: DiagramData) -> str:
    """The questions the coach's map leaves out once closed, so the pass sees
    an own part question that was already answered."""
    lines = [
        note_line(q)
        for q in sorted(data.questions, key=question_order)
        if record.note(q) is record.QUESTION and not on_map(q)
    ]
    return f"\n\n{CLOSED}\n" + "\n".join(lines) if lines else ""


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
    """add_impression, with only the fields a card's guess gives."""
    (schema,) = [s for s in schemas() if s["name"] == ToolName.AddImpression.value]
    given = schema["input_schema"]
    return [
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
    if call.name != ToolName.AddImpression.value:
        return f"{call.name} is not part of a case report rewrite"
    extra = sorted(set(call.args) - set(FIELDS))
    if extra:
        return f"add_impression may not give {', '.join(extra)} here"
    if call.args.get("state") != QuestionState.Raised.value:
        return "a guess on the case report is raised"
    card = call.args.get(CARD)
    if card not in {c.value for c in CaseReportCard}:
        return f"no case report card {card!r}"
    if card == CaseReportCard.Choice:
        return "the choice is part of own_part now: state the other way it could have gone there"
    evidence = call.args.get("evidence") or []
    if card == CaseReportCard.WhatBrought and not any(
        one.get("kind") == EvidenceKind.Statement for one in evidence
    ):
        return "what_brought rests on the person's own message: give it as a statement"
    clusters = {str(one.get("id")) for one in evidence if one.get("kind") == EvidenceKind.Cluster}
    for line in (call.args.get("text") or "").splitlines():
        slot = SLOT.match(line)
        if slot and slot.group(2) not in clusters:
            return f"{slot.group(1)} {slot.group(2)} names a cluster the card does not rest on"
    return None


def caused(call) -> str | None:
    """The first word in a card's text that gives a cause or a why, or None (R-0850)."""
    found = record.CAUSE.search(call.args.get("text") or "")
    return found and found.group(0)


def uncaused(text: str) -> str:
    """The text with every sentence that gives a cause or a why taken out."""
    kept = []
    for line in text.splitlines():
        sentences = [s for s in SENTENCE.split(line) if not record.CAUSE.search(s)]
        if sentences:
            kept.append(" ".join(sentences))
    return "\n".join(kept)


def box(diagram: Diagram, user: User, turn_id: str) -> Toolbox:
    """The coach's tools on the family's newest session, as the coach."""
    return Toolbox(
        diagram.id,
        turn_id,
        user_id=user.id,
        session_id=sessions(diagram)[-1].id,
        author=Author.Coach,
        zone=user.timezone,
    )


def summaries(diagram: Diagram, meter: Metered) -> str:
    """One summary per conversation, the stored one, written now for a
    conversation that has none (R-0850)."""
    lines = []
    for n, discussion in enumerate(sessions(diagram), 1):
        if not discussion.summary:
            discussion.update_summary(meter)
        day = discussion.created_at.date().isoformat()
        lines.append(f"{n}. {day}: {discussion.summary}")
    return "\n".join(lines)


def opening(data: DiagramData, first: Discussion) -> str:
    """The first conversation's opening, each message by its number, up to
    OPENING_CHARS; nothing when a note on the what_brought card already
    holds what brought the person in (R-0850)."""
    if any(q.get(CARD) == CaseReportCard.WhatBrought for q in data.questions):
        return ""
    said, size = [], 0
    for statement in sorted(first.statements, key=order):
        who = "Person" if statement.speaker_id == first.chat_user_speaker_id else "Coach"
        line = f"[message {statement.id}, {statement.created_at.date().isoformat()}] {who}: {statement.text}"
        said.append(line[: OPENING_CHARS - size])
        size += len(line)
        if size >= OPENING_CHARS:
            break
    return "\n".join(said)


def asked(diagram: Diagram, user: User, toolbox: Toolbox, meter: Metered) -> tuple[str, list[dict]]:
    """The one call's system prompt, the coach's own, and its opening message
    with every event's words and notes, one summary per conversation, and,
    with no note on what brought the person, the first conversation's opening
    read raw, so it reads nothing (R-0850)."""
    data = diagram.get_diagram_data()
    own = profile.own(data)
    system = get_agent_prompt(
        record=outline(data, diagram.version, own and own["id"]) + closed(data),
        today=clock.today(user.timezone).isoformat(),
        coverage=coverage.block(data),
    )
    events, _ = toolbox.call(ToolName.ReadEvents, {"fields": [ReadField.Words, ReadField.Notes]})
    content = f"{case_report_rewrite()}\n\nEVENTS\n{events}\n\n{SUMMARIES}\n{summaries(diagram, meter)}"
    raw = opening(data, sessions(diagram)[0])
    if raw:
        content += f"\n\n{OPENING}\n{raw}"
    return system, [{"role": "user", "content": content}]


def wrote(diagram: Diagram, toolbox: Toolbox, calls: list) -> list[str]:
    """Each guess in through the coach's own tool, a refused one written down,
    and what was on a card written anew taken off it. The cards written, in
    order."""
    before = {q["id"] for q in toolbox.data.questions}
    for call in calls:
        refusal = checked(call)
        if refusal is None:
            _, _, refusal = run_call(toolbox, call)
        if refusal:
            _observe(diagram.id, toolbox.turn_id, ObservationKind.ToolRefused,
                     {"tool": call.name, "refusal": refusal, "retried": False,
                      "reason": f"case report rewrite: {call.name}: {refusal}"})
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
        record.apply(diagram.id, off, author=Author.Coach, turn_id=toolbox.turn_id, user_id=toolbox.user_id)
    return cards


class Moved(Exception):
    """The family changed while the model wrote, so its cards would be old."""


def _called(diagram: Diagram, meter: Metered, system: str, messages: list[dict], turn_id: str):
    """One model call, the report held through every piece of it."""
    words = meter.turn(system, messages, offered(), turn_id)
    while True:
        turnlog.hold(diagram.id, turn_id)
        try:
            next(words)
        except StopIteration as stop:
            return stop.value


def _again(turn, caught: dict) -> list[dict]:
    """The model's answer and what each call came to: a card that gave a
    cause or a why is refused, the rest stand."""
    results = [
        {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": (
                f"refused: {caught[call.id]!r} gives a cause or a why; state the pattern, "
                "what happened and when, and give this card again"
                if call.id in caught
                else "kept"
            ),
            "is_error": call.id in caught,
        }
        for call in turn.calls
    ]
    return [{"role": "assistant", "content": turn.blocks}, {"role": "user", "content": results}]


def rewrite(diagram: Diagram, meter: Metered, user: User, turn_id: str) -> list[str]:
    """One model call writes every card again (R-0825). A card that gives a
    cause or a why is refused and asked for once more; given again with one,
    it is written with those sentences taken out (R-0850). Cards read from a
    family that changed during the call are not written, so the report stays
    out of date (R-0826)."""
    toolbox = box(diagram, user, turn_id)
    version = diagram.version
    system, messages = asked(diagram, user, toolbox, meter)
    turn = _called(diagram, meter, system, messages, turn_id)
    calls = turn.calls
    caught = {call.id: word for call in calls if (word := caused(call))}
    if caught:
        _observe(diagram.id, turn_id, ObservationKind.ToolRefused,
                 {"tool": ToolName.AddImpression.value, "refusal": f"gave a cause: {', '.join(caught.values())}",
                  "retried": True, "reason": "case report rewrite: a card gave a cause or a why"})
        retry = _called(diagram, meter, system, messages + _again(turn, caught), turn_id)
        calls = [c for c in calls if c.id not in caught] + retry.calls
    for call in calls:
        if caused(call):
            call.args = {**call.args, "text": uncaused(call.args.get("text") or "")}
    calls = [c for c in calls if c.args.get("text")]
    db.session.refresh(diagram)
    if diagram.version != version:
        raise Moved(f"diagram {diagram.id} moved from version {version} to {diagram.version}")
    return wrote(diagram, toolbox, calls)


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
    except Moved as moved:
        _log.info(f"{TASK} {turn_id} wrote nothing: {moved}")
        TokenMeter.charge(user_id, meter.spent)
        db.session.commit()
        return _end(diagram_id, turn_id, {"type": TurnEventKind.Failed.value, "message": MOVED})
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
    turnlog.release(diagram_id, turn_id)
    return event
