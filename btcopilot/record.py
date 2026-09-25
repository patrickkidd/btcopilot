"""The one write path onto a diagram's record.

Every mutation of the record goes through `apply`: it locks the diagram row, sets
the fields, and writes the Change row in the same transaction, so the log can
never disagree with the record. `undo` replays a turn backwards with a
compare-and-set on each value.
"""

import logging
import re

from sqlalchemy import update as sql_update

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Statement
from btcopilot.prompts import Role
from btcopilot.models import Diagram
from btcopilot.schema import (
    ITEM_COLLECTIONS,
    MIN_CLUSTER_EVENTS,
    EventKind,
    ItemKind,
    QuestionKind,
    QuestionOutcome,
    QuestionState,
    RelationshipKind,
    VariableShift,
)

_log = logging.getLogger(__name__)


def next_id(data) -> int:
    """The first id no person, event, bond or emotion on the record holds. The
    counter alone is not trusted: a record written without it, or behind its
    own items, would hand out an id that renames somebody instead of adding
    them."""
    used = [
        item["id"]
        for collection in (data.people, data.events, data.pair_bonds, data.emotions)
        for item in collection
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    return max(used + [data.lastItemId or 0]) + 1


def next_key(prefix: str, taken: set[str]) -> str:
    """The first free id of a kind keyed by a letter and a number: c3, q4."""
    n = len(taken) + 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


class Invalid(Exception):
    """The record the deltas would leave behind breaks a rule of the data model.
    The reason is for the coach; `plain` says the same rule to a person editing
    by hand, with no ids and no field names."""

    def __init__(self, reason: str, plain: str):
        super().__init__(reason)
        self.plain = plain


# A question is closed, never removed (R-0006): what the user declined has to
# stay where the coach can see it.
NEVER_REMOVED = ("a question is never removed; close it", "A question is never removed.")
GONE = "That is not in the record."


class Conflict(Exception):
    """A delta's expected `before` did not match what the record holds."""

    def __init__(self, delta, actual):
        self.delta = delta
        self.actual = actual
        super().__init__(
            f"expected {delta['before']!r} at {delta['item_kind']} "
            f"{delta['item_id']}.{delta['field']}, found {actual!r}"
        )


def apply(
    diagram_id: int,
    deltas: list[dict],
    *,
    author: Author,
    turn_id: str,
    user_id: int | None = None,
    session_id: str | None = None,
    statement_id: int | None = None,
) -> Change:
    """Set each delta's `after` on the record and log the command.

    Each delta is {item_kind, item_id, field, after}; `before` is read from the
    record so the log is always true, and any `before` passed in is ignored.
    Values are in the record's own tagged JSON form (see btcopilot.diagramjson).

    A delta with field None and after None removes the item, cascading the way
    the app's own scene does, and logs `before` as the whole item so undo puts
    it back. A field set on an id the record does not hold makes the item, and
    is logged as one add holding the whole item, so undo takes it off.
    """
    diagram = _lock(diagram_id)
    data = diagramjson.loads(diagram.data)
    applied = [d for delta in deltas for d in _apply(data, delta)]
    return _commit(
        diagram,
        data,
        compress(applied),
        author,
        turn_id,
        user_id,
        session_id,
        statement_id,
    )


def undo(
    diagram_id: int,
    turn_id: str,
    *,
    author: Author,
    user_id: int | None = None,
    session_id: str | None = None,
) -> Change:
    """Reverse every delta of `turn_id`, newest first, and log the reversal."""
    diagram = _lock(diagram_id)
    changes = (
        Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id)
        .order_by(Change.id.desc())
        .all()
    )
    if not changes:
        raise ValueError(f"no changes for turn {turn_id} on diagram {diagram_id}")

    data = diagramjson.loads(diagram.data)
    applied = []
    for change in changes:
        # A question is put back only where a removal closed it.
        removal = any(_removes(delta) for delta in change.deltas)
        for delta in reversed(change.deltas):
            if delta["item_kind"] == ItemKind.Question.value and not removal:
                continue
            inverse = _inverse(delta)
            actual = _get(data, inverse)
            if actual != inverse["before"]:
                raise Conflict(inverse, actual)
            done = _apply(data, inverse)
            # Taking off what the turn made would also take what hangs on it
            # since, which the turn did not make.
            if inverse["field"] is None and inverse["after"] is None and len(done) > 1:
                raise Conflict(inverse, [f"{d['item_kind']} {d['item_id']}" for d in done[:-1]])
            applied.extend(done)
    return _commit(
        diagram,
        data,
        compress(applied),
        author,
        f"undo:{turn_id}",
        user_id,
        session_id,
        None,
        undoing=True,
    )


def rewind(data: dict, deltas: list[dict]):
    """Take one change row's logged deltas back off the record, newest first,
    one for one: a removal's cascade is logged delta by delta, so nothing here
    cascades. A thing the row made comes off whole, whether it was logged as one
    add or, as rows written before adds were logged whole did, as field sets on
    a new id, which once taken back leave it holding nothing but that id."""
    for delta in reversed(deltas):
        if delta["field"] is not None:
            _set(data, _inverse(delta))
        elif delta["after"] is None:
            _restore(data, _inverse(delta))
        else:
            _drop(data, ItemKind(delta["item_kind"]), delta["item_id"])
    for kind, item_id in {
        (ItemKind(d["item_kind"]), str(d["item_id"]))
        for d in deltas
        if d["field"] is not None and d["item_kind"] != ItemKind.Diagram.value
    }:
        item = _find(data, kind, item_id)
        if all(value is None for field, value in item.items() if field != "id"):
            _collection(data, kind).remove(item)


def _inverse(delta: dict) -> dict:
    return dict(delta, before=delta["after"], after=delta["before"])


def compress(deltas: list[dict]) -> list[dict]:
    """Collapse consecutive deltas on the same item and field, first before and
    last after, and fold the field sets that follow an item's add into that
    add, so a thing made is logged whole."""
    out = []
    made = {}
    for delta in deltas:
        key = (delta["item_kind"], str(delta["item_id"]))
        if delta["field"] is None:
            made.pop(key, None)
        elif key in made:
            made[key]["after"] = {**made[key]["after"], delta["field"]: delta["after"]}
            continue
        if out and (out[-1]["item_id"], out[-1]["item_kind"], out[-1]["field"]) == (
            delta["item_id"],
            delta["item_kind"],
            delta["field"],
        ):
            out[-1] = dict(out[-1], after=delta["after"])
        else:
            out.append(dict(delta))
        if delta["field"] is None and out[-1]["before"] is None:
            made[key] = out[-1]
    return out


def _lock(diagram_id: int) -> Diagram:
    return (
        db.session.query(Diagram)
        .filter(Diagram.id == diagram_id)
        .with_for_update()
        .one()
    )


def _collection(data: dict, kind: ItemKind) -> list[dict]:
    return data.setdefault(ITEM_COLLECTIONS[kind], [])


def _find(data: dict, kind: ItemKind, item_id) -> dict | None:
    for item in _collection(data, kind):
        if str(item.get("id")) == str(item_id):
            return item
    return None


def _item(data: dict, delta: dict) -> dict:
    kind = ItemKind(delta["item_kind"])
    if kind is ItemKind.Diagram:
        return data
    item = _find(data, kind, delta["item_id"])
    if item is None:
        item = {"id": delta["item_id"]}
        _collection(data, kind).append(item)
    return item


def _delta(delta: dict, before, after) -> dict:
    return {
        "item_id": delta["item_id"],
        "item_kind": ItemKind(delta["item_kind"]).value,
        "field": delta["field"],
        "before": before,
        "after": after,
    }


def _get(data: dict, delta: dict):
    kind = ItemKind(delta["item_kind"])
    if delta["field"] is None:
        return diagramjson.to_json(_find(data, kind, delta["item_id"]))
    return diagramjson.to_json(_item(data, delta).get(delta["field"]))


def _apply(data: dict, delta: dict) -> list[dict]:
    kind = ItemKind(delta["item_kind"])
    if delta["field"] is not None:
        if kind is ItemKind.Diagram or _find(data, kind, delta["item_id"]) is not None:
            return [_set(data, delta)]
        made = dict(delta, field=None, after={"id": delta["item_id"]})
        return [_restore(data, made), _set(data, delta)]
    if kind is ItemKind.Diagram:
        raise ValueError("the diagram itself cannot be removed by a delta")
    if delta["after"] is None:
        if kind is ItemKind.Question:
            raise Invalid(*NEVER_REMOVED)
        return _remove(data, kind, delta["item_id"])
    return [_restore(data, delta)]


def _set(data: dict, delta: dict) -> dict:
    item = _item(data, delta)
    before = diagramjson.to_json(item.get(delta["field"]))
    item[delta["field"]] = diagramjson.from_json(delta["after"])
    return _delta(delta, before, delta["after"])


def _restore(data: dict, delta: dict) -> dict:
    kind = ItemKind(delta["item_kind"])
    if _find(data, kind, delta["item_id"]) is not None:
        raise ValueError(f"{kind.value} {delta['item_id']} is already in the record")
    _collection(data, kind).append(diagramjson.from_json(delta["after"]))
    return _delta(delta, None, delta["after"])


def _drop(data: dict, kind: ItemKind, item_id) -> dict:
    item = _find(data, kind, item_id)
    if item is None:
        raise ValueError(f"no {kind.value} {item_id} in the record")
    _collection(data, kind).remove(item)
    return {
        "item_id": item_id,
        "item_kind": kind.value,
        "field": None,
        "before": diagramjson.to_json(item),
        "after": None,
    }


def _remove(data: dict, kind: ItemKind, item_id) -> list[dict]:
    """Remove an item and everything the app's scene removes along with it.

    Mirrors Scene._do_removeItem: a person takes their events, the emotions
    naming them, and their pair bonds; a pair bond orphans its children; an
    event takes the emotions it caused. A question about the item is let go
    and loses its link, since a question is never removed.
    """
    deltas = []
    for question in _collection(data, ItemKind.Question):
        if question.get("item_kind") == kind.value and str(question.get("item_id")) == str(item_id):
            fields = {"item_kind": None, "item_id": None}
            if question["state"] != QuestionState.Resolved:
                fields.update(state=QuestionState.Resolved.value, outcome=QuestionOutcome.LetGo.value)
            deltas += [
                _set(
                    data,
                    {"item_kind": ItemKind.Question, "item_id": question["id"], "field": f, "after": v},
                )
                for f, v in fields.items()
            ]
    if kind is ItemKind.Person:
        for event in [
            e for e in _collection(data, ItemKind.Event) if involves(e, item_id)
        ]:
            deltas += _remove(data, ItemKind.Event, event["id"])
        for emotion in [
            e
            for e in _collection(data, ItemKind.Emotion)
            if str(e.get("person")) == str(item_id) or str(e.get("target")) == str(item_id)
        ]:
            deltas.append(_drop(data, ItemKind.Emotion, emotion["id"]))
        for bond in [
            b
            for b in _collection(data, ItemKind.PairBond)
            if str(b.get("person_a")) == str(item_id)
            or str(b.get("person_b")) == str(item_id)
        ]:
            deltas += _remove(data, ItemKind.PairBond, bond["id"])
    elif kind is ItemKind.PairBond:
        for child in _collection(data, ItemKind.Person):
            if str(child.get("parents")) == str(item_id):
                deltas.append(
                    _set(
                        data,
                        {
                            "item_kind": ItemKind.Person,
                            "item_id": child["id"],
                            "field": "parents",
                            "after": None,
                        },
                    )
                )
    elif kind is ItemKind.Event:
        for emotion in [
            e
            for e in _collection(data, ItemKind.Emotion)
            if str(e.get("event")) == str(item_id)
        ]:
            deltas.append(_drop(data, ItemKind.Emotion, emotion["id"]))
    deltas.append(_drop(data, kind, item_id))
    return deltas


def involves(event: dict, person_id) -> bool:
    """Scene's Event.people(): the person is one of the event's roles."""
    ids = [event.get("person"), event.get("spouse"), event.get("child")]
    ids += event.get("relationshipTargets") or []
    ids += event.get("relationshipTriangles") or []
    return any(str(x) == str(person_id) for x in ids if x is not None)


def _removes(delta: dict) -> bool:
    return delta["field"] is None and delta["after"] is None


def _validate(data: dict, deltas: list[dict], author: Author, undoing: bool):
    """Every cluster this write leaves behind holds at least MIN_CLUSTER_EVENTS
    events.

    Checked here because `_commit` is the one function every writer reaches --
    `apply`, `undo`, the coach's tools and the regrouping pass -- and checked on
    the assembled item rather than the delta, because a cluster's fields arrive
    as separate deltas and only the item says how many events it ends up
    holding. A write answers for the clusters it touches, not for the ones it
    inherited.
    """
    small = []
    for cluster_id in dict.fromkeys(
        str(delta["item_id"])
        for delta in deltas
        if delta["item_kind"] == ItemKind.Cluster.value
    ):
        cluster = _find(data, ItemKind.Cluster, cluster_id)
        if cluster and len(cluster.get("eventIds") or []) < MIN_CLUSTER_EVENTS:
            small.append(cluster_id)
    if small:
        raise Invalid(
            f"that would leave clusters {small} with fewer than {MIN_CLUSTER_EVENTS} "
            "events: add an event to the cluster, or remove the grouping",
            f"A cluster needs at least {MIN_CLUSTER_EVENTS} events.",
        )
    _words(data, deltas)
    _moves(data, deltas)
    _twins(data, deltas)
    _people(data, deltas)
    _structure(data, deltas)
    # What a removal or an undo does to a question is the record's own doing.
    if not undoing and not any(_removes(delta) for delta in deltas):
        _questions(data, deltas, author)


LINKS = (
    ("person", "person"),
    ("spouse", "spouse"),
    ("child", "child"),
    ("relationshipTargets", "target"),
    ("relationshipTriangles", "third person"),
)


def _role(event: dict, person_id) -> str | None:
    for field, role in LINKS:
        value = event.get(field)
        ids = value if isinstance(value, list) else [value]
        if any(str(x) == str(person_id) for x in ids if x is not None):
            return role
    return None


VARIABLES = ("symptom", "anxiety", "functioning")
SHIFTS = {shift.value for shift in VariableShift}
RELATIONSHIPS = {relationship.value for relationship in RelationshipKind}
MATCH_LINKS = ("person", "spouse", "child", "relationshipTargets", "relationshipTriangles")


def _val(value):
    return getattr(value, "value", value)


def _touched(deltas: list[dict]) -> list[str]:
    return _touched_kind(deltas, ItemKind.Event)


def _moved(event: dict) -> bool:
    """The event says something moved: a variable went up, down or stayed the
    same, or a relationship took a direction."""
    if any(_val(event.get(field)) in SHIFTS for field in VARIABLES):
        return True
    return _val(event.get("relationship")) in RELATIONSHIPS


def _day(value) -> str | None:
    if not value:
        return None
    if hasattr(value, "toString"):
        return value.toString("yyyy-MM-dd") or None
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def _words(data: dict, deltas: list[dict]):
    """A moment's words are who and what (owner ruling, 2026-09-09): the
    description says what happened and never names a person the event already
    links, and a birth is about the child. Checked on the events this write
    touches, the way the cluster floor is."""
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        kind = getattr(event.get("kind"), "value", event.get("kind"))
        if (
            kind in (EventKind.Birth.value, EventKind.Adopted.value)
            and event.get("person") is not None
            and event.get("child") is None
        ):
            raise Invalid(
                f"event {event_id}: a birth is about the child: "
                "set child, not person",
                "A birth is about the child: choose who was born under Child.",
            )
        description = event.get("description") or ""
        if not description:
            continue
        for person in _collection(data, ItemKind.Person):
            role = _role(event, person.get("id"))
            if role is None:
                continue
            first = (person.get("name") or "").strip()
            full = f"{first} {(person.get('last_name') or '').strip()}".strip()
            for name in (full, first):
                if name and re.search(
                    rf"\b{re.escape(name)}\b", description, re.IGNORECASE
                ):
                    raise Invalid(
                        f"event {event_id}'s description names {name}, who is "
                        f"already its {role}; say what happened without the name",
                        f"The summary names {name}, who is already on this event. "
                        "Say what happened without the name.",
                    )


def _moves(data: dict, deltas: list[dict]):
    """A noted event says what happened, a shift says which way something
    moved, and an early birth says nothing but when someone was born (owner
    ruling R-0037). Checked on the events this
    write touches, the way the cluster floor is."""
    events = _collection(data, ItemKind.Event)
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        kind = _val(event.get("kind"))
        if kind == EventKind.Noted.value and not (event.get("description") or "").strip():
            raise Invalid(
                f"event {event_id} is a noted event with no words: say what "
                "happened",
                "A noted event needs a few words saying what happened.",
            )
        if kind == EventKind.Shift.value and not _moved(event):
            raise Invalid(
                f"event {event_id} is a shift with no variable and no "
                "relationship move: say which of symptom, anxiety, functioning "
                "or relationship moved, and which way",
                "A shift needs to say what moved and which way: symptom, anxiety, "
                "functioning or a relationship.",
            )
        end = _day(event.get("endDateTime"))
        if end and end < (_day(event.get("dateTime")) or end):
            raise Invalid(
                f"event {event_id} ends before it begins: date is when it began, "
                "end_date when it ended",
                "The end date is before the start date.",
            )
        if kind not in (EventKind.Birth.value, EventKind.Adopted.value):
            continue
        # early = before the first moment that moved anything: that is where
        # the diagnostic period starts (R-0038); births before it are scaffolding
        day = _day(event.get("dateTime"))
        days = [
            other_day
            for other in events
            if str(other.get("id")) != event_id
            and _moved(other)
            and (other_day := _day(other.get("dateTime")))
        ]
        if day and (not days or day < min(days)) and _moved(event):
            raise Invalid(
                f"event {event_id} is an early birth: it anchors age and "
                "carries no symptom, anxiety, functioning or relationship",
                "A birth before the first shift only says when someone was born: "
                "it carries no symptom, anxiety, functioning or relationship.",
            )


def _links(event: dict) -> tuple:
    out = []
    for field in MATCH_LINKS:
        value = event.get(field)
        if isinstance(value, list):
            out.append(tuple(sorted(str(x) for x in value if x is not None)))
        else:
            out.append(str(value) if value is not None else None)
    return tuple(out)


def _moves_of(event: dict) -> tuple:
    return tuple(_val(event.get(field)) for field in (*VARIABLES, "relationship"))


def twin_key(event: dict) -> tuple:
    """Two events are the same event when kind, day, people and what moved
    all match."""
    return (
        _val(event.get("kind")),
        _day(event.get("dateTime")),
        _links(event),
        _moves_of(event),
    )


def _twins(data: dict, deltas: list[dict]):
    """The same event is not written down twice: an event this write adds that
    matches one already in the record on kind, day, people and what moved is
    refused, naming the one that is there. Two shifts for one person on one day
    that move different variables are two events (R-0432)."""
    added = {
        str(delta["item_id"])
        for delta in deltas
        if delta["item_kind"] == ItemKind.Event.value
        and delta["field"] in (None, "kind")
        and delta["before"] is None
    }
    events = _collection(data, ItemKind.Event)
    for event_id in _touched(deltas):
        if event_id not in added:
            continue
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        for other in events:
            if str(other.get("id")) == event_id:
                continue
            if twin_key(other) == twin_key(event):
                raise Invalid(
                    f"that event is already event {other.get('id')}: change it "
                    f"with edit_event(id={other.get('id')}) rather than adding it",
                    "That event is already in the diagram. Change the one that is "
                    "there rather than adding it again.",
                )


def _touched_kind(deltas: list[dict], kind: ItemKind) -> list[str]:
    return list(
        dict.fromkeys(
            str(delta["item_id"])
            for delta in deltas
            if delta["item_kind"] == kind.value and delta["item_id"] is not None
        )
    )


def pair(bond: dict) -> tuple:
    return tuple(
        sorted(str(bond.get(side)) for side in ("person_a", "person_b"))
    )


#: The words people use for a role, as the record's own generic names spell it
#: (R-0429: "Sarah's mother", never beside "Sarah's Mum").
ROLE_WORDS = {
    "mother": Role.Mother,
    "mum": Role.Mother,
    "mom": Role.Mother,
    "mommy": Role.Mother,
    "mummy": Role.Mother,
    "mama": Role.Mother,
    "father": Role.Father,
    "dad": Role.Father,
    "daddy": Role.Father,
    "papa": Role.Father,
    "partner": Role.Partner,
}
GENERIC = re.compile(r"^(.+?)['\u2019]s\s+(\w+)$")


def generic_key(person: dict) -> tuple | None:
    """Whose what a generically named person is: ("sarah", Role.Mother) for
    "Sarah's Mum" and "Sarah's mother" alike."""
    match = GENERIC.match((person.get("name") or "").strip())
    if not match or match.group(2).lower() not in ROLE_WORDS:
        return None
    return match.group(1).strip().lower(), ROLE_WORDS[match.group(2).lower()]


def _people(data: dict, deltas: list[dict]):
    """One person is not written down twice under two words for the same role."""
    people = _collection(data, ItemKind.Person)
    for person_id in _touched_kind(deltas, ItemKind.Person):
        person = _find(data, ItemKind.Person, person_id)
        key = person and generic_key(person)
        if not key:
            continue
        for other in people:
            if str(other.get("id")) != person_id and generic_key(other) == key:
                raise Invalid(
                    f"{person['name']} is already person {other['id']} "
                    f"({other['name']}): use that person rather than adding another",
                    f"{person['name']} is already in the diagram as {other['name']}. "
                    "Use that person rather than adding another.",
                )


def _structure(data: dict, deltas: list[dict]):
    """Who belongs to whom, checked on what this write leaves behind.

    Nobody is their own parent or their own partner, a bond is between two
    different people who are both in the record, and any two people have one
    bond ever, because a child is the offspring of a bond rather than of a
    pairing written twice.
    """
    bonds = _collection(data, ItemKind.PairBond)
    for bond_id in _touched_kind(deltas, ItemKind.PairBond):
        bond = _find(data, ItemKind.PairBond, bond_id)
        if bond is None:
            continue
        sides = [bond.get("person_a"), bond.get("person_b")]
        if any(side is None for side in sides):
            raise Invalid(
                f"pair bond {bond_id} needs two people: add the missing one as a "
                "person first, generically named where nobody named them",
                "A pair-bond needs two people.",
            )
        if str(sides[0]) == str(sides[1]):
            raise Invalid(
                f"pair bond {bond_id} is one person with themselves",
                "A pair-bond needs two different people.",
            )
        for side in sides:
            if _find(data, ItemKind.Person, side) is None:
                raise Invalid(
                    f"pair bond {bond_id} names person {side}, who is not in the record",
                    "One of those two is no longer in the diagram.",
                )
        for other in bonds:
            if str(other.get("id")) != str(bond_id) and pair(other) == pair(bond):
                raise Invalid(
                    f"those two already have pair bond {other.get('id')}: change "
                    f"it with edit_pair_bond(id={other.get('id')}) rather than "
                    "adding a second one",
                    "Those two already have a pair-bond. Change that one rather "
                    "than adding a second.",
                )

    for person_id in _touched_kind(deltas, ItemKind.Person):
        person = _find(data, ItemKind.Person, person_id)
        if person is None or person.get("parents") is None:
            continue
        bond = _find(data, ItemKind.PairBond, person["parents"])
        if bond is None:
            raise Invalid(
                f"person {person_id} is born to pair bond {person['parents']}, "
                "which is not in the record",
                "Those parents are no longer in the diagram.",
            )
        if str(person_id) in pair(bond):
            raise Invalid(
                f"person {person_id} cannot be their own parent",
                "Nobody can be their own parent.",
            )


QUESTION_LINKS = (ItemKind.Person, ItemKind.PairBond, ItemKind.Event, ItemKind.Cluster)
QUESTION_ORDER = list(QuestionState)


def normal(text: str) -> str:
    return " ".join(text.lower().split())


def _questions(data: dict, deltas: list[dict], author: Author):
    """A question has words, moves only forward from held to asked to
    resolved, says how it ended exactly when it is resolved, is kept once in
    the same words, and is dismissed by the user alone, who writes nothing else
    on it (R-0006, R-0077)."""
    questions = _collection(data, ItemKind.Question)
    user = Author(author) is Author.User
    for question_id in _touched_kind(deltas, ItemKind.Question):
        question = _find(data, ItemKind.Question, question_id)
        mine = [
            d
            for d in deltas
            if d["item_kind"] == ItemKind.Question.value and str(d["item_id"]) == question_id
        ]
        state = QuestionState(_val(question.get("state")))
        outcome = question.get("outcome") and QuestionOutcome(_val(question["outcome"]))
        QuestionKind(_val(question.get("kind")))
        moved = [d for d in mine if d["field"] == "state"]
        added = any(d["field"] is None for d in mine)
        was = None if added else QuestionState(moved[0]["before"] if moved else state)
        if was is QuestionState.Resolved:
            raise Invalid(
                f"question {question_id} is already closed", "That question is already closed."
            )
        if moved and not added and QUESTION_ORDER.index(state) <= QUESTION_ORDER.index(was):
            if was is QuestionState.Asked:
                raise Invalid(
                    f"question {question_id} was already asked",
                    "That question was already asked.",
                )
            raise Invalid(
                f"question {question_id} is already held",
                "That question is already kept for later.",
            )
        if not (question.get("text") or "").strip():
            raise Invalid(f"question {question_id} has no words", "It gave the question no words.")
        if (state is QuestionState.Resolved) != bool(outcome):
            raise Invalid(
                f"question {question_id}: give an outcome exactly when it is resolved",
                "It did not say how the question ended.",
            )
        if (outcome is QuestionOutcome.DeclinedByUser) != user or (
            user and any(d["field"] not in ("state", "outcome") for d in mine)
        ):
            raise Invalid(
                f"only the user dismisses question {question_id}, and does nothing else to it",
                "Only you can dismiss a question.",
            )
        link = (question.get("item_kind"), question.get("item_id"))
        if (link[0] is None) != (link[1] is None):
            raise Invalid(
                f"question {question_id}: give item_kind and item_id together, or neither",
                "It named what the question is about only halfway.",
            )
        if link[0] is not None and (
            ItemKind(link[0]) not in QUESTION_LINKS
            or _find(data, ItemKind(link[0]), link[1]) is None
        ):
            raise Invalid(
                f"question {question_id} is about {link[0]} {link[1]}, which is not in the record",
                GONE,
            )
        for other in questions:
            if str(other.get("id")) == question_id or normal(other["text"]) != normal(
                question["text"]
            ):
                continue
            if other.get("outcome") == QuestionOutcome.DeclinedByUser:
                raise Invalid(
                    f"the user turned that question down as {other['id']}: never ask it again",
                    "The user already turned this question down.",
                )
            if other["state"] != QuestionState.Resolved:
                raise Invalid(
                    f"that question is already {other['id']}",
                    "That question is already there.",
                )


def _commit(
    diagram, data, deltas, author, turn_id, user_id, session_id, statement_id, undoing=False
) -> Change:
    _validate(data, deltas, author, undoing)
    version = db.session.execute(
        sql_update(Diagram)
        .where(Diagram.id == diagram.id)
        .values(
            data=diagramjson.encode(data, diagram.data), version=Diagram.version + 1
        )
        .returning(Diagram.version)
    ).scalar_one()
    change = Change(
        diagram_id=diagram.id,
        version=version,
        statement_id=statement_id,
        turn_id=turn_id,
        user_id=user_id,
        session_id=session_id,
        author=Author(author),
        deltas=deltas,
    )
    db.session.add(change)
    db.session.commit()
    db.session.expire(diagram)
    _log.info(
        f"Diagram {diagram.id} turn {turn_id} by {Author(author).value}: "
        f"{len(deltas)} deltas"
    )
    return change


def diff(old: dict, new: dict) -> list[dict]:
    """Deltas from one record blob to another, at item and field level."""
    deltas = []
    for kind, collection in ITEM_COLLECTIONS.items():
        by_id = {str(i.get("id")): i for i in old.get(collection) or []}
        for item in new.get(collection) or []:
            was = by_id.pop(str(item.get("id")), {})
            for field in set(item) | set(was):
                if item.get(field) != was.get(field):
                    deltas.append(
                        {
                            "item_id": item.get("id"),
                            "item_kind": kind.value,
                            "field": field,
                            "before": diagramjson.to_json(was.get(field)),
                            "after": diagramjson.to_json(item.get(field)),
                        }
                    )
        for was in by_id.values():
            for field in was:
                deltas.append(
                    {
                        "item_id": was.get("id"),
                        "item_kind": kind.value,
                        "field": field,
                        "before": diagramjson.to_json(was[field]),
                        "after": None,
                    }
                )
    return deltas


def _stated(diagram_id: int) -> tuple[list[Change], dict[int, int]]:
    """This diagram's change rows that carry a statement, oldest first, and
    the session each of those statements belongs to."""
    rows = (
        Change.query.filter(
            Change.diagram_id == diagram_id, Change.statement_id.isnot(None)
        )
        .order_by(Change.id)
        .all()
    )
    said = {
        statement.id: statement.discussion_id
        for statement in Statement.query.filter(
            Statement.id.in_({row.statement_id for row in rows})
        ).all()
    }
    return rows, said


def coded_in(diagram_id: int, kind: ItemKind = ItemKind.Event) -> dict[int, dict]:
    """Where each moment on this diagram was written down: the message the coach
    was saying when it went in, and the session that message belongs to. People
    and pair bonds trace the same way, and the kind asked for says which.

    The command log is the record of that. Every command carries the deltas it
    applied, and a coach turn stamps its own statement on the commands it made,
    so a moment traces to a message through the commands that named it. The
    newest such command wins: a moment changed twice belongs to the last thing
    said about it.
    """
    found: dict[int, dict] = {}
    rows, said = _stated(diagram_id)
    for row in rows:
        for delta in row.deltas or []:
            if delta.get("item_kind") != kind.value:
                continue
            try:
                item_id = int(delta["item_id"])
            except (KeyError, TypeError, ValueError):
                continue
            found[item_id] = {
                "discussion_id": said.get(row.statement_id),
                "statement_id": row.statement_id,
                "turn_id": row.turn_id,
            }
    return found


def asks(delta: dict) -> bool:
    if delta["field"] is None:
        return delta["after"].get("state") == QuestionState.Asked
    return delta["field"] == "state" and delta["after"] == QuestionState.Asked


def asked_in(diagram_id: int) -> dict[str, dict]:
    """The message each question was asked in, and its session: the newest
    change row whose delta made the question asked."""
    found = {}
    rows, said = _stated(diagram_id)
    for row in rows:
        for delta in row.deltas:
            if delta["item_kind"] == ItemKind.Question.value and asks(delta):
                found[str(delta["item_id"])] = {
                    "discussion_id": said[row.statement_id],
                    "statement_id": row.statement_id,
                }
    return found
