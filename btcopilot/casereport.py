"""The case report against the diagram as it stands: whether something has
changed since the coach wrote its cards (R-0827), and the rewrite of every card
the coach writes at once, from the diagram, in one model call (R-0825).

Out of date is a rule on the command log, no model: a person, an event or a
pair-bond changed after a card on the report was last written. The
rewrite runs in the worker like a coach turn and ends in a done or failed
event on the turn log; the page polls its state.
"""

import datetime
import enum
import logging
import re
import uuid
from collections import Counter

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
# After btcopilot.models: btcopilot.clusters imports btcopilot.metered first,
# and btcopilot.metered and btcopilot.models import each other.
from btcopilot import clusters
from btcopilot.prompts import case_report_rewrite, get_agent_prompt
from btcopilot.questions import order, sessions
from btcopilot.recordtext import note_line, on_map, outline, question_order
from btcopilot.schema import (
    DEFAULT_SUBJECT_NAME,
    MIN_CLUSTER_EVENTS,
    CardLine,
    CaseReportCard,
    DateCertainty,
    DiagramData,
    EvidenceKind,
    EventKind,
    ItemKind,
    QuestionState,
    RelationshipKind,
    enum_val,
    parse_date,
)
from btcopilot.toolbox import CARDS, ReadField, ToolName, Toolbox, schemas
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
# What the page says of a report the catch-up marked out of date (R-0772).
NEW_WAY = "The coach now writes this report a new way."
FIELDS = ("text", "evidence", "state", CARD)
CLOSED = "CLOSED QUESTIONS"
BROKE = "The case report could not be written again just now."
REFUSED = "The case report could not be written again from this diagram."
MOVED = "The diagram changed while the case report was being written; refresh it again."
SUMMARIES = "ONE SUMMARY PER CONVERSATION (oldest first)"
OPENING = "THE OPENING OF THE FIRST CONVERSATION"
HELD = "THE SHIFTS THAT SUPPORT EACH CLUSTER"
KIN = "WHAT EACH PERSON IS TO THE PERSON"
ORDER = "BROTHERS AND SISTERS IN BIRTH ORDER"
TRIANGLES = "TRIANGLES THE EVENTS MARK"
PAIRS = "RELATIONSHIP EVENTS BY PAIR"
SIDES = "EACH SIDE OF THE FAMILY"
# The relationship marks one person makes toward another, as against the
# inside and outside marks of a triangle.
TRIANGLE = (RelationshipKind.Inside, RelationshipKind.Outside)
WORDS_CHARS = 60
# How much of the first conversation the rewrite reads raw, when no note on
# the what_brought card holds what brought the person in (R-0850).
OPENING_CHARS = 2000
# A cluster's slot on the coach's guess: "For c3: ..." or "Against c3: ...".
SLOT = re.compile(rf"^({CardLine.For.value}|{CardLine.Against.value}) (\S+):")
# Every mark that opens a line of a card, which the page draws only at the
# start of one (R-0850).
MARK = re.compile(
    rf"\b(?:(?:{CardLine.For.value}|{CardLine.Against.value}) \S+"
    rf"|{'|'.join(m.value for m in CardLine if m not in (CardLine.For, CardLine.Against))}):"
)
# Words that say what will come. Only what to work on predicts, on its
# Prognosis line (FE 3117, 3463-3467; R-0850). "Going to" says what will come
# only after a present "is", "are" or "am", never in "stopped going to class".
FORETOLD = re.compile(
    r"\b(will|won't|(?:is|are|am|'s|’s|'re|’re) going to|expect(?:s|ed)?|predicts?|prediction"
    r"|prognosis|(?:un)?likely)\b",
    re.I,
)
# The Executive Summary: who has the trouble and what it is in one or two
# sentences, then the pattern of the coach's guess in one (R-0850).
SUMMARY_SENTENCES = 3
# Whose reading a card is: the person's ("You said ...") or the app's ("The
# app's guess: ..."), unless the card is the one line saying the diagram holds
# too little for it (R-0850).
WHOSE = re.compile(r"\byou (?:said|told)\b|\bthe app['’]s guess\b", re.I)
# on a case nobody on is the person it belongs to, what they said is given by name
SAID = re.compile(r"\b(?:said|told)\b|\bthe app['’]s guess\b", re.I)
ABOUT = (
    "Nobody on this case is the person it belongs to: the coach on it reads "
    "this report. Write every card about {name} by name, never to them as "
    "\"you\": what {name} said is theirs (\"{name} said ...\")."
)
THIN = "Not enough in the diagram yet"
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


def _logged(diagram_id: int) -> list[Change]:
    """The change rows the report is read against, oldest first: a change
    taken back, and the undo itself, count for nothing."""
    taken = record.undone(diagram_id)
    return [
        c
        for c in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id)
        if c.id not in taken and not c.turn_id.startswith("undo:")
    ]


def _shown(data: DiagramData) -> set[str]:
    """The cards the page shows an entry on; the retired choice card is not one."""
    return {q[CARD] for q in data.questions if q.get(CARD)} & set(CARDS)


def written(diagram_id: int, data: DiagramData) -> dict[str, datetime.datetime | None]:
    """When the coach last wrote each card the page shows, a refresh or one
    card, or None for a card the change log holds no write of."""
    shown = _shown(data)
    when = dict.fromkeys(shown)
    for change in _logged(diagram_id):
        for card in shown.intersection(map(_carded, change.deltas)):
            when[card] = change.created_at
    return when


def stale(diagram_id: int, data: DiagramData) -> dict | None:
    """The newest change to a person, an event or a pair-bond made after the
    coach last wrote a card on the report, a refresh or one card, or None:
    its change row id, when, and one sentence naming it, or how many when
    there are several: one item in one turn is one change, and a pair-bond
    written with an event is part of that event. With none, a report the
    catch-up marked out of date until a Refresh says the coach now writes it
    a new way, against that last write (R-0772)."""
    rows = _logged(diagram_id)
    shown = _shown(data)
    last = None
    for i, change in enumerate(rows):
        if shown.intersection(map(_carded, change.deltas)):
            last = i
    if last is None:
        return None
    since = {}
    for change in rows[last + 1 :]:
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
        if not db.session.get(Diagram, diagram_id).case_report_forced_out_of_date:
            return None
        return {"change_id": rows[last].id, "at": rows[last].created_at.isoformat(), "sentence": NEW_WAY}
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
    shaped = _shaped(card, call.args.get("text") or "")
    if shaped:
        return shaped
    evidence = call.args.get("evidence") or []
    if not all(isinstance(one, dict) for one in evidence):
        return "give each piece of evidence as an object with its kind and its id"
    clusters = {str(one.get("id")) for one in evidence if one.get("kind") == EvidenceKind.Cluster}
    for line in (call.args.get("text") or "").splitlines():
        line = line.strip()
        slot = SLOT.match(line)
        if slot and slot.group(2) not in clusters:
            return f"{slot.group(1)} {slot.group(2)} names a cluster the card does not rest on"
        inside = next((m for m in MARK.finditer(line) if m.start() > 0), None)
        if inside:
            return (
                f"{inside.group(0)!r} is inside a line: start each of "
                f"{', '.join(m.value for m in CardLine)} on a line of its own"
            )
        raw = record.RAW_ID.search(line[slot.end():] if slot else line)
        if raw:
            return (
                f"{raw.group(0)!r} is an id in the card's words: name the person, event or "
                "cluster in words; a cluster's id goes only after For or Against"
            )
    return None


def _shaped(card: str, text: str) -> str | None:
    """Why a card's words break its card's shape, outside the person's quoted
    words, or None: a prediction off what to work on, or an Executive Summary
    longer than the trouble and the pattern (R-0850)."""
    said = record.QUOTED.sub("", text)
    word = card != CaseReportCard.WorkOn and FORETOLD.search(said)
    if word:
        return (
            f"{word.group(0)!r} says what will come; only the Prognosis line of "
            f"{CaseReportCard.WorkOn.value} predicts"
        )
    return None


def overlong(call) -> int | None:
    """The sentence count of an Executive Summary past SUMMARY_SENTENCES, or
    None; kept and observed, never refused (R-0850)."""
    if call.args.get(CARD) != CaseReportCard.MainGuess:
        return None
    said = record.QUOTED.sub("", call.args.get("text") or "")
    count = sum(1 for line in said.splitlines() for s in record.SENTENCE.split(line.strip()) if s)
    return count if count > SUMMARY_SENTENCES else None


def unmarked(call, addressed: bool = True) -> str | None:
    """Why a card's words, outside the person's quoted ones, do not say whose
    reading they are, or None; what brought the person is their own quoted
    words, and the family card gives the diagram's facts bare (R-0850, R-0863).
    On a case written about the person (`addressed` false) what they said is
    given by name."""
    text = call.args.get("text") or ""
    if call.args.get(CARD) in (CaseReportCard.WhatBrought, CaseReportCard.Family) or text.startswith(THIN):
        return None
    marks, said = (WHOSE, "\"You said ...\"") if addressed else (SAID, "\"<their name> said ...\"")
    return None if marks.search(record.QUOTED.sub("", text)) else (
        f"the card does not say whose reading it is: give what the person said as "
        f"{said} and the rest as \"The app's guess: ...\""
    )


def misspoken(call, addressed: bool = True) -> str | None:
    """Why a card's text cannot stand as the coach's words, or None: a word
    that gives a cause or a why (R-0850, R-0864), or, on a case written to the
    person (`addressed`), one that speaks as them outside their quoted words
    (R-0860)."""
    text = call.args.get("text") or ""
    word = record.caused(text)
    if word:
        return (
            f"{word!r} gives a cause or a why; say what happened and when, side by "
            "side, and how close in time"
        )
    if not addressed:
        return None
    word = record.voiced(text)
    return word and (
        f"{word!r} speaks as the person; write as the coach, calling them you, "
        "and put their own words only inside quotation marks"
    )


def uncaused(text: str) -> str:
    """The text with every sentence taken out that gives a cause or a why,
    the person's own voice kept: a case written about them (R-0850)."""
    kept = []
    for line in text.splitlines():
        sentences = [s for s in record.SENTENCE.split(line) if not record.caused(s)]
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


SURENESS = (DateCertainty.Unknown, DateCertainty.Approximate, DateCertainty.Certain)


def _sure(data: DiagramData, *ids: int) -> DateCertainty:
    """The least sure date among these events."""
    marks = {
        e["id"]: DateCertainty(enum_val(e.get("dateCertainty")) or DateCertainty.Certain)
        for e in data.events
        if e.get("id") in ids
    }
    return min(marks.values(), key=SURENESS.index)


def _days(gap: int, sure: DateCertainty) -> str:
    """How far a shift falls from its cluster's opening, no finer than the
    two dates hold: days when both are certain, years when either is
    approximate, nothing when either is a guess [Oracle: R-0855]."""
    if sure is DateCertainty.Unknown:
        return "at a date nobody knows"
    side = "after" if gap > 0 else "before"
    if sure is DateCertainty.Approximate:
        years = round(abs(gap) / 365)
        if years == 0:
            return "within about a year of its opening"
        return f"about {years} year{'' if years == 1 else 's'} {side} its opening"
    if gap == 0:
        return "on the day of its opening"
    return f"{abs(gap)} days {side} its opening"


def held(data: DiagramData) -> str:
    """Each drawn cluster read against the data: how many of its events are a
    rise in symptom or anxiety, a fall in functioning or a relationship shift,
    whether they are all one person's, and how far the first and last fall
    from its opening, so the coach's guess says on that cluster's Against line
    when there are fewer than three (R-0850)."""
    people = {str(p["id"]): p for p in data.people}
    lines = []
    for cluster in data.drawn_clusters():
        read = clusters.judge(cluster, data)
        count = len(read.shiftIds)
        parts = [f"{count} supporting shift{'' if count == 1 else 's'}"
                 + ("" if read.supported else f", fewer than {MIN_CLUSTER_EVENTS}")]
        if read.runOf is not None:
            parts.append(f"all of them {_name(people, read.runOf) or 'one person'}'s")
        if read.opening is not None and read.toFirst is not None:
            first, last = read.shiftIds[0], read.shiftIds[-1]
            parts.append(
                f"opened by event {read.opening}, the first shift "
                f"{_days(read.toFirst, _sure(data, read.opening, first))}, "
                f"the last {_days(read.toLast, _sure(data, read.opening, last))}"
            )
        changes = _changes(data, cluster)
        if changes:
            parts.append(f"changes in the family in its years: {changes}")
        if read.opening is not None:
            parts.append(_opener(data, read.opening))
        lines.append(f"{cluster['id']}: " + "; ".join(parts))
    return "\n".join(lines)


UNDATED = "date unknown"


def _year(event: dict | None) -> str:
    """An event's year, no surer than its date is marked [Oracle: R-0855]."""
    when = parse_date(event.get("dateTime")) if event else None
    sure = enum_val(event.get("dateCertainty")) if event else None
    if when is None or sure == DateCertainty.Unknown.value:
        return UNDATED
    return f"about {when.year}" if sure == DateCertainty.Approximate.value else str(when.year)


def _who(data: DiagramData, pid) -> str:
    return coverage.label(data, ItemKind.Person, pid)


def _changes(data: DiagramData, cluster: dict) -> str:
    """Every event other than a shift in the cluster's years, anyone's, by
    year: the births, deaths, couplings, partings and noted events that piled
    up then (FE 3109-3111)."""
    dated = {e["id"]: parse_date(e.get("dateTime")) for e in data.events}
    years = [dated[i].year for i in cluster.get("eventIds") or [] if dated.get(i)]
    if not years:
        return ""
    by_year: dict[int, list[str]] = {}
    for event in sorted(data.events, key=lambda e: (dated[e["id"]] or datetime.date.max, e["id"])):
        when = dated[event["id"]]
        kind = EventKind(enum_val(event.get("kind")) or EventKind.Shift.value)
        if when and min(years) <= when.year <= max(years) and kind.isLead():
            by_year.setdefault(when.year, []).append(kind.value)
    return "; ".join(f"{year} {', '.join(kinds)}" for year, kinds in by_year.items()) or "none in the diagram"


def _opener(data: DiagramData, event_id: int) -> str:
    """Who the cluster's opening event is about, with their partners and
    their children, so the coach can say who was rearranged around it."""
    event = next(e for e in data.events if e["id"] == event_id)
    pid = event.get("person")
    if pid is None:
        return "its opening names no person"
    bonds = [
        b for b in data.pair_bonds if pid in (b.get("person_a"), b.get("person_b"))
    ]
    partners = [
        _who(data, other)
        for b in bonds
        for other in (b.get("person_a"), b.get("person_b"))
        if other not in (pid, None)
    ]
    children = [
        f"{_who(data, p['id'])} born {_year(profile.birth(data, p['id']))}"
        for b in bonds
        for p in data.people
        if p.get("parents") == b["id"]
    ]
    return (
        f"its opening is about {_who(data, pid)}, "
        f"partners: {', '.join(partners) or 'none in the diagram'}, "
        f"children: {', '.join(children) or 'none in the diagram'}"
    )


def _names_of(data: DiagramData) -> dict:
    return {p["id"]: p.get("name") or "unnamed" for p in data.people}


def _named(data: DiagramData) -> dict:
    return {pid: f"{pid} {name}" for pid, name in _names_of(data).items()}


def kin(data: DiagramData) -> str:
    """Everyone the record places, grouped by what they are to the person and,
    in a parent's family, whose side they are on, so a card names the side of
    the family a fact comes from (R-0850)."""
    side = {pid: parent for parent, people in coverage.sides(data).items() for pid in people}
    named = _named(data)
    groups: dict[str, list[str]] = {}
    for person in data.people:
        pid = person["id"]
        role, parent = coverage.role(data, pid), side.get(pid)
        if role is None and parent is None:
            continue
        what = role or "a relative"
        if parent is not None and parent != pid:
            what += f" on the {coverage.role(data, parent) or 'parent'}'s side"
        groups.setdefault(what, []).append(named[pid])
    return "\n".join(f"{what}: {', '.join(people)}" for what, people in groups.items())


def _place(data: DiagramData, kids: list[int], pid: int) -> str:
    """Where one falls among their brothers and sisters, or that it is not
    known when a birth among them has no date anyone is sure of."""
    if any(_year(profile.birth(data, kid)) == UNDATED for kid in kids):
        return "place not known, a birth among them has no date"
    return f"born {kids.index(pid) + 1} of {len(kids)}"


def order_of_birth(data: DiagramData) -> str:
    """The person's brothers and sisters and each parent's, in birth order,
    with each one's place among them (FE 3221, 3461; R-0850)."""
    own = profile.own(data)
    if own is None:
        return ""
    named = _named(data)
    lines = []
    for pid in [own["id"], *coverage.sides(data)]:
        kids = coverage.in_birth_order(data, pid)
        if len(kids) == 1:
            said = "no brothers or sisters in the diagram"
        else:
            said = _place(data, kids, pid) + ": " + ", ".join(
                f"{named[k]} {_year(profile.birth(data, k))}" for k in kids
            )
        lines.append(f"{_who(data, pid)}: {said}")
    return "\n".join(lines)


def _words(event: dict) -> str:
    said = (event.get("title") or event.get("description") or "").strip()
    return f" “{said[:WORDS_CHARS]}”" if said else ""


def _dated(event: dict) -> tuple:
    when = parse_date(event.get("dateTime"))
    return (when is None, when or datetime.date.min, event["id"])


def _marked(event: dict) -> RelationshipKind | None:
    value = enum_val(event.get("relationship"))
    return RelationshipKind(value) if value else None


def _names(named: dict, ids) -> str:
    return " and ".join(named.get(i, str(i)) for i in ids)


def triangles(data: DiagramData) -> str:
    """One line per three people the inside and outside marks put together,
    each mark dated with who was inside and who outside, so a card names a
    triangle only when the events mark it (R-0850)."""
    named = _names_of(data)
    marked: dict[frozenset, list[str]] = {}
    for event in sorted(data.events, key=_dated):
        kind = _marked(event)
        if kind not in TRIANGLE or event.get("person") is None:
            continue
        mover = event["person"]
        targets = event.get("relationshipTargets") or []
        thirds = event.get("relationshipTriangles") or []
        if kind is RelationshipKind.Inside:
            inside, outside = [mover, *targets], thirds
        else:
            inside, outside = [*targets, *thirds], [mover]
        marked.setdefault(frozenset([mover, *targets, *thirds]), []).append(
            f"{_year(event)} {_names(named, inside)} inside, {_names(named, outside)} outside{_words(event)}"
        )
    return "\n".join(
        f"{', '.join(_who(data, pid) for pid in sorted(three))}: {'; '.join(marks)}"
        for three, marks in marked.items()
    )


def pairs(data: DiagramData) -> str:
    """One line per two people, one of them in the person's own family or
    their parents' or grandparents', with every relationship mark between
    them by date, who made it, and its words, from the stored events alone,
    so a card lays the people out in time order (R-0850, R-0864). Pairs
    farther out are counted; their marks are on the event lines."""
    named = _names_of(data)
    near = coverage.nearest(data)
    marked: dict[frozenset, list[str]] = {}
    for event in sorted(data.events, key=_dated):
        kind = _marked(event)
        if kind is None or kind in TRIANGLE or event.get("person") is None:
            continue
        mover = event["person"]
        for target in event.get("relationshipTargets") or []:
            marked.setdefault(frozenset([mover, target]), []).append(
                f"{_year(event)} {named.get(mover, mover)} {kind.value}{_words(event)}"
            )
    lines = [
        f"{' and '.join(_who(data, pid) for pid in sorted(two))}: {'; '.join(marks)}"
        for two, marks in marked.items()
        if two & near
    ]
    farther = sum(1 for two in marked if not two & near)
    if farther:
        lines.append(
            f"{farther} more pair{'' if farther == 1 else 's'} farther out in the family "
            f"{'has' if farther == 1 else 'have'} relationship events"
        )
    return "\n".join(lines)


def by_side(data: DiagramData) -> str:
    """How many events the diagram holds about each parent's side of the
    family, so a side it knows little about reads as a fact toward cutoff,
    held as the app's guess (FE 3115, 3205); who on it has died; and the
    person's last relationship event with each one on it, the only contact
    the diagram holds, so a card gives the contact now or says it is not
    known (R-0850)."""
    deaths = {e.get("person"): e for e in data.events if enum_val(e.get("kind")) == EventKind.Death.value}
    roles = coverage.roles(data)
    who = coverage.labels(data, roles)
    named = _named(data)

    def on_side(pid: int, parent: int) -> str:
        """Someone on a parent's side as the cards name them: a parent's
        brother or sister is that parent's, "mother's sister", never the
        person's aunt or uncle, which a card read as the parent's own aunt or
        uncle."""
        role = roles.get(pid)
        if role not in coverage.AUNT_ROLE:
            return who[pid]
        sibling = coverage.SIB[coverage.AUNT_ROLE.index(role)]
        return f"{named[pid]} ({roles.get(parent)}'s {sibling})"

    lines = []
    for parent, side in coverage.sides(data).items():
        people = sorted(side)
        count = sum(any(record.involves(e, pid) for pid in side) for e in data.events)
        died = [f"{on_side(pid, parent)} {_year(deaths[pid])}" for pid in people if pid in deaths]
        living = [on_side(pid, parent) for pid in people if pid not in deaths]
        lines.append(
            f"the side of {who[parent]}: {count} events; "
            f"died: {', '.join(died) or 'none in the diagram'}; "
            f"no death among them in the diagram: {', '.join(living) or 'none'}; "
            f"the person's last relationship event with each one on it: "
            f"{_contact(data, side) or 'none in the diagram'}"
        )
    return "\n".join(lines)


def _contact(data: DiagramData, side: set[int]) -> str:
    """The last relationship event between the person and each one on a side
    of the family, either way, by date."""
    me = profile.own(data)["id"]
    names = _names_of(data)
    named = _named(data)
    last = {}
    for event in sorted(data.events, key=_dated):
        mover = event.get("person")
        kind = _marked(event)
        if kind is None or mover is None:
            continue
        others = {*(event.get("relationshipTargets") or []), *(event.get("relationshipTriangles") or [])}
        for pid in others if mover == me else [mover] if me in others else []:
            if pid in side:
                last[pid] = f"{_year(event)} {names.get(mover, mover)} {kind.value}{_words(event)}"
    return "; ".join(f"{named[pid]} {said}" for pid, said in sorted(last.items()))


def family(data: DiagramData) -> str:
    """The blocks the refresh reads beside the events, each left out when the
    diagram holds nothing for it (R-0850)."""
    blocks = [
        (KIN, kin(data)),
        (ORDER, order_of_birth(data)),
        (SIDES, by_side(data)),
        (TRIANGLES, triangles(data)),
        (PAIRS, pairs(data)),
    ]
    return "".join(f"\n\n{title}\n{body}" for title, body in blocks if body)


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


def audience(diagram: Diagram, data: DiagramData) -> tuple[int | None, str]:
    """The person the case report speaks to as "you", when the person it
    belongs to is on the case, else none and the line naming the client it is
    about (FD-387)."""
    own = profile.own(data)
    if profile.addressed(diagram, data):
        return (own["id"] if own else None), ""
    return None, "\n\n" + ABOUT.format(name=(own or {}).get("name") or DEFAULT_SUBJECT_NAME)


def asked(diagram: Diagram, user: User, toolbox: Toolbox, meter: Metered) -> tuple[str, list[dict]]:
    """The one call's system prompt, the coach's own, and its opening message
    with every event's words and notes, the shifts that support each drawn
    cluster with the changes in the family in its years and who its opening
    is about, what each person is to the person, the brothers and sisters in
    birth order, the events on each side of the family, the triangles and the
    relationship events by pair, one summary per conversation, and, with no note on what brought
    the person, the first conversation's opening read raw, so it reads nothing
    (R-0850)."""
    data = diagram.get_diagram_data()
    to, about = audience(diagram, data)
    system = get_agent_prompt(
        record=outline(data, diagram.version, to) + closed(data),
        today=clock.today(user.timezone).isoformat(),
        coverage=coverage.block(data),
    )
    events, _ = toolbox.call(ToolName.ReadEvents, {"fields": [ReadField.Words, ReadField.Notes]})
    content = case_report_rewrite() + about
    content += f"\n\nEVENTS\n{events}"
    support = held(data)
    if support:
        content += f"\n\n{HELD}\n{support}"
    content += family(data)
    content += f"\n\n{SUMMARIES}\n{summaries(diagram, meter)}"
    raw = opening(data, sessions(diagram)[0])
    if raw:
        content += f"\n\n{OPENING}\n{raw}"
    return system, [{"role": "user", "content": content}]


def wrote(diagram: Diagram, toolbox: Toolbox, calls: list) -> list[str]:
    """Each guess in through the coach's own tool, a refused one written down,
    and what was on a card written anew taken off it. The cards written, in
    order."""
    before = {q["id"] for q in toolbox.data.questions}
    _put(diagram, toolbox, calls, retried=False)
    return _settled(diagram, toolbox, before)


def _put(diagram: Diagram, toolbox: Toolbox, calls: list, retried: bool,
         first: dict[str, str] | None = None) -> dict[str, str]:
    """Each guess in through the coach's own tool unless it gives a cause or
    a why, speaks as the person, or the checks refuse it, every refusal written down with its card
    and, on the second try, what came of the first (`first`, by card). A card
    not saying whose reading it is is refused when it will be asked for again
    (`retried`), else kept and written down. Why each refused call was
    refused, as the model reads it."""
    refused = {}
    to = profile.addressed(diagram, toolbox.data)
    for call in calls:
        told = refusal = misspoken(call, to) or checked(call) or (unmarked(call, to) if retried else None)
        if refusal is None:
            told, _, refusal = run_call(toolbox, call)
            if not refusal:
                _kept(diagram.id, toolbox.turn_id, call, retried, first, to)
        if refusal:
            refused[call.id] = told
            card = call.args.get(CARD)
            _observe(diagram.id, toolbox.turn_id, ObservationKind.ToolRefused,
                     {"tool": call.name, "refusal": refusal, "retried": retried,
                      "reason": _reason(card or call.name, f"refused: {refusal}",
                                        first and first[card])})
    return refused


def _kept(diagram_id: int, turn_id: str, call, retried: bool, first: dict[str, str] | None,
          addressed: bool = True) -> None:
    """A card written though off its shape, written down: an Executive
    Summary past its sentences, or, with no try left, a card not saying whose
    reading it is (R-0850)."""
    count = overlong(call)
    if count:
        _observe(diagram_id, turn_id, ObservationKind.ToolRefused,
                 {"tool": call.name, "refusal": f"the Executive Summary has {count} sentences, "
                  f"more than {SUMMARY_SENTENCES}; kept", "retried": retried, "sentences": count,
                  "reason": _reason(CaseReportCard.MainGuess.value, f"kept: {count} sentences")})
    whose = not retried and unmarked(call, addressed)
    if whose:
        card = call.args.get(CARD)
        _observe(diagram_id, turn_id, ObservationKind.ToolRefused,
                 {"tool": call.name, "refusal": f"{whose}; kept", "retried": retried,
                  "reason": _reason(card, f"kept: {whose}", first and first.get(card))})


def _reason(card: str, came: str, first: str | None = None) -> str:
    """An observation's reason: the card, what came of it, and on the second
    try what came of the first, refused with its reason or missing (R-0850)."""
    said = f"case report rewrite: {card}: {came}"
    return f"{said}; first try: {first}" if first else said


def _absent(diagram_id: int, turn_id: str, card: str, retried: bool,
            first: str | None = None) -> None:
    _observe(diagram_id, turn_id, ObservationKind.ToolRefused,
             {"tool": ToolName.AddImpression.value, "refusal": f"no {card} card given",
              "retried": retried, "reason": _reason(card, "missing", first)})


def _asked(data: DiagramData, card: CaseReportCard) -> int:
    """How many guesses a rewrite asks for on a card: one, or on each parent's
    family one a side for each of the person's parents in the diagram (R-0866)."""
    if card is CaseReportCard.Sides:
        return min(max(len(coverage.sides(data)), 1), record.CARD_HOLDS[card])
    return 1


def _missing(toolbox: Toolbox, before: set[str]) -> list[str]:
    """The cards given fewer guesses since the rewrite began than it asks for."""
    written = Counter(q.get(CARD) for q in toolbox.data.questions if q["id"] not in before)
    return [card.value for card in CARDS if written[card.value] < _asked(toolbox.data, card)]


def _settled(diagram: Diagram, toolbox: Toolbox, before: set[str]) -> list[str]:
    """What was on a card written anew taken off it, unless the card is still
    short of what was asked, so a side not given again keeps its note. The
    cards written, in order."""
    after = toolbox.data.questions
    new = [q for q in after if q["id"] not in before and q.get(CARD)]
    cards = list(dict.fromkeys(q[CARD] for q in new))
    short = set(_missing(toolbox, before))
    off = [
        {"item_kind": ItemKind.Question.value, "item_id": q["id"], "field": CARD, "after": None}
        for q in after
        if q.get(CARD) in cards and q.get(CARD) not in short and q["id"] not in {n["id"] for n in new}
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


def _again(turn, refused: dict[str, str], missing: list[str]) -> list[dict]:
    """The model's answer, what each call came to, and the cards it did not
    give: a refused card is given again, a missing one now."""
    results = [
        {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": f"refused: {refused[call.id]}; give this card again" if call.id in refused else "kept",
            "is_error": call.id in refused,
        }
        for call in turn.calls
    ]
    if missing:
        results.append({"type": "text", "text": (
            f"Not given: {', '.join(missing)}. Give each now; leave one out again only when "
            "nothing on the diagram could rest under it."
        )})
    return [{"role": "assistant", "content": turn.blocks}, {"role": "user", "content": results}]


def rewrite(diagram: Diagram, meter: Metered, user: User, turn_id: str) -> list[str]:
    """One model call writes every card again (R-0825, R-0850). A card
    refused (a cause or a why, the person's voice outside quotation marks, a
    prediction off what to work on, not saying whose reading it is, a mark
    inside a line, an id in its words, or the coach's tool) and a card not
    given are asked for once more; given again with a cause or in the
    person's voice, a card is written with those sentences taken out, given
    again not saying whose reading it is, it is written and written down, and
    one still refused or missing keeps what it had, written down (R-0850,
    R-0860).
    Cards read from a family that changed during a call are not written, so
    the report stays out of date (R-0826)."""
    toolbox = box(diagram, user, turn_id)
    before = {q["id"] for q in toolbox.data.questions}
    version = diagram.version
    system, messages = asked(diagram, user, toolbox, meter)
    turn = _called(diagram, meter, system, messages, turn_id)
    _unmoved(diagram, version)
    refused = _put(diagram, toolbox, turn.calls, retried=True)
    first = {c.args.get(CARD): f"refused: {refused[c.id]}" for c in turn.calls if c.id in refused}
    missing = _missing(toolbox, before)
    for card in missing:
        if card not in first:
            _absent(diagram.id, turn_id, card, retried=True)
            first[card] = "missing"
    if first:
        again = set(first)
        version = diagram.version
        retry = _called(diagram, meter, system, messages + _again(turn, refused, missing), turn_id)
        _unmoved(diagram, version)
        calls = [c for c in retry.calls if c.args.get(CARD) in again]
        to = profile.addressed(diagram, toolbox.data)
        for call in calls:
            if misspoken(call, to):
                text = call.args.get("text") or ""
                call.args = {**call.args, "text": record.plain(text) if to else uncaused(text)}
        given = [c for c in calls if c.args.get("text")]
        twice = _put(diagram, toolbox, given, retried=False, first=first)
        written = {c.args.get(CARD) for c in given if c.id in twice}
        for card in _missing(toolbox, before):
            if card not in written:
                _absent(diagram.id, turn_id, card, retried=False, first=first[card])
    return _settled(diagram, toolbox, before)


def _unmoved(diagram: Diagram, version: int) -> None:
    db.session.refresh(diagram)
    if diagram.version != version:
        raise Moved(f"diagram {diagram.id} moved from version {version} to {diagram.version}")


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
        _taken_back(diagram_id, turn_id)
        return _end(diagram_id, turn_id, {"type": TurnEventKind.Failed.value, "message": MOVED})
    except Refusal as refused:
        db.session.rollback()
        _taken_back(diagram_id, turn_id)
        _observe(diagram_id, turn_id, ObservationKind.TurnDeclined,
                 {"category": refused.category, "reason": f"case report rewrite: {refused.category}"})
        return _end(diagram_id, turn_id, {"type": TurnEventKind.Refused.value, "message": REFUSED})
    # The one router in this task: the page is told it ended, and the error goes on.
    except Exception as error:
        db.session.rollback()
        _taken_back(diagram_id, turn_id)
        _observe(diagram_id, turn_id, ObservationKind.TurnFailed,
                 {"error": f"{type(error).__name__}: {error}",
                  "reason": f"case report rewrite: {type(error).__name__}"})
        _end(diagram_id, turn_id, {"type": TurnEventKind.Failed.value, "message": BROKE})
        raise
    TokenMeter.charge(user_id, meter.spent)
    cleared(diagram, cards)
    db.session.commit()
    db.session.refresh(diagram)
    return _end(
        diagram_id,
        turn_id,
        {"type": TurnEventKind.Done.value, "turn_id": turn_id, "cards": cards, "version": diagram.version},
    )


def cleared(diagram: Diagram, cards: list[str]) -> None:
    """Cards written anew take off the out-of-date mark the catch-up put on
    the report (R-0772)."""
    if cards:
        diagram.case_report_forced_out_of_date = False


def _taken_back(diagram_id: int, turn_id: str) -> None:
    """A rewrite that fails leaves the cards as they were: what the first
    answer wrote before the second failed is taken back, and counts for
    nothing in whether the report is out of date (R-0825, R-0850)."""
    ids = [c.id for c in Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id)]
    if ids:
        record.undo_changes(diagram_id, ids, author=Author.Coach)


def _end(diagram_id: int, turn_id: str, event: dict) -> dict:
    turnlog.append(turn_id, event)
    turnlog.release(diagram_id, turn_id)
    return event
