"""The one write path onto a diagram's record.

Every mutation of the record goes through `apply`: it locks the diagram row, sets
the fields, and writes the Change row in the same transaction, so the log can
never disagree with the record. `undo` replays a turn backwards with a
compare-and-set on each value.
"""

import contextlib
import enum
import logging
import re
from dataclasses import dataclass

from sqlalchemy import update as sql_update

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Statement
from btcopilot.prompts import Role
from btcopilot.models import Diagram
from btcopilot.schema import (
    ITEM_COLLECTIONS,
    CaseReportCard,
    LIST_FIELDS,
    MIN_CLUSTER_EVENTS,
    DateCertainty,
    EventKind,
    EvidenceKind,
    Fact,
    ItemKind,
    NotedFact,
    PersonKind,
    Pushback,
    QuestionKind,
    QuestionOutcome,
    QuestionState,
    RelationshipKind,
    TITLE_WORDS,
    VariableShift,
    parse_date,
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
    session_id: int | None = None,
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
    with _locked(diagram_id) as diagram:
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
    session_id: int | None = None,
) -> Change:
    """Reverse every delta of `turn_id`, newest first, and log the reversal."""
    with _locked(diagram_id) as diagram:
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
        _back(data, delta)
    for kind, item_id in {
        (ItemKind(d["item_kind"]), str(d["item_id"]))
        for d in deltas
        if d["field"] is not None and d["item_kind"] != ItemKind.Diagram.value
    }:
        item = _find(data, kind, item_id)
        if all(value in (None, []) for field, value in item.items() if field != "id"):
            _collection(data, kind).remove(item)


def _back(data: dict, delta: dict) -> dict:
    if delta["field"] is not None:
        return _set(data, _inverse(delta))
    if delta["after"] is None:
        return _restore(data, _inverse(delta))
    return _drop(data, ItemKind(delta["item_kind"]), delta["item_id"])


def taking_back(data: dict, changes: list[Change]) -> list[tuple[Change, list[dict]]]:
    """Each change row taken back off `data` one for one, newest first, with
    the deltas that logs; a value changed since it was written is a Conflict."""
    out = []
    for change in sorted(changes, key=lambda c: c.id, reverse=True):
        done = []
        for delta in reversed(change.deltas):
            inverse = _inverse(delta)
            actual = _get(data, inverse)
            if actual != inverse["before"]:
                raise Conflict(inverse, actual)
            done.append(_back(data, delta))
        out.append((change, done))
    return out


def undo_changes(
    diagram_id: int, ids: list[int], *, author: Author, user_id: int | None = None
) -> list[Change]:
    """Take these change rows back, newest first, each logged as its own
    change `undo:<turn>#<row id>` so the log names the row taken back. Unlike
    `undo`, which takes back a whole turn, it also takes off the questions and
    impressions a row added. Every row is checked before any is written."""
    changes = (
        Change.query.filter(Change.diagram_id == diagram_id, Change.id.in_(ids)).all()
    )
    missing = set(ids) - {change.id for change in changes}
    if missing:
        raise ValueError(f"no changes {sorted(missing)} on diagram {diagram_id}")
    taking_back(diagramjson.loads(db.session.get(Diagram, diagram_id).data), changes)
    out = []
    for change in sorted(changes, key=lambda c: c.id, reverse=True):
        with _locked(diagram_id) as diagram:
            data = diagramjson.loads(diagram.data)
            [(_, deltas)] = taking_back(data, [change])
            out.append(
                _commit(
                    diagram,
                    data,
                    deltas,
                    author,
                    f"undo:{change.turn_id}#{change.id}",
                    user_id,
                    change.session_id,
                    None,
                    undoing=True,
                )
            )
    return out


def undone(diagram_id: int) -> set[int]:
    """The ids of the change rows `undo_changes` took back."""
    rows = Change.query.filter(
        Change.diagram_id == diagram_id, Change.turn_id.like("undo:%#%")
    )
    return {int(row.turn_id.rpartition("#")[2]) for row in rows}


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


@contextlib.contextmanager
def _locked(diagram_id: int):
    """The record's row, locked until the write commits. A write the record
    refuses gives the lock back: the turn goes on after a refusal, and the
    ledger row of its next model call is written on its own connection, which
    would wait on this row for as long as the turn waits on it."""
    savepoint = db.session.begin_nested()
    try:
        yield _lock(diagram_id)
    except (Invalid, Conflict):
        savepoint.rollback()
        raise


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
    return diagramjson.to_json(_held(_item(data, delta), delta))


def _held(item: dict, delta: dict):
    """A field's value as the log states it: a list field left off the item
    is the empty list it reads as, so taking a later set back leaves a list."""
    empty = [] if delta["field"] in LIST_FIELDS.get(ItemKind(delta["item_kind"]), ()) else None
    return item.get(delta["field"], empty)


def _apply(data: dict, delta: dict) -> list[dict]:
    kind = ItemKind(delta["item_kind"])
    if delta["field"] is not None:
        if kind is ItemKind.Diagram or _find(data, kind, delta["item_id"]) is not None:
            return [_set(data, delta), *_carded(data, delta)]
        made = dict(delta, field=None, after={"id": delta["item_id"]})
        return [_restore(data, made), _set(data, delta), *_carded(data, delta)]
    if kind is ItemKind.Diagram:
        raise ValueError("the diagram itself cannot be removed by a delta")
    if delta["after"] is None:
        if kind is ItemKind.Question:
            raise Invalid(*NEVER_REMOVED)
        return _remove(data, kind, delta["item_id"])
    return [_restore(data, delta)]


# The case report card a guess or a question is on: the newest on a card
# replaces the one before it, except that up to three guesses are on what to
# work on and on the coach's guess (R-0709, R-0732).
CARD = "case_report_card"
CARD_HOLDS = {CaseReportCard.WorkOn: 3, CaseReportCard.CoachGuess: 3}
QUESTION_CARDS = (CaseReportCard.OwnPart, CaseReportCard.Choice)


def _carded(data: dict, delta: dict) -> list[dict]:
    """Taking a card off the entries that held it before, in the same change."""
    if delta["item_kind"] != ItemKind.Question.value or delta["field"] != CARD:
        return []
    card = delta["after"]
    if card is None:
        return []
    item = _item(data, delta)
    others = [
        q
        for q in _collection(data, ItemKind.Question)
        if q is not item and q.get(CARD) == card and note(q) is note(item)
    ]
    keep = CARD_HOLDS.get(CaseReportCard(card), 1) - 1
    return [
        _set(data, {"item_kind": ItemKind.Question, "item_id": q["id"], "field": CARD, "after": None})
        for q in others[: max(len(others) - keep, 0)]
    ]


def _set(data: dict, delta: dict) -> dict:
    item = _item(data, delta)
    before = diagramjson.to_json(_held(item, delta))
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
        fields = {}
        if question.get("item_kind") == kind.value and str(question.get("item_id")) == str(item_id):
            fields = {"item_kind": None, "item_id": None}
            if question.get("fact") is not None:
                fields["fact"] = None
            if question["state"] != QuestionState.Resolved:
                fields.update(state=QuestionState.Resolved.value, outcome=QuestionOutcome.LetGo.value)
        kept = [
            one
            for one in question.get("evidence") or []
            if (one["kind"], str(one["id"])) != (kind.value, str(item_id))
        ]
        if len(kept) != len(question.get("evidence") or []):
            fields["evidence"] = kept
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
        # a cluster holds only events in the record; one left under the floor
        # goes, and its events are dots again
        for cluster in list(_collection(data, ItemKind.Cluster)):
            ids = cluster.get("eventIds") or []
            kept = [i for i in ids if str(i) != str(item_id)]
            if len(kept) == len(ids):
                continue
            if len(kept) < MIN_CLUSTER_EVENTS:
                deltas += _remove(data, ItemKind.Cluster, cluster["id"])
            else:
                deltas.append(
                    _set(
                        data,
                        {
                            "item_kind": ItemKind.Cluster,
                            "item_id": cluster["id"],
                            "field": "eventIds",
                            "after": kept,
                        },
                    )
                )
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
    touched = [
        (cluster_id, cluster)
        for cluster_id in _touched_kind(deltas, ItemKind.Cluster)
        if (cluster := _find(data, ItemKind.Cluster, cluster_id)) is not None
    ]
    small = [
        cluster_id
        for cluster_id, cluster in touched
        if len(cluster.get("eventIds") or []) < MIN_CLUSTER_EVENTS
    ]
    if small:
        raise Invalid(
            f"that would leave clusters {small} with fewer than {MIN_CLUSTER_EVENTS} "
            "events: add an event to the cluster, or remove the grouping",
            f"A cluster needs at least {MIN_CLUSTER_EVENTS} events.",
        )
    for cluster_id, cluster in touched:
        for event_id in cluster.get("eventIds") or []:
            if _find(data, ItemKind.Event, event_id) is None:
                raise Invalid(
                    f"cluster {cluster_id} names event {event_id}, which is not in "
                    "the record: a cluster groups events the record holds",
                    "One of the events in that cluster is no longer in the diagram.",
                )
    _values(data, deltas)
    _words(data, deltas)
    _moves(data, deltas)
    _twins(data, deltas)
    _people(data, deltas)
    _structure(data, deltas)
    # What a removal or an undo does to a question is the record's own doing.
    if not undoing and not any(_removes(delta) for delta in deltas):
        _questions(data, deltas, author)


COUPLE_KINDS = {kind.value for kind in EventKind if kind.isCouple()}

MOVE_LINKS = (
    ("relationshipTargets", "target"),
    ("relationshipTriangles", "third person"),
)
LINKS = (("person", "person"), ("spouse", "spouse"), ("child", "child")) + MOVE_LINKS


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
KINDS = {kind.value for kind in EventKind}
OFFSPRING_KINDS = {kind.value for kind in EventKind if kind.isOffspring()}
WORDED_KINDS = (EventKind.Noted.value, EventKind.Shift.value)
# Words an editor leaves behind that say nothing about what happened.
PLACEHOLDERS = {"", "new event", "unknown"}
TRIANGLES = (RelationshipKind.Inside.value, RelationshipKind.Outside.value)
DATES = ("dateTime", "endDateTime")
#: Each closed field of an event, the values it may hold, and what they are called.
EVENT_SETS = (
    ("kind", KINDS, "event kinds"),
    *((field, SHIFTS, "shift directions") for field in VARIABLES),
    ("relationship", RELATIONSHIPS, "relationships"),
    ("dateCertainty", {c.value for c in DateCertainty}, "date certainties"),
    ("item", {f.value for f in NotedFact}, "items a noted event records"),
)
GENDERS = {kind.value for kind in PersonKind}


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


def _values(data: dict, deltas: list[dict]):
    """Every closed field holds one of its own values, and a person has a name.
    Checked on the items this write touches."""
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        for field, allowed, noun in EVENT_SETS:
            value = _val(event.get(field))
            if (value is not None or field == "kind") and value not in allowed:
                raise Invalid(
                    f"event {event_id}'s {field} is {value!r}, which is not one of "
                    f"the {noun}: {', '.join(sorted(allowed))}",
                    f"That event needs one of the {noun}.",
                )
    for person_id in _touched_kind(deltas, ItemKind.Person):
        person = _find(data, ItemKind.Person, person_id)
        if person is None:
            continue
        if not (person.get("name") or "").strip():
            raise Invalid(
                f"person {person_id} has no name: use the name as it was said, or "
                "whose relation they are where nobody named them",
                "A person needs a name.",
            )
        gender = _val(person.get("gender"))
        if gender is not None and gender not in GENDERS:
            raise Invalid(
                f"person {person_id}'s gender is {gender!r}, which is not one of the "
                f"genders: {', '.join(sorted(GENDERS))}",
                "That person needs one of the genders.",
            )
    for bond_id in _touched_kind(deltas, ItemKind.PairBond):
        bond = _find(data, ItemKind.PairBond, bond_id)
        if bond is not None and bond.get("married") not in (True, False, None):
            raise Invalid(
                f"pair bond {bond_id}'s married is {bond['married']!r}: it is true, "
                "false, or left out when nobody said",
                "Whether they married could not be read.",
            )


def _words(data: dict, deltas: list[dict]):
    """A moment's words are who and what (owner ruling, 2026-09-09): the title
    and the description say what happened and never name a person the event
    already links. Checked on the events this write touches, the way the
    cluster floor is."""
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        for field, plain in (("title", "title"), ("description", "summary")):
            named = linked_name(data, event, event.get(field) or "")
            if named:
                name, role = named
                raise Invalid(
                    f"event {event_id}'s {field} names {name}, who is already "
                    f"its {role}; say what happened without the name",
                    f"The {plain} names {name}, who is already on this event. "
                    "Say what happened without the name.",
                )


def linked_name(data: dict, event: dict, words: str) -> tuple[str, str] | None:
    """The name, and the role, of a person the event links whom its words name."""
    for person in _collection(data, ItemKind.Person):
        role = _role(event, person.get("id"))
        if role is None:
            continue
        first = (person.get("name") or "").strip()
        full = f"{first} {(person.get('last_name') or '').strip()}".strip()
        for name in (full, first):
            if name and re.search(rf"\b{re.escape(name)}\b", words, re.IGNORECASE):
                return name, role
    return None


def _moves(data: dict, deltas: list[dict]):
    """A noted event and a shift say in words what happened under a short
    title (R-0681), a shift says which way something moved, and only a shift
    carries a move: a birth, marriage or death is not itself a shift (R-0037,
    R-0364, R-0375). Dates are dates, and an event ends after it begins.
    Checked on the events this write touches, the way the cluster floor is."""
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        kind = _val(event.get("kind"))
        if kind in WORDED_KINDS and (event.get("description") or "").strip().lower() in PLACEHOLDERS:
            raise Invalid(
                f"event {event_id} is a {kind} event with no words: say what "
                "happened",
                f"A {EventKind(kind).menuLabel().lower()} event needs a few words "
                "saying what happened.",
            )
        if kind in WORDED_KINDS and not TITLE_WORDS[0] <= len(
            (event.get("title") or "").split()
        ) <= TITLE_WORDS[1]:
            raise Invalid(
                f"event {event_id} is a {kind} event and needs a title: a "
                f"complete phrase of {TITLE_WORDS[0]} to {TITLE_WORDS[1]} words "
                "saying what changed, such as 'Lost his job'",
                f"A {EventKind(kind).menuLabel().lower()} event needs a title of "
                f"{TITLE_WORDS[0]} to {TITLE_WORDS[1]} words, such as "
                "\"Lost his job\".",
            )
        if kind == EventKind.Shift.value and not _moved(event):
            raise Invalid(
                f"event {event_id} is a shift with no variable and no "
                "relationship move: say which of symptom, anxiety, functioning "
                "or relationship moved, and which way",
                "A shift needs to say what moved and which way: symptom, anxiety, "
                "functioning or a relationship.",
            )
        if kind != EventKind.Shift.value and _moved(event):
            raise Invalid(
                f"event {event_id} is a {kind} event, and only a shift carries "
                "symptom, anxiety, functioning or a relationship move: record "
                "what moved as a shift of its own, dated to it",
                "Only a shift carries symptom, anxiety, functioning or a "
                "relationship: record that as a shift of its own.",
            )
        if event.get("item") is not None and kind != EventKind.Noted.value:
            raise Invalid(
                f"event {event_id} is a {kind} event: only a noted event says "
                "which item of the basic data it records",
                "Only a noted event says it records schooling, work, health or "
                "where someone lived.",
            )
        for field in DATES:
            day = _day(event.get(field))
            if day and parse_date(day) is None:
                raise Invalid(
                    f"event {event_id}'s {field} {event.get(field)!r} is not a "
                    "date: give it as YYYY-MM-DD, the first of the month or the "
                    "year when only those are known",
                    "That date could not be read.",
                )
        end = _day(event.get("endDateTime"))
        if end and end < (_day(event.get("dateTime")) or end):
            raise Invalid(
                f"event {event_id} ends before it begins: date is when it began, "
                "end_date when it ended",
                "The end date is before the start date.",
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

    Nobody is their own parent, their own partner, or the target or third
    person of their own move, a bond is between two different people who are
    both in the record, and any two people have one bond ever, because a child
    is the offspring of a bond rather than of a pairing written twice. An event
    names who it is about, only people in the record, a couple that has a bond,
    and for a birth the child's own parents; a person is born once and dies
    once.
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

    for couple in _lost(data, deltas):
        events = [
            str(event.get("id"))
            for event in _collection(data, ItemKind.Event)
            if _val(event.get("kind")) in COUPLE_KINDS
            and pair({"person_a": event.get("person"), "person_b": event.get("spouse")})
            == couple
        ]
        if events:
            raise Invalid(
                f"that leaves event {', '.join(events)} naming persons "
                f"{' and '.join(couple)} as a couple with no pair bond: change or "
                "remove those events first",
                "Those two still have events as a couple: change or remove those "
                "first.",
            )

    for person_id in _touched_kind(deltas, ItemKind.Person):
        person = _find(data, ItemKind.Person, person_id)
        if person is None:
            continue
        for event in _collection(data, ItemKind.Event):
            if _val(event.get("kind")) == EventKind.Birth.value and str(
                event.get("child")
            ) == str(person_id):
                _born(data, str(event.get("id")), event)
        if person.get("parents") is None:
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

    people = {str(person.get("id")) for person in _collection(data, ItemKind.Person)}
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        for field, role in MOVE_LINKS:
            if field in event and not isinstance(event[field], list):
                raise Invalid(
                    f"event {event_id}'s {field} is not a list: give the "
                    f"{role}s as a list of person ids, empty when there is none",
                    f"The {role}s of a move could not be read.",
                )
        kind = _val(event.get("kind"))
        label = EventKind(kind).menuLabel()
        if kind in OFFSPRING_KINDS and event.get("child") is None:
            raise Invalid(
                f"event {event_id} is a {kind} with no child: a {kind} is about "
                "the child: "
                + (
                    "set child, not person"
                    if event.get("person") is not None
                    else "set child to who was born or taken in"
                ),
                f"{label} is about the child: choose who under Child.",
            )
        if kind not in OFFSPRING_KINDS and event.get("person") is None:
            raise Invalid(
                f"event {event_id} is a {kind} event about nobody: set person to "
                "who it happened to, adding them as a person first",
                f"{label} needs the person it happened to.",
            )
        for field in ("person", "spouse", "child", *(f for f, _ in MOVE_LINKS)):
            value = event.get(field)
            for person_id in value if isinstance(value, list) else [value]:
                if person_id is not None and str(person_id) not in people:
                    raise Invalid(
                        f"event {event_id} names person {person_id}, who is not in "
                        "the record: add them as a person first",
                        "Someone on that event is not in the diagram.",
                    )
        if event.get("spouse") is not None and str(event["spouse"]) == str(
            event.get("person")
        ):
            raise Invalid(
                f"event {event_id} names person {event['spouse']} as both person "
                "and spouse: they are two different people",
                "Those must be two different people.",
            )
        if event.get("child") is not None and str(event["child"]) in {
            str(event.get("person")),
            str(event.get("spouse")),
        }:
            raise Invalid(
                f"event {event_id} has person {event['child']} as both the child "
                "and a parent: nobody is born to themselves",
                "Nobody can be their own parent.",
            )
        mover = str(event.get("person"))
        for field, role in MOVE_LINKS:
            if mover in {str(x) for x in event.get(field) or []}:
                raise Invalid(
                    f"event {event_id} has person {mover} as both the mover and "
                    f"the {role}: a move is toward, away from or about someone "
                    f"else, so name the other person as the {role}",
                    f"Someone cannot be their own {role} in a move.",
                )
        move = _val(event.get("relationship"))
        targets = {str(x) for x in event.get("relationshipTargets") or []}
        thirds = {str(x) for x in event.get("relationshipTriangles") or []}
        if move and not targets:
            raise Invalid(
                f"event {event_id} is a {move} move with no target: every "
                "relationship move names who it was aimed at, so put them in "
                "relationship_targets, adding them as a person first, "
                "generically named where nobody named them",
                f"{RelationshipKind(move).menuLabel()} needs the person it was "
                "aimed at.",
            )
        if targets and not move:
            raise Invalid(
                f"event {event_id} has relationship_targets but no relationship "
                "move: set the move they were the target of, or leave them out",
                "Only a relationship move names who it was aimed at.",
            )
        if move in TRIANGLES and not thirds:
            raise Invalid(
                f"event {event_id} is an {move} move with no third person: a "
                "triangle is three people, so put the one left outside of an "
                "inside move, or the second of the two left together by an "
                "outside move, in relationship_triangles",
                f"{RelationshipKind(move).menuLabel()} needs the third person.",
            )
        if thirds and move not in TRIANGLES:
            raise Invalid(
                f"event {event_id} has relationship_triangles but is not an inside "
                "or outside move: only a triangle move has a third person",
                "Only a triangle move has a third person.",
            )
        if targets & thirds:
            raise Invalid(
                f"event {event_id} has person {min(targets & thirds)} as both a "
                "target and the third person: a triangle is three different "
                "people",
                "A triangle is three different people.",
            )
        if kind in COUPLE_KINDS and event.get("spouse") is None:
            raise Invalid(
                f"event {event_id} is a {kind} event, which is about a couple: "
                "name the other one as spouse, adding them as a person first, "
                "generically named where nobody named them",
                f"{label} needs both partners.",
            )
        if kind in COUPLE_KINDS and not any(
            pair(bond) == pair({"person_a": event["person"], "person_b": event["spouse"]})
            for bond in _collection(data, ItemKind.PairBond)
        ):
            raise Invalid(
                f"event {event_id} is a {kind} event between persons "
                f"{event['person']} and {event['spouse']}, who have no pair bond: "
                "add their pair bond first",
                f"{label} needs those two to be partners first.",
            )
        if kind == EventKind.Birth.value:
            _born(data, event_id, event)
        if kind in (EventKind.Birth.value, EventKind.Death.value):
            role = "child" if kind == EventKind.Birth.value else "person"
            for other in _collection(data, ItemKind.Event):
                if (
                    str(other.get("id")) != event_id
                    and _val(other.get("kind")) == kind
                    and str(other.get(role)) == str(event[role])
                ):
                    raise Invalid(
                        f"person {event[role]} already has a {kind}, event "
                        f"{other.get('id')}: change it with "
                        f"edit_event(id={other.get('id')}) rather than adding a "
                        "second",
                        f"That person already has a {kind}.",
                    )


def couple_bond(bonds: list[dict], event: dict) -> tuple | None:
    """What a couple event needs of the couple's bond before it is written, as
    (bond id, fields): the bond itself, id None, when they have none, or married
    set on theirs when the event is a marriage (R-0430, R-0593)."""
    kind = _val(event.get("kind"))
    a, b = event.get("person"), event.get("spouse")
    if kind not in COUPLE_KINDS or None in (a, b) or str(a) == str(b):
        return None
    married = kind == EventKind.Married.value
    couple = {"person_a": a, "person_b": b}
    bond = next((x for x in bonds if pair(x) == pair(couple)), None)
    if bond is None:
        return None, dict(couple, married=True) if married else couple
    if married and bond.get("married") is not True:
        return bond["id"], {"married": True}
    return None


def _born(data: dict, event_id: str, birth: dict):
    """A birth's parents are the child's own parents: the two sides of the bond
    the child is born to, so the birth and the child never disagree about who
    someone's mother is."""
    child = _find(data, ItemKind.Person, birth.get("child"))
    bond = child and _find(data, ItemKind.PairBond, child.get("parents"))
    if not bond:
        return
    for parent in (birth.get("person"), birth.get("spouse")):
        if parent is not None and str(parent) not in pair(bond):
            raise Invalid(
                f"event {event_id} names person {parent} as a parent of person "
                f"{child['id']}, who is born to pair bond {bond['id']} (persons "
                f"{' and '.join(pair(bond))}): a birth's parents are the child's "
                "parents, so name those two",
                "A birth's parents must be the child's own parents.",
            )


def _lost(data: dict, deltas: list[dict]) -> set[tuple]:
    """The pairs of people that had a bond before this write and have none
    after it."""
    was = {}
    for delta in deltas:
        if delta["item_kind"] != ItemKind.PairBond.value:
            continue
        bond_id = str(delta["item_id"])
        if delta["field"] is None and delta["before"]:
            was[bond_id] = dict(delta["before"])
        elif delta["field"] in ("person_a", "person_b"):
            was.setdefault(
                bond_id, dict(_find(data, ItemKind.PairBond, bond_id) or {})
            )[delta["field"]] = delta["before"]
    now = {pair(bond) for bond in _collection(data, ItemKind.PairBond)}
    return {
        pair(bond)
        for bond in was.values()
        if None not in (bond.get("person_a"), bond.get("person_b"))
    } - now


QUESTION_LINKS = (ItemKind.Person, ItemKind.PairBond, ItemKind.Event, ItemKind.Cluster)
FACT_LINKS = (ItemKind.Person, ItemKind.PairBond)


@dataclass(frozen=True)
class Note:
    """What differs between a question and an impression; everything else
    about the two is one set of rules."""

    noun: str
    # The state the person sees it in: a question is asked, an impression raised.
    shown: QuestionState
    # The outcomes only the user writes, and the one that bars the same words.
    theirs: tuple
    barred: QuestionOutcome
    barred_plain: str
    ours: tuple
    # What the user may write on it at all.
    fields: tuple

    @property
    def order(self) -> list:
        return [QuestionState.Held, self.shown, QuestionState.Resolved]


QUESTION = Note(
    "question",
    QuestionState.Asked,
    (QuestionOutcome.DeclinedByUser,),
    QuestionOutcome.DeclinedByUser,
    "The user already turned this question down.",
    (
        QuestionOutcome.Fact,
        QuestionOutcome.Answered,
        QuestionOutcome.Unknown,
        QuestionOutcome.DeclinedInChat,
        QuestionOutcome.LetGo,
    ),
    ("state", "outcome"),
)
IMPRESSION = Note(
    "impression",
    QuestionState.Raised,
    (QuestionOutcome.DoesntFit,),
    QuestionOutcome.DoesntFit,
    "You said that one doesn't fit.",
    (QuestionOutcome.Revised, QuestionOutcome.LetGo),
    ("state", "outcome", "pushback"),
)


def note(item: dict) -> Note:
    return IMPRESSION if item.get("kind") == QuestionKind.Impression else QUESTION


def normal(text: str) -> str:
    return " ".join(text.lower().split())


def _questions(data: dict, deltas: list[dict], author: Author):
    """A question or an impression has words, moves only forward from held to
    shown to resolved, says how it ended exactly when it is resolved, is kept
    once in the same words and never in words the user turned down, and is
    turned down or pushed back on by the user alone, who writes nothing else
    on it (R-0006, R-0077)."""
    questions = _collection(data, ItemKind.Question)
    user = Author(author) is Author.User
    for question_id in _touched_kind(deltas, ItemKind.Question):
        question = _find(data, ItemKind.Question, question_id)
        rules = note(question)
        noun = rules.noun
        mine = [
            d
            for d in deltas
            if d["item_kind"] == ItemKind.Question.value and str(d["item_id"]) == question_id
        ]
        state = QuestionState(_val(question.get("state")))
        outcome = question.get("outcome") and QuestionOutcome(_val(question["outcome"]))
        QuestionKind(_val(question.get("kind")))
        written = {d["field"] for d in mine}
        # taken off a card, by the coach or by a newer entry on that card, on
        # an entry in any state
        if written == {CARD} and question.get(CARD) is None:
            _card(question, question_id, rules, state, written, author)
            continue
        moved = [d for d in mine if d["field"] == "state"]
        added = any(d["field"] is None for d in mine)
        was = None if added else QuestionState(moved[0]["before"] if moved else state)
        if state not in rules.order:
            raise Invalid(
                f"{noun} {question_id} cannot be {state.value}: it is held, "
                f"{rules.shown.value} or resolved",
                f"A {noun} cannot be {state.value}.",
            )
        if was is QuestionState.Resolved:
            raise Invalid(f"{noun} {question_id} is already closed", f"That {noun} is already closed.")
        if moved and not added and rules.order.index(state) <= rules.order.index(was):
            if was is rules.shown:
                raise Invalid(
                    f"{noun} {question_id} was already {was.value}",
                    f"That {noun} was already {was.value}.",
                )
            raise Invalid(
                f"{noun} {question_id} is already held",
                f"That {noun} is already kept for later.",
            )
        if not (question.get("text") or "").strip():
            raise Invalid(f"{noun} {question_id} has no words", f"It gave the {noun} no words.")
        if (state is QuestionState.Resolved) != bool(outcome):
            raise Invalid(
                f"{noun} {question_id}: give an outcome exactly when it is resolved",
                f"It did not say how the {noun} ended.",
            )
        theirs = outcome in rules.theirs or "pushback" in written
        if user != theirs or (user and not written <= set(rules.fields)):
            raise Invalid(
                f"only the user turns {noun} {question_id} down or pushes back on it, "
                "and does nothing else to it",
                "Only you can dismiss a question."
                if rules is QUESTION
                else f"Only you can push back on an {noun}.",
            )
        if outcome and outcome not in (*rules.theirs, *rules.ours):
            raise Invalid(
                f"{noun} {question_id} ends only as one of "
                f"{', '.join(o.value for o in rules.ours)}",
                f"That is not how an {noun} ends." if rules is IMPRESSION
                else f"That is not how a {noun} ends.",
            )
        if question.get("pushback") is not None:
            Pushback(question["pushback"])
        _card(question, question_id, rules, state, written, author)
        if question.get("answer") is not None and (
            rules is IMPRESSION or outcome is not QuestionOutcome.Answered
        ):
            raise Invalid(
                f"{noun} {question_id}: give the message that answers it only when "
                "closing a question as answered",
                "It kept an answer on something that was not answered.",
            )
        if rules is IMPRESSION:
            _rests(data, question, question_id, added)
            if added:
                _uncaused(question, question_id)
                _unsourced(data, question, question_id)
        else:
            _linked(data, question, question_id)
            _names(question, question_id)
        for other in questions:
            if (
                str(other.get("id")) == question_id
                or note(other) is not rules
                or normal(other["text"]) != normal(question["text"])
            ):
                continue
            if other.get("outcome") == rules.barred:
                raise Invalid(
                    f"the user turned that {noun} down as {other['id']}: never say it again",
                    rules.barred_plain,
                )
            if other["state"] != QuestionState.Resolved:
                raise Invalid(f"that {noun} is already {other['id']}", f"That {noun} is already there.")


def _card(question: dict, question_id: str, rules, state, written: set, author: Author):
    """Only the coach puts an entry on a case report card; a question goes only
    on the own part card or the choice card; and an entry kept for later is on
    none, since the page never sees it (R-0709)."""
    noun = rules.noun
    if CARD in written and Author(author) is not Author.Coach:
        raise Invalid(
            f"only the coach puts {noun} {question_id} on a case report card",
            "Only the coach chooses what goes on the case report.",
        )
    if question.get(CARD) is None:
        return
    card = CaseReportCard(question[CARD])
    if rules is QUESTION and card not in QUESTION_CARDS:
        raise Invalid(
            f"question {question_id} cannot be on the {card.value} card: a question "
            f"goes only on {' or '.join(c.value for c in QUESTION_CARDS)}",
            "A question cannot go on that card of the case report.",
        )
    if state is QuestionState.Held:
        raise Invalid(
            f"{noun} {question_id} is held: put it on a card when it is {rules.shown.value}",
            f"A {noun} kept for later cannot go on the case report.",
        )


def _linked(data: dict, question: dict, question_id: str):
    link = (question.get("item_kind"), question.get("item_id"))
    if (link[0] is None) != (link[1] is None):
        raise Invalid(
            f"question {question_id}: give item_kind and item_id together, or neither",
            "It named what the question is about only halfway.",
        )
    if link[0] is not None and (
        ItemKind(link[0]) not in QUESTION_LINKS or _find(data, ItemKind(link[0]), link[1]) is None
    ):
        raise Invalid(
            f"question {question_id} is about {link[0]} {link[1]}, which is not in the record",
            GONE,
        )


def _names(question: dict, question_id: str):
    """A fact question may name the item of the basic data it asks about, on
    the person or the couple it is linked to."""
    if question.get("fact") is None:
        return
    Fact(question["fact"])
    if question["kind"] != QuestionKind.Fact or question.get("item_kind") not in FACT_LINKS:
        raise Invalid(
            f"question {question_id} names {question['fact']}: only a fact question "
            "about a person or a couple names what it asks",
            "It named what the question asks on something that cannot hold it.",
        )


def _rests(data: dict, impression: dict, impression_id: str, added: bool):
    """An impression is raised on something in the record. Whether a
    statement is this family's is the toolbox's to check; the record holds
    no statements. Evidence taken off the record since leaves it on less, or
    on nothing, for the coach to judge."""
    evidence = impression.get("evidence") or []
    if added and not evidence:
        raise Invalid(
            f"impression {impression_id} rests on nothing: give the events, people, "
            "bonds, clusters or messages it comes from",
            "It gave the impression nothing to rest on.",
        )
    for one in evidence:
        kind = EvidenceKind(one["kind"])
        if kind is not EvidenceKind.Statement and _find(data, ItemKind(kind.value), one["id"]) is None:
            raise Invalid(
                f"impression {impression_id} rests on {kind.value} {one['id']}, which is "
                "not in the record",
                GONE,
            )


# Words that say one thing brought about another. An impression notes what
# came first and how close in time (R-0569, R-0504); Bowen never went beyond
# "a striking time sequence".
CAUSE = re.compile(
    r"\b(caus(e|es|ed|ing)|drove|drives|driven|(led|leads|leading) to|because of"
    r"|made (him|her|them)|result(ed|s)? in|trigger(ed|s)?)\b",
    re.IGNORECASE,
)


# Words that point a person away from their own story to sources behind the
# coach (R-0688).
LITERATURE = re.compile(
    r"\b(books?|literature|the theory|theories|research|Bowen|Kerr|Havstad|Papero"
    r"|Gilbert|Titelman)\b",
    re.IGNORECASE,
)


def _uncaused(impression: dict, impression_id: str):
    found = CAUSE.search(impression.get("text") or "")
    if found:
        raise Invalid(
            f"impression {impression_id} says one thing brought about another "
            f"({found.group(0)!r}): say what came first and how close in time, "
            "and claim no more than what it rests on holds",
            "The impression says one thing caused another. Say what came first "
            "and how close in time instead.",
        )


def sourced(text: str, people: list[dict]) -> str | None:
    """The first word of the text that points to the literature, or None. An
    author's surname that is also a name in this family is the family's."""
    names = {
        (p.get(field) or "").lower() for p in people for field in ("name", "last_name")
    }
    return next(
        (m.group(0) for m in LITERATURE.finditer(text) if m.group(0).lower() not in names),
        None,
    )


def _unsourced(data: dict, impression: dict, impression_id: str):
    found = sourced(impression.get("text") or "", _collection(data, ItemKind.Person))
    if found:
        raise Invalid(
            f"impression {impression_id} mentions the literature ({found!r}): "
            "speak from what this person has told you, never books, the theory, "
            "research or an author",
            "The impression mentions books or theory. Say it from what was told.",
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
        session_id=None if session_id is None else str(session_id),
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


SHOWN = (QuestionState.Asked, QuestionState.Raised)


def asks(delta: dict) -> bool:
    if delta["field"] is None:
        return delta["after"].get("state") in SHOWN
    return delta["field"] == "state" and delta["after"] in SHOWN


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


class Kept(enum.StrEnum):
    """A fact about a person that two records of one person can disagree on,
    which a merge keeps from one side only."""

    Birth = "birth"
    Death = "death"
    Gender = "gender"
    Notes = "notes"
    Parents = "parents"


class Side(enum.StrEnum):
    """Whose fact a merge keeps where the two people's records differ."""

    Keep = "keep"
    Drop = "drop"


#: The event that holds a birth or a death, and the role its person has in it.
LIFE = {Kept.Birth: (EventKind.Birth, "child"), Kept.Death: (EventKind.Death, "person")}
KEPT_WORDS = {
    Kept.Birth: "born",
    Kept.Death: "died",
    Kept.Gender: "gender",
    Kept.Notes: "notes",
    Kept.Parents: "parents",
}


def collections(data) -> dict:
    """A DiagramData's items as the dict the write path reads."""
    return {name: getattr(data, name) for name in ITEM_COLLECTIONS.values()}


def life(data: dict, person_id, fact: Kept) -> dict | None:
    kind, role = LIFE[fact]
    return next(
        (
            e
            for e in _collection(data, ItemKind.Event)
            if _val(e.get("kind")) == kind.value and str(e.get(role)) == str(person_id)
        ),
        None,
    )


def facts(data: dict, person_id) -> dict[Kept, object]:
    """What a person's record says of each fact a merge keeps from one side;
    None where it says nothing."""
    person = _find(data, ItemKind.Person, person_id)
    gender = _val(person.get("gender"))
    return {
        **{fact: _day((life(data, person_id, fact) or {}).get("dateTime")) for fact in LIFE},
        Kept.Gender: None if gender in (None, PersonKind.Unknown.value) else gender,
        Kept.Notes: (person.get("notes") or "").strip() or None,
        Kept.Parents: person.get("parents"),
    }


def differing(data: dict, a, b) -> dict[Kept, tuple]:
    """The facts two people's records both hold and disagree on."""
    fa, fb = facts(data, a), facts(data, b)
    return {
        fact: (fa[fact], fb[fact])
        for fact in Kept
        if None not in (fa[fact], fb[fact]) and str(fa[fact]) != str(fb[fact])
    }


def dropped_words(fact: Kept, lost, won) -> str:
    """A fact one side of a merge gave up, as the line under the merge says it."""
    if fact in LIFE:
        lost, won = (lost, won) if lost[:4] == won[:4] else (lost[:4], won[:4])
        return f"{KEPT_WORDS[fact]} {lost} dropped \u00b7 {won} kept"
    if fact is Kept.Gender:
        return f"{lost} dropped \u00b7 {won} kept"
    return f"the other {KEPT_WORDS[fact]} dropped"


def kin(data: dict, a, b) -> bool:
    """The two are partners, or one is the other's parent."""
    if any(pair(bond) == pair({"person_a": a, "person_b": b}) for bond in _collection(data, ItemKind.PairBond)):
        return True
    for child, parent in ((a, b), (b, a)):
        person = _find(data, ItemKind.Person, child) or {}
        bond = _find(data, ItemKind.PairBond, person.get("parents"))
        if bond and str(parent) in pair(bond):
            return True
    return False


@dataclass
class Merge:
    """What joining one person into another writes, what it moves over to the
    kept person, and the facts of either side it leaves behind."""

    deltas: list[dict]
    moved: list[tuple[ItemKind, str]]
    dropped: list[str]


def _merge_refusal(data: dict, keep, drop, take: dict[str, str]):
    if str(keep) == str(drop):
        raise Invalid(
            f"keep and drop are both person {keep}: name two people",
            "That is one person already.",
        )
    for person_id in (keep, drop):
        if _find(data, ItemKind.Person, person_id) is None:
            raise Invalid(f"No person {person_id} in the record", GONE)
    if kin(data, keep, drop):
        raise Invalid(
            f"persons {keep} and {drop} are partners, or parent and child: two "
            "people, never one",
            "Those two are partners, or parent and child, so they are two people.",
        )
    unnamed = [fact for fact in differing(data, keep, drop) if fact.value not in take]
    if unnamed:
        both = differing(data, keep, drop)
        said = "; ".join(
            f"{fact.value}: {both[fact][0]} on person {keep}, {both[fact][1]} on person {drop}"
            for fact in unnamed
        )
        raise Invalid(
            f"the two differ on {said}. Ask the person which is right, name it in "
            "take as keep or drop, and merge again",
            "Those two differ on "
            + " and ".join(KEPT_WORDS[fact] for fact in unnamed)
            + ", so it asks which is right first.",
        )


def merging(data: dict, keep, drop, take: dict[str, str], name: str | None = None) -> Merge:
    """Join person `drop` into person `keep`. Every event, pair bond, parent
    link, relationship, question and impression naming the dropped person names
    the kept one; a fact the kept person lacks comes over; a fact both hold is
    the kept person's unless `take` gives it to the dropped one; a pair bond both had with the same
    partner becomes one; then the dropped person goes. Reads `data` only."""
    deltas = []
    moved: dict[tuple[ItemKind, str], None] = {}
    dropped = []
    keep_id = int(keep)

    def put(kind: ItemKind, item_id, field: str, after):
        deltas.append({"item_kind": kind.value, "item_id": item_id, "field": field, "after": after})

    def remove(kind: ItemKind, item_id):
        deltas.append({"item_kind": kind.value, "item_id": item_id, "field": None, "after": None})

    both = differing(data, keep, drop)
    theirs = {fact for fact, side in take.items() if side == Side.Drop.value}
    gone = set()
    for fact in LIFE:
        kept, lost = life(data, keep, fact), life(data, drop, fact)
        if kept is None or lost is None:
            continue
        if fact.value in theirs or _day(kept.get("dateTime")) is None:
            for field in ("dateTime", "dateCertainty"):
                put(ItemKind.Event, kept["id"], field, diagramjson.to_json(lost.get(field)))
        remove(ItemKind.Event, lost["id"])
        gone.add(str(lost["id"]))

    for event in _collection(data, ItemKind.Event):
        if str(event.get("id")) in gone:
            continue
        for field in ("person", "spouse", "child"):
            if str(event.get(field)) == str(drop):
                put(ItemKind.Event, event["id"], field, keep_id)
                moved[(ItemKind.Event, str(event["id"]))] = None
        for field, _ in MOVE_LINKS:
            ids = event.get(field) or []
            if any(str(x) == str(drop) for x in ids):
                swapped = [keep_id if str(x) == str(drop) else x for x in ids]
                put(ItemKind.Event, event["id"], field, list(dict.fromkeys(swapped)))
                moved[(ItemKind.Event, str(event["id"]))] = None

    for emotion in _collection(data, ItemKind.Emotion):
        for field in ("person", "target"):
            if str(emotion.get(field)) == str(drop):
                put(ItemKind.Emotion, emotion["id"], field, keep_id)

    renamed = {(ItemKind.Person.value, str(drop)): keep_id}
    bonds = _collection(data, ItemKind.PairBond)
    for bond in bonds:
        sides = [side for side in ("person_a", "person_b") if str(bond.get(side)) == str(drop)]
        if not sides:
            continue
        other = bond.get("person_b" if sides[0] == "person_a" else "person_a")
        twin = next(
            (b for b in bonds if pair(b) == pair({"person_a": keep, "person_b": other})),
            None,
        )
        if twin is None:
            put(ItemKind.PairBond, bond["id"], sides[0], keep_id)
            moved[(ItemKind.PairBond, str(bond["id"]))] = None
            continue
        for child in _collection(data, ItemKind.Person):
            if str(child.get("parents")) == str(bond["id"]):
                put(ItemKind.Person, child["id"], "parents", twin["id"])
        if bond.get("married") and not twin.get("married"):
            put(ItemKind.PairBond, twin["id"], "married", True)
        renamed[(ItemKind.PairBond.value, str(bond["id"]))] = twin["id"]
        moved[(ItemKind.PairBond, str(twin["id"]))] = None

    for question in _collection(data, ItemKind.Question):
        to = renamed.get((question.get("item_kind"), str(question.get("item_id"))))
        if to is not None:
            put(ItemKind.Question, question["id"], "item_id", type(question["item_id"])(to))
            moved[(ItemKind.Question, str(question["id"]))] = None
        evidence = question.get("evidence") or []
        swapped = [
            dict(one, id=type(one["id"])(renamed.get((one["kind"], str(one["id"])), one["id"])))
            for one in evidence
        ]
        if swapped != evidence:
            unique = list({(one["kind"], str(one["id"])): one for one in swapped}.values())
            put(ItemKind.Question, question["id"], "evidence", unique)
            moved[(ItemKind.Question, str(question["id"]))] = None

    for (kind, bond_id), twin_id in renamed.items():
        if kind == ItemKind.PairBond.value:
            remove(ItemKind.PairBond, next(b["id"] for b in bonds if str(b["id"]) == bond_id))

    kept = _find(data, ItemKind.Person, keep)
    lost = _find(data, ItemKind.Person, drop)
    if name:
        put(ItemKind.Person, kept["id"], "name", name)
    for field in ("name", "last_name"):
        if lost.get(field) and not kept.get(field) and not (name and field == "name"):
            put(ItemKind.Person, kept["id"], field, lost[field])
    mine, other = facts(data, keep), facts(data, drop)
    for fact, field in ((Kept.Gender, "gender"), (Kept.Notes, "notes"), (Kept.Parents, "parents")):
        if other[fact] is not None and (mine[fact] is None or fact.value in theirs):
            put(ItemKind.Person, kept["id"], field, lost.get(field))
    for fact, (ours, other_value) in both.items():
        lost_fact, won = (ours, other_value) if fact.value in theirs else (other_value, ours)
        dropped.append(dropped_words(fact, str(lost_fact), str(won)))
    remove(ItemKind.Person, lost["id"])
    return Merge(deltas, list(moved), dropped)


def merge(
    diagram_id: int,
    keep,
    drop,
    *,
    take: dict[str, str],
    name: str | None = None,
    author: Author,
    turn_id: str,
    user_id: int | None = None,
    session_id: int | None = None,
    statement_id: int | None = None,
) -> tuple[Change, Merge]:
    """Join two records of one person as one change, so one undo of its turn
    puts both back as they were."""
    with _locked(diagram_id) as diagram:
        data = diagramjson.loads(diagram.data)
        _merge_refusal(data, keep, drop, take)
        plan = merging(data, keep, drop, take, name)
        applied = [d for delta in plan.deltas for d in _apply(data, delta)]
        change = _commit(
            diagram, data, compress(applied), author, turn_id, user_id, session_id, statement_id
        )
        return change, plan
