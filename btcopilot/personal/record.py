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
from btcopilot.schema import ITEM_COLLECTIONS, ItemKind

_log = logging.getLogger(__name__)


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
    """
    diagram = _lock(diagram_id)
    data = diagramjson.loads(diagram.data)
    applied = [_set(data, d) for d in deltas]
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
            applied.append(_set(data, inverse))
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


def _item(data: dict, delta: dict) -> dict:
    kind = ItemKind(delta["item_kind"])
    if kind is ItemKind.Diagram:
        return data
    collection = data.setdefault(ITEM_COLLECTIONS[kind], [])
    for item in collection:
        if str(item.get("id")) == str(delta["item_id"]):
            return item
    item = {"id": delta["item_id"]}
    collection.append(item)
    return item


def _get(data: dict, delta: dict):
    return diagramjson.to_json(_item(data, delta).get(delta["field"]))


def _set(data: dict, delta: dict) -> dict:
    item = _item(data, delta)
    before = diagramjson.to_json(item.get(delta["field"]))
    item[delta["field"]] = diagramjson.from_json(delta["after"])
    return {
        "item_id": delta["item_id"],
        "item_kind": ItemKind(delta["item_kind"]).value,
        "field": delta["field"],
        "before": before,
        "after": delta["after"],
    }


def _commit(
    diagram, data, deltas, author, turn_id, user_id, session_id, statement_id
) -> Change:
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
