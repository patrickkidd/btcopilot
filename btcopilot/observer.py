"""What a coach turn left behind that looks like a mistake, written down once
the turn ends. It changes nothing and refuses nothing: the coach has to see
repeats for itself, and each row is a candidate case for its regression evals
[Oracle: R-0481, R-0482].
"""

import re

from btcopilot import profile, record, turnstore, tuning
from btcopilot.coachturn import MAX_STEPS
from btcopilot.extensions import db
from btcopilot.models import Change, Discussion, Observation, ObservationKind, Statement
from btcopilot.recordtext import date_text
from btcopilot.schema import DiagramData, ItemKind
from btcopilot.toolbox import CHANGES, READS, ToolName
from btcopilot.toolnames import SUBJECT
from btcopilot.turnlog import TurnEventKind

# An asked question is stored self-contained, so its words may reword the
# reply's ("How old are Ada's brothers now?" for "And how old are they now?").
# Below this share of the question's words found in the reply, the two are
# written down as possibly different questions.
QUESTION_OVERLAP = 0.5
WORDS = re.compile(r"[\w']+")

# What this watcher writes, so a resumed turn replaces only these. How the turn
# ended is written where it ended, and stays.
WATCHED = (
    ObservationKind.DuplicatePerson,
    ObservationKind.DuplicateEvent,
    ObservationKind.AddWithoutRead,
    ObservationKind.QuestionUnsaid,
    ObservationKind.ToolRefused,
    ObservationKind.StepCap,
    ObservationKind.EarlierEdit,
)

ADDS = (
    ToolName.EditPerson,
    ToolName.EditPairBond,
    ToolName.EditEvent,
    ToolName.EditCluster,
)


def observe(diagram_id: int, turn_id: str, data: DiagramData) -> None:
    """Only what the turn touched is looked at, so an old repeat is written
    down once, against the turn that made it. A resumed turn is looked at
    whole again, so its rows replace those of the attempt that failed."""
    Observation.query.filter(
        Observation.turn_id == turn_id, Observation.kind.in_(WATCHED)
    ).delete()
    changed = {
        (delta["item_kind"], delta["item_id"])
        for change in Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id)
        for delta in change.deltas
    }
    events = {
        e["id"] for e in data.events if (ItemKind.Event.value, e["id"]) in changed
    }
    people = {item_id for kind, item_id in changed if kind == ItemKind.Person.value} | {
        e.get("child") for e in data.events if e["id"] in events
    }
    kept = turnstore.kept({turn_id}).get(turn_id, [])
    found = [
        *_same(
            ObservationKind.DuplicatePerson,
            data.people,
            people,
            lambda p: _person(data, p),
        ),
        *_same(ObservationKind.DuplicateEvent, data.events, events, record.twin_key),
        *_unread(kept),
        *_unsaid(diagram_id, turn_id, data),
        *_refused(kept),
        *_capped(kept),
        *_earlier(diagram_id, turn_id, kept),
    ]
    for kind, detail in found:
        db.session.add(
            Observation(
                diagram_id=diagram_id, turn_id=turn_id, kind=kind, detail=detail
            )
        )


def _same(kind: ObservationKind, items: list[dict], touched: set, key) -> list:
    groups: dict[tuple, list] = {}
    for item in items:
        same = key(item)
        if same is not None:
            groups.setdefault(same, []).append(item["id"])
    return [
        (kind, {"ids": ids, "same": list(same)})
        for same, ids in groups.items()
        if len(ids) > 1 and touched & set(ids)
    ]


def _person(data: DiagramData, person: dict) -> tuple | None:
    name = " ".join(p for p in (person.get("name"), person.get("last_name")) if p)
    if not name:
        return None
    born = profile.birth(data, person["id"])
    day = date_text(born["dateTime"]) if born else None
    return name.lower(), day and day[:4]


def overlap(question: str, reply: str) -> float:
    """The share of the question's distinct words, ignoring case, punctuation
    and which apostrophe was typed, that the reply also uses."""
    asked = _words(question)
    return len(asked & _words(reply)) / len(asked)


def _words(text: str) -> set[str]:
    return set(WORDS.findall(text.lower().replace("\u2019", "'")))


def _unsaid(diagram_id: int, turn_id: str, data: DiagramData) -> list:
    """Questions the turn asked whose words its reply hardly shares."""
    reply = (
        Statement.query.join(Discussion)
        .filter(
            Statement.turn_id == turn_id,
            Statement.speaker_id == Discussion.chat_ai_speaker_id,
        )
        .one_or_none()
    )
    if reply is None:
        return []
    asked = {
        str(delta["item_id"])
        for change in Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id)
        for delta in change.deltas
        if delta["item_kind"] == ItemKind.Question.value and record.asks(delta)
    }
    return [
        (
            ObservationKind.QuestionUnsaid,
            {"question": q["id"], "overlap": round(overlap(q["text"], reply.text), 2)},
        )
        for q in data.questions
        if q["id"] in asked
        and record.note(q) is not record.TODO
        and overlap(q["text"], reply.text) < QUESTION_OVERLAP
    ]


def _unread(kept: list[dict]) -> list:
    """Adds made before the turn's first read: the coach added without
    looking at what the record already holds."""
    adds = []
    for event in kept:
        if event["type"] != TurnEventKind.ToolCall.value:
            continue
        if event["name"] in READS:
            break
        if (
            event["name"] in ADDS
            and event["args"].get("id") is None
            and not event.get("refusal")
        ):
            adds.append({"name": event["name"], "args": event["args"]})
    return [(ObservationKind.AddWithoutRead, {"calls": adds})] if adds else []


def _refused(kept: list[dict]) -> list:
    """Each call the record refused, and whether the coach made the same tool
    work later in the turn."""
    # calls kept before 2026-09-24 carry no refusal field
    calls = [
        dict(e, refusal=e.get("refusal"))
        for e in kept
        if e["type"] == TurnEventKind.ToolCall.value
    ]
    return [
        (
            ObservationKind.ToolRefused,
            {
                "tool": call["name"],
                "refusal": call["refusal"],
                "retried": any(
                    later["name"] == call["name"] and later["refusal"] is None
                    for later in calls[i + 1 :]
                ),
                "reason": f"{call['name']}: {tuning.reason(call['refusal'])}",
            },
        )
        for i, call in enumerate(calls)
        if call["refusal"] is not None
    ]


def _capped(kept: list[dict]) -> list:
    """The coach used every tool step it had since the turn last failed, so it
    was made to stop and answer."""
    since = [TurnEventKind.Failed.value] + [e["type"] for e in kept]
    last = len(since) - since[::-1].index(TurnEventKind.Failed.value)
    steps = since[last:].count(TurnEventKind.Step.value)
    return [(ObservationKind.StepCap, {"steps": steps})] if steps >= MAX_STEPS else []


def _earlier(diagram_id: int, turn_id: str, kept: list[dict]) -> list:
    """Edit calls on items made before this sitting began: how often the coach
    goes back over what an earlier sitting put down, for tuning (R-0517)."""
    sitting = Statement.query.filter_by(turn_id=turn_id).first().discussion
    made = {
        (delta["item_kind"], str(delta["item_id"]))
        for change in Change.query.filter(
            Change.diagram_id == diagram_id, Change.created_at >= sitting.created_at
        )
        for delta in change.deltas
        if delta["field"] is None and delta["after"] is not None
    }
    calls = [
        {"name": e["name"], "item": list(item)}
        for e in kept
        if e["type"] == TurnEventKind.ToolCall.value
        and not e.get("refusal")
        and (item := _item(e))
        and item not in made
    ]
    if not calls:
        return []
    return [(ObservationKind.EarlierEdit, {"count": len(calls), "calls": calls})]


def _item(call: dict) -> tuple | None:
    """What an edit call changes, when it names something already there."""
    args = call["args"]
    if call["name"] == ToolName.Remove:
        return args["item_kind"], str(args["item_id"])
    if call["name"] in CHANGES and args.get("id") is not None:
        return SUBJECT[call["name"]].value, str(args["id"])
    return None
