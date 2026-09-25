"""What a coach turn left behind that looks like a mistake, written down once
the turn ends. It changes nothing and refuses nothing: the coach has to see
repeats for itself, and each row is a candidate case for its regression evals
[Oracle: R-0481, R-0482].
"""

import re

from btcopilot import profile, record, turnstore
from btcopilot.extensions import db
from btcopilot.models import Change, Discussion, Observation, ObservationKind, Statement
from btcopilot.recordtext import date_text
from btcopilot.schema import DiagramData, ItemKind
from btcopilot.toolbox import READS, ToolName
from btcopilot.turnlog import TurnEventKind

# An asked question is stored self-contained, so its words may reword the
# reply's ("How old are Ada's brothers now?" for "And how old are they now?").
# Below this share of the question's words found in the reply, the two are
# written down as possibly different questions.
QUESTION_OVERLAP = 0.5
WORDS = re.compile(r"[\w']+")

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
    Observation.query.filter_by(turn_id=turn_id).delete()
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
    found = [
        *_same(
            ObservationKind.DuplicatePerson,
            data.people,
            people,
            lambda p: _person(data, p),
        ),
        *_same(ObservationKind.DuplicateEvent, data.events, events, record.twin_key),
        *_unread(turn_id),
        *_unsaid(diagram_id, turn_id, data),
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
        if q["id"] in asked and overlap(q["text"], reply.text) < QUESTION_OVERLAP
    ]


def _unread(turn_id: str) -> list:
    """Adds made before the turn's first read: the coach added without
    looking at what the record already holds."""
    adds = []
    for event in turnstore.kept({turn_id}).get(turn_id, []):
        if event["type"] != TurnEventKind.ToolCall.value:
            continue
        if event["name"] in READS:
            break
        if (
            event["name"] in ADDS
            and event["args"].get("id") is None
            and not event.get("refused")
        ):
            adds.append({"name": event["name"], "args": event["args"]})
    return [(ObservationKind.AddWithoutRead, {"calls": adds})] if adds else []
