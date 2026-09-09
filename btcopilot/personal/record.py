"""The one write path onto a diagram's record.

Every mutation of the record goes through `apply`: it locks the diagram row, sets
the fields, and writes the Change row in the same transaction, so the log can
never disagree with the record. `undo` replays a turn backwards with a
compare-and-set on each value.
"""

import logging

from sqlalchemy import update as sql_update

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.personal.models import Author, Change
from btcopilot.pro.models import Diagram
from btcopilot.schema import ITEM_COLLECTIONS, MIN_CLUSTER_EVENTS, ItemKind

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
            f"clusters {small} would hold fewer than {MIN_CLUSTER_EVENTS} events"
        )


def _commit(
    diagram, data, deltas, author, turn_id, user_id, session_id, statement_id
) -> Change:
    _validate(data, deltas)
    db.session.execute(
        sql_update(Diagram)
        .where(Diagram.id == diagram.id)
        .values(data=diagramjson.dumps(data), version=Diagram.version + 1)
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
