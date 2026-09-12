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
from btcopilot.personal.models import Author, Change
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    ITEM_COLLECTIONS,
    MIN_CLUSTER_EVENTS,
    EventKind,
    ItemKind,
    RelationshipKind,
    VariableShift,
)

_log = logging.getLogger(__name__)


class Invalid(Exception):
    """The record the deltas would leave behind breaks a rule of the data model."""


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
    it back.
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
        for delta in reversed(change.deltas):
            inverse = dict(delta, before=delta["after"], after=delta["before"])
            actual = _get(data, inverse)
            if actual != inverse["before"]:
                raise Conflict(inverse, actual)
            applied.extend(_apply(data, inverse))
    return _commit(
        diagram,
        data,
        compress(applied),
        author,
        f"undo:{turn_id}",
        user_id,
        session_id,
        None,
    )


def compress(deltas: list[dict]) -> list[dict]:
    """Collapse consecutive deltas on the same item and field: first before, last after."""
    out = []
    for delta in deltas:
        if out and (out[-1]["item_id"], out[-1]["item_kind"], out[-1]["field"]) == (
            delta["item_id"],
            delta["item_kind"],
            delta["field"],
        ):
            out[-1] = dict(out[-1], after=delta["after"])
        else:
            out.append(dict(delta))
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
    if delta["field"] is not None:
        return [_set(data, delta)]
    kind = ItemKind(delta["item_kind"])
    if kind is ItemKind.Diagram:
        raise ValueError("the diagram itself cannot be removed by a delta")
    if delta["after"] is None:
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
    event takes the emotions it caused.
    """
    deltas = []
    if kind is ItemKind.Person:
        for event in [e for e in _collection(data, ItemKind.Event) if _names(e, item_id)]:
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


def _names(event: dict, person_id) -> bool:
    """Scene's Event.people(): the person is one of the event's roles."""
    ids = [event.get("person"), event.get("spouse"), event.get("child")]
    ids += event.get("relationshipTargets") or []
    ids += event.get("relationshipTriangles") or []
    return any(str(x) == str(person_id) for x in ids if x is not None)


def _validate(data: dict, deltas: list[dict]):
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
            "events: add an event to the cluster, or remove the grouping"
        )
    _words(data, deltas)
    _moves(data, deltas)
    _twins(data, deltas)


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
    return list(
        dict.fromkeys(
            str(delta["item_id"])
            for delta in deltas
            if delta["item_kind"] == ItemKind.Event.value
        )
    )


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
                "set child, not person"
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
                        f"already its {role}; say what happened without the name"
                    )


def _moves(data: dict, deltas: list[dict]):
    """A shift says which way something moved, and an early birth says nothing
    but when someone was born (owner ruling R-0037). Checked on the events this
    write touches, the way the cluster floor is."""
    events = _collection(data, ItemKind.Event)
    for event_id in _touched(deltas):
        event = _find(data, ItemKind.Event, event_id)
        if event is None:
            continue
        kind = _val(event.get("kind"))
        if kind == EventKind.Shift.value and not _moved(event):
            raise Invalid(
                f"event {event_id} is a shift with no variable and no "
                "relationship move: say which of symptom, anxiety, functioning "
                "or relationship moved, and which way"
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
                "carries no symptom, anxiety, functioning or relationship"
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


def _twins(data: dict, deltas: list[dict]):
    """The same moment is not written down twice: an event this write adds that
    matches one already in the record is refused, naming the one that is there."""
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
            if (
                _val(other.get("kind")) == _val(event.get("kind"))
                and _day(other.get("dateTime")) == _day(event.get("dateTime"))
                and _links(other) == _links(event)
            ):
                raise Invalid(
                    f"that event is already event {other.get('id')}: change it "
                    f"with edit_event(id={other.get('id')}) rather than adding it"
                )


def _commit(
    diagram, data, deltas, author, turn_id, user_id, session_id, statement_id
) -> Change:
    _validate(data, deltas)
    db.session.execute(
        sql_update(Diagram)
        .where(Diagram.id == diagram.id)
        .values(
            data=diagramjson.encode(data, diagram.data), version=Diagram.version + 1
        )
    )
    change = Change(
        diagram_id=diagram.id,
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


def coded_in(diagram_id: int) -> dict[int, dict]:
    """Where each moment on this diagram was written down: the message the coach
    was saying when it went in, and the session that message belongs to.

    The command log is the record of that. Every command carries the deltas it
    applied, and a coach turn stamps its own statement on the commands it made,
    so a moment traces to a message through the commands that named it. The
    newest such command wins: a moment changed twice belongs to the last thing
    said about it.
    """
    from btcopilot.personal.models import Statement

    found: dict[int, dict] = {}
    rows = (
        Change.query.filter(
            Change.diagram_id == diagram_id, Change.statement_id.isnot(None)
        )
        .order_by(Change.id)
        .all()
    )
    if not rows:
        return found
    said = {
        statement.id: statement.discussion_id
        for statement in Statement.query.filter(
            Statement.id.in_({row.statement_id for row in rows})
        ).all()
    }
    for row in rows:
        for delta in row.deltas or []:
            if delta.get("item_kind") != ItemKind.Event.value:
                continue
            try:
                event_id = int(delta["item_id"])
            except (KeyError, TypeError, ValueError):
                continue
            found[event_id] = {
                "discussion_id": said.get(row.statement_id),
                "statement_id": row.statement_id,
            }
    return found
