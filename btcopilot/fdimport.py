"""A desktop Family Diagram file made into a new diagram in the chat app.

What the person entered is copied as it stands; what only drew the old
picture is dropped. The whole import is one change-log turn, so one undo
takes it back [Oracle: R-0850]."""

import collections
from dataclasses import dataclass, field

from btcopilot import diagramjson, record
from btcopilot.extensions import db
from btcopilot.models import Author, Diagram
from btcopilot.schema import (
    DateCertainty,
    EventKind,
    ItemKind,
    NotedFact,
    RelationshipKind,
    VariableShift,
    enum_val,
)

TURN = "fd-import:{}"
# The desktop's own words for two kinds the app names otherwise [Oracle: R-0864].
MOVED = "moved"
OLD_SHIFT = "variable-shift"
VALUES = {
    **{name: {v.value for v in VariableShift} for name in ("symptom", "anxiety", "functioning")},
    "relationship": {v.value for v in RelationshipKind},
}
# On an event: a hand-coded value the app has no word for, as the file held
# it, for a later coding pass to read.
RAW = "fileValues"
PERSON = {
    "name": "name",
    "lastName": "last_name",
    "gender": "gender",
    "notes": "notes",
    "primary": "primary",
    "alias": "alias",
    "nickName": "nickName",
    "middleName": "middleName",
    "birthName": "birthName",
}
PERSON_USED = {"kind", "id", "parents", "childOf"}
BOND = ("person_a", "person_b", "married")
EVENT = (
    "person",
    "spouse",
    "child",
    "description",
    "notes",
    "location",
    "dateTime",
    "endDateTime",
    "relationshipTargets",
    "relationshipTriangles",
    "tags",
)
EVENT_USED = {"id", "kind", "unsure", "dateCertainty", "dynamicProperties", *VALUES}
LINE_USED = {"id", "kind", "person", "target", "event", "notes", "tags"}
DROPPED = ("layers", "layerItems", "multipleBirths", "items", "pruned")


@dataclass
class Imported:
    people: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    pair_bonds: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    lines: int = 0
    blanks: list[dict] = field(default_factory=list)
    dropped: collections.Counter = field(default_factory=collections.Counter)

    def summary(self) -> dict:
        return {
            "people": len(self.people),
            "events": len(self.events),
            "pair_bonds": len(self.pair_bonds),
            "relationship_lines": self.lines,
            "left_blank": len(self.blanks),
            "dropped": sum(self.dropped.values()),
        }


def _kept(value) -> bool:
    return value not in (None, "", [], {}, False)


def _drop(out: Imported, collection: str, chunk: dict, used) -> None:
    for key, value in chunk.items():
        if key not in used and _kept(value):
            out.dropped[f"{collection}.{key}"] += 1


def _set(item: dict, key: str, value) -> None:
    if _kept(value):
        item[key] = value


def _person(out: Imported, chunk: dict) -> dict:
    person = {"id": chunk["id"]}
    for theirs, ours in PERSON.items():
        _set(person, ours, enum_val(chunk.get(theirs)))
    parents = chunk.get("parents") or (chunk.get("childOf") or {}).get("parents")
    _set(person, "parents", parents)
    _drop(out, "people", chunk, PERSON_USED | set(PERSON))
    return person


def _bond(out: Imported, chunk: dict) -> dict:
    bond = {"id": chunk["id"], **{key: chunk.get(key) for key in BOND}}
    _drop(out, "pair_bonds", chunk, {"kind", "id", *BOND})
    return bond


def _value(out: Imported, event: dict, name: str, raw) -> None:
    """A hand-coded value copied as it stands, or left blank with the file's
    text kept when it is not one of the app's values [Oracle: R-0859]."""
    raw = enum_val(raw)
    if not _kept(raw):
        return
    if raw in VALUES[name]:
        event[name] = raw
        return
    event.setdefault(RAW, {})[name] = str(raw)
    out.blanks.append({"event": event["id"], "field": name, "raw": str(raw)})


def _event(out: Imported, chunk: dict) -> dict:
    kind = enum_val(chunk["kind"])
    event = {"id": chunk["id"]}
    if kind == MOVED:
        event.update(kind=EventKind.Noted.value, item=NotedFact.Places.value)
    elif kind == OLD_SHIFT:
        event["kind"] = EventKind.Shift.value
    else:
        event["kind"] = EventKind(kind).value
    for key in EVENT:
        _set(event, key, chunk.get(key))
    certainty = enum_val(chunk.get("dateCertainty"))
    if chunk.get("unsure"):
        event["dateCertainty"] = DateCertainty.Approximate.value
    elif certainty in {c.value for c in DateCertainty}:
        event["dateCertainty"] = certainty
    else:
        event["dateCertainty"] = DateCertainty.Certain.value
    coded = chunk.get("dynamicProperties") or {}
    for name in VALUES:
        own = enum_val(chunk.get(name))
        _value(out, event, name, own if _kept(own) else coded.get(name))
    _drop(out, "events", chunk, EVENT_USED | set(EVENT))
    _drop(out, "events.dynamicProperties", coded, VALUES)
    return event


def _line(out: Imported, chunk: dict, events: dict) -> dict | None:
    """A relationship line puts its kind and target on the event it belongs
    to, or becomes a shift of its own on its person, undated."""
    kind = enum_val(chunk["kind"])
    target = chunk.get("target")
    out.lines += 1
    _drop(out, "emotions", chunk, LINE_USED)
    if chunk.get("event") is not None:
        event = events[chunk["event"]]
        if "relationship" not in event and RAW not in event:
            _value(out, event, "relationship", kind)
        if target is not None and target not in event.setdefault("relationshipTargets", []):
            event["relationshipTargets"].append(target)
        if _kept(chunk.get("notes")) and chunk["notes"] != event.get("notes"):
            out.dropped["emotions.notes"] += 1
        return None
    event = {
        "id": chunk["id"],
        "kind": EventKind.Shift.value,
        "person": chunk.get("person"),
        "dateCertainty": DateCertainty.Unknown.value,
    }
    _value(out, event, "relationship", kind)
    if "relationship" in event:
        label = RelationshipKind(event["relationship"]).menuLabel()
        event.update(description=label, title=f"{label} move")
    _set(event, "relationshipTargets", [target] if target is not None else [])
    _set(event, "notes", chunk.get("notes"))
    _set(event, "tags", chunk.get("tags"))
    return event


def convert(fd: dict) -> Imported:
    out = Imported(tags=list(fd.get("tags") or []))
    out.people = [_person(out, chunk) for chunk in fd.get("people") or []]
    bonds = fd.get("pair_bonds") or fd.get("marriages") or []
    out.pair_bonds = [_bond(out, chunk) for chunk in bonds]
    out.events = [_event(out, chunk) for chunk in fd.get("events") or []]
    by_id = {event["id"]: event for event in out.events}
    for chunk in fd.get("emotions") or []:
        made = _line(out, chunk, by_id)
        if made is not None:
            out.events.append(made)
    for name in DROPPED:
        out.dropped[name] += len(fd.get(name) or [])
    out.dropped = +out.dropped
    return out


def _removable(imported: Imported) -> list[tuple[ItemKind, dict]]:
    """People and pair-bonds in an order each can come off with nothing hanging
    on it: a bond after its children, a person after their bonds."""
    bonds_of = collections.Counter(
        bond[side] for bond in imported.pair_bonds for side in ("person_a", "person_b")
    )
    children = collections.Counter(p["parents"] for p in imported.people if "parents" in p)
    people, bonds, out = list(imported.people), list(imported.pair_bonds), []
    while people or bonds:
        free_bonds = [b for b in bonds if not children[b["id"]]]
        free_people = [p for p in people if not bonds_of[p["id"]]]
        if not free_bonds and not free_people:
            raise ValueError("some people are their own ancestors in this file")
        for bond in free_bonds:
            bonds.remove(bond)
            bonds_of.subtract([bond["person_a"], bond["person_b"]])
            out.append((ItemKind.PairBond, bond))
        for person in free_people:
            people.remove(person)
            if "parents" in person:
                children[person["parents"]] -= 1
            out.append((ItemKind.Person, person))
    return out


def deltas(imported: Imported) -> list[dict]:
    """Every item added whole, ordered so that undoing the turn, newest first,
    takes each off with nothing hanging on it."""
    items = [
        *reversed(_removable(imported)),
        *((ItemKind.Event, event) for event in imported.events),
    ]
    return [
        {"item_kind": ItemKind.Diagram.value, "item_id": None, "field": "tags", "after": imported.tags},
        *(
            {"item_kind": kind.value, "item_id": item["id"], "field": None, "after": item}
            for kind, item in items
        ),
    ]


def save(user_id: int, name: str, imported: Imported, *, yes: bool) -> Diagram | None:
    """A new diagram holding the import, checked by the record's own rules.
    Without `yes` the check runs and nothing is kept."""
    diagram = Diagram(user_id=user_id, name=name, data=diagramjson.dumps({}))
    db.session.add(diagram)
    db.session.flush()
    if not yes:
        try:
            record.preview(diagram.id, deltas(imported), author=Author.Pro)
        finally:
            db.session.rollback()
        return None
    record.apply(
        diagram.id,
        deltas(imported),
        author=Author.Pro,
        turn_id=TURN.format(diagram.id),
        user_id=user_id,
    )
    return diagram
