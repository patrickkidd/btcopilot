"""A desktop Family Diagram file made into a new diagram in the chat app.

What the person entered is copied as it stands; what only drew the old
picture is dropped. The coding pass then reads what the mapping left for it,
the ids are renumbered, and the whole import is one change-log turn, so one
undo takes it back [Oracle: R-0850]. Every choice made along the way is a
Decision, for the ledger the person is sent [Oracle: R-0873]."""

import collections
import itertools
from dataclasses import dataclass, field, replace

from btcopilot import diagramjson, fdcoding, record
from btcopilot.coverage import CHILD_ROLE
from btcopilot.extensions import db
from btcopilot.fdcoding import RAW
from btcopilot.fdledger import Decision
from btcopilot.models import Author, Diagram
from btcopilot.prompts import Role
from btcopilot.record import generic_key
from btcopilot.schema import (
    RESERVED_ITEM_IDS,
    DateCertainty,
    EventKind,
    ItemKind,
    NotedFact,
    PersonKind,
    RelationshipKind,
    VariableShift,
    enum_val,
)

TURN = "fd-import:{}"
# The desktop's own words for two kinds the app names otherwise [Oracle: R-0864].
MOVED = "moved"
OLD_SHIFT = "variable-shift"
VALUES = {
    **{
        name: {v.value for v in VariableShift}
        for name in ("symptom", "anxiety", "functioning")
    },
    "relationship": {v.value for v in RelationshipKind},
}
TRIANGLES = (RelationshipKind.Inside.value, RelationshipKind.Outside.value)
PERSON = {
    "name": "name",
    "lastName": "last_name",
    "gender": "gender",
    "notes": "notes",
    "alias": "alias",
    "nickName": "nickName",
    "middleName": "middleName",
    "birthName": "birthName",
}
PERSON_USED = {
    "kind",
    "id",
    "parents",
    "childOf",
    "primary",
    "deceased",
    "deceasedReason",
    "diagramNotes",
}
BOND = ("person_a", "person_b", "married")
BOND_USED = {"kind", "id", "notes", "diagramNotes", *BOND}
EVENT = (
    "person",
    "spouse",
    "child",
    "description",
    "notes",
    "location",
    "relationshipTargets",
    "relationshipTriangles",
    "tags",
)
DATES = ("dateTime", "endDateTime")
EVENT_USED = {
    "id",
    "kind",
    "unsure",
    "dateCertainty",
    "dynamicProperties",
    *DATES,
    *VALUES,
}
LINE_USED = {
    "id",
    "kind",
    "person",
    "target",
    "event",
    "notes",
    "tags",
    "startDate",
    "endDate",
    "startDateUnsure",
}
DROPPED = ("layers", "layerItems", "multipleBirths", "items", "pruned")
COLLECTIONS = ("people", "pair_bonds", "events")
PERSON_REFS = ("person", "spouse", "child")
PERSON_LISTS = ("relationshipTargets", "relationshipTriangles")


@dataclass
class Imported:
    data: dict
    decisions: list[Decision] = field(default_factory=list)
    # The new ids of the people the file marked primary, when not exactly one
    # was, so the coach's first turn can ask which one is you [Oracle: R-0871].
    primaries: list[int] = field(default_factory=list)
    # Which item of the file each item of `data` came from, by its id there.
    labels: dict[int, str] = field(default_factory=dict)
    # The file's relationship lines that went onto an event, to that event's id.
    joined: dict[str, int] = field(default_factory=dict)
    lines: int = 0
    dropped: collections.Counter = field(default_factory=collections.Counter)

    def summary(self) -> dict:
        return {
            "people": len(self.data["people"]),
            "events": len(self.data["events"]),
            "pair_bonds": len(self.data["pair_bonds"]),
            "relationship_lines": self.lines,
            "choices": len(self.decisions),
            "dropped": sum(self.dropped.values()),
        }

    def decide(self, item: str, name: str, before, after, reason: str) -> None:
        self.decisions.append(Decision(item, name, _text(before), _text(after), reason))


def _text(value) -> str:
    return "" if value is None else str(value)


def _kept(value) -> bool:
    return value not in (None, "", [], {}, False)


def _drop(out: Imported, collection: str, chunk: dict, used) -> None:
    for key, value in chunk.items():
        if key not in used and _kept(value):
            out.dropped[f"{collection}.{key}"] += 1


def _set(item: dict, key: str, value) -> None:
    if _kept(value):
        item[key] = value


def _raw(item: dict, key: str, value) -> None:
    if _kept(value):
        item.setdefault(RAW, {})[key] = value


def _person(out: Imported, chunk: dict) -> dict:
    person = {"id": chunk["id"]}
    for theirs, ours in PERSON.items():
        _set(person, ours, enum_val(chunk.get(theirs)))
    parents = chunk.get("parents") or (chunk.get("childOf") or {}).get("parents")
    _set(person, "parents", parents)
    _raw(person, "diagramNotes", chunk.get("diagramNotes"))
    out.labels[chunk["id"]] = f"person {chunk['id']}"
    _drop(out, "people", chunk, PERSON_USED | set(PERSON))
    return person


def _bond(out: Imported, chunk: dict) -> dict:
    bond = {"id": chunk["id"], **{key: chunk.get(key) for key in BOND}}
    _raw(bond, "notes", chunk.get("notes"))
    _raw(bond, "diagramNotes", chunk.get("diagramNotes"))
    out.labels[chunk["id"]] = f"pair-bond {chunk['id']}"
    _drop(out, "pair_bonds", chunk, BOND_USED)
    return bond


def _value(out: Imported, event: dict, name: str, raw, label: str) -> None:
    """A hand-coded value copied as it stands, or left blank with the file's
    text kept for the coding pass when it is not one of the app's values
    [Oracle: R-0859]."""
    raw = enum_val(raw)
    if not _kept(raw):
        return
    if raw in VALUES[name]:
        event[name] = raw
        return
    _raw(event, name, str(raw))
    out.decide(
        label,
        name,
        raw,
        "",
        "The app has no such value, so the coding pass reads the file's word.",
    )


def _dates(out: Imported, event: dict, chunk: dict, label: str, names=DATES) -> None:
    """The day kept as the app stores it; a time of day is only in the ledger."""
    for ours, theirs in zip(DATES, names):
        value = chunk.get(theirs)
        if not value:
            continue
        event[ours] = value[:10]
        if len(value) > 10:
            out.decide(
                label,
                theirs,
                value,
                value[:10],
                "The app keeps the day only, not the time of day.",
            )


def _event(out: Imported, chunk: dict) -> dict:
    kind = enum_val(chunk["kind"])
    label = f"event {chunk['id']}"
    event = {"id": chunk["id"]}
    if kind == MOVED:
        event.update(kind=EventKind.Noted.value, item=NotedFact.Places.value)
        out.decide(
            label,
            "kind",
            kind,
            EventKind.Noted.value,
            "The app keeps a move as a noted event about places.",
        )
    elif kind == OLD_SHIFT:
        event["kind"] = EventKind.Shift.value
    else:
        event["kind"] = EventKind(kind).value
    for key in EVENT:
        _set(event, key, chunk.get(key))
    _dates(out, event, chunk, label)
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
        _value(out, event, name, own if _kept(own) else coded.get(name), label)
    out.labels[chunk["id"]] = label
    _drop(out, "events", chunk, EVENT_USED | set(EVENT))
    _drop(out, "events.dynamicProperties", coded, VALUES)
    return event


def _aimed(event: dict, kind: str) -> bool:
    """The event names whom a move of this kind was aimed at, and for an
    inside or outside move the third person."""
    return bool(event.get("relationshipTargets")) and (
        kind not in TRIANGLES or bool(event.get("relationshipTriangles"))
    )


def _relationship(out: Imported, event: dict, kind: str, label: str) -> None:
    """A line's kind goes on its event, unless the event names no other
    person, or an inside or outside no third person: then the coding pass
    reads it [Oracle: R-0869]."""
    if _aimed(event, kind):
        _value(out, event, "relationship", kind, label)
        return
    _raw(event, "relationship", kind)
    out.decide(
        label,
        "kind",
        kind,
        "",
        "The line names no other person enough to code it, so the coding pass reads it.",
    )


def _unaimed(out: Imported) -> None:
    """An event's own hand-coded move that names no other person enough to
    code it is read by the coding pass, as a line's is [Oracle: R-0869]."""
    for event in out.data["events"]:
        kind = event.get("relationship")
        if kind is None or _aimed(event, kind):
            continue
        _raw(event, "relationship", event.pop("relationship"))
        out.decide(
            f"event {event['id']}",
            "relationship",
            kind,
            "",
            "The event names no other person enough to code it, so the coding pass reads it.",
        )


def _line(out: Imported, chunk: dict, events: dict) -> dict | None:
    """A relationship line puts its kind and target on the event it belongs
    to, or becomes a shift of its own on its person."""
    kind = enum_val(chunk["kind"])
    target = chunk.get("target")
    label = f"relationship line {chunk['id']}"
    out.lines += 1
    _drop(out, "emotions", chunk, LINE_USED)
    if chunk.get("event") is not None:
        event = events[chunk["event"]]
        out.joined[label] = event["id"]
        if target is not None and target not in event.setdefault(
            "relationshipTargets", []
        ):
            event["relationshipTargets"].append(target)
        if "relationship" not in event and "relationship" not in event.get(RAW, {}):
            _relationship(out, event, kind, label)
        notes = chunk.get("notes")
        if _kept(notes) and notes not in (event.get("notes") or ""):
            event["notes"] = (
                f"{event['notes']}\n\n{notes}" if event.get("notes") else notes
            )
            out.decide(
                label,
                "notes",
                notes,
                event["notes"],
                "The line's notes are added to its event's notes.",
            )
        return None
    event = {
        "id": chunk["id"],
        "kind": EventKind.Shift.value,
        "person": chunk.get("person"),
    }
    _dates(out, event, chunk, label, ("startDate", "endDate"))
    if "dateTime" not in event:
        event["dateCertainty"] = DateCertainty.Unknown.value
    elif chunk.get("startDateUnsure"):
        event["dateCertainty"] = DateCertainty.Approximate.value
    else:
        event["dateCertainty"] = DateCertainty.Certain.value
    _set(event, "relationshipTargets", [target] if target is not None else [])
    _relationship(out, event, kind, label)
    if "relationship" in event:
        name = RelationshipKind(event["relationship"]).menuLabel()
        event.update(description=name, title=f"{name} move")
    _set(event, "notes", chunk.get("notes"))
    _set(event, "tags", chunk.get("tags"))
    out.labels[chunk["id"]] = label
    return event


def _primary(out: Imported, chunks: list[dict]) -> None:
    """Only one person is the one the diagram is about; when the file marks
    none or several, none is set [Oracle: R-0871]."""
    marked = [chunk["id"] for chunk in chunks if chunk.get("primary")]
    people = {person["id"]: person for person in out.data["people"]}
    if len(marked) == 1:
        people[marked[0]]["primary"] = True
        return
    out.primaries = marked
    out.decide(
        "diagram",
        "primary",
        f"{len(marked)} people marked primary",
        "none marked",
        "The file does not mark exactly one primary person, so the coach asks which one is you.",
    )


def _deaths(out: Imported, chunks: list[dict], ids) -> None:
    """A person ticked deceased has a death event; cause of death goes on it
    [Oracle: R-0870]."""
    deaths = {
        e.get("person"): e
        for e in out.data["events"]
        if e["kind"] == EventKind.Death.value
    }
    for chunk in chunks:
        reason = chunk.get("deceasedReason") or ""
        if not chunk.get("deceased") and not reason:
            continue
        label = f"person {chunk['id']}"
        death = deaths.get(chunk["id"])
        if death is None:
            death = {
                "id": next(ids),
                "kind": EventKind.Death.value,
                "person": chunk["id"],
                "dateCertainty": DateCertainty.Unknown.value,
            }
            out.data["events"].append(death)
            out.decide(
                label,
                "deceased",
                True,
                "a death event, date unknown",
                "The file ticks them deceased with no death event.",
            )
        if reason and reason not in (death.get("description") or ""):
            death["description"] = (
                f"{death['description']}; {reason}"
                if death.get("description")
                else reason
            )
            out.decide(
                label,
                "deceasedReason",
                reason,
                death["description"],
                "Cause of death goes on the death event.",
            )


def _word(person: dict, role: tuple) -> str:
    woman, man, anyone = role
    return {PersonKind.Female: woman, PersonKind.Male: man}.get(
        person.get("gender"), anyone
    )


def _anchors(person: dict, bonds: dict, bonds_of: dict, children: dict):
    """Whom an unnamed person can be named after, the way the coach names
    them: a child's parent first, then a partner, then a parent's child."""
    for bond in bonds_of[person["id"]]:
        for child in children[bond["id"]]:
            yield child, _word(person, (Role.Mother.value, Role.Father.value, "parent"))
    for bond in bonds_of[person["id"]]:
        yield (
            bond["person_b"] if bond["person_a"] == person["id"] else bond["person_a"]
        ), Role.Partner.value
    parents = bonds.get(person.get("parents"))
    for side in ("person_a", "person_b") if parents else ():
        yield parents[side], CHILD_ROLE


def _named(person: dict) -> bool:
    return bool((person.get("name") or "").strip())


def _forms(anchor: dict, word: str, counted: bool, taken: dict):
    """The names an unnamed person may take after one relative: by first
    name, by full name where someone else shares the first, then counted where
    even that is taken: the relative's second partner, or a second relative
    of the same name."""
    full = " ".join(filter(None, (anchor["name"], anchor.get("last_name"))))
    yield f"{anchor['name']}'s {word}"
    yield f"{full}'s {word}"
    if not counted:
        return
    same = taken.get(generic_key({"name": f"{full}'s {word}"})) == anchor["id"]
    for n in itertools.count(2):
        yield f"{full}'s {word} {n}" if same else f"{full} {n}'s {word}"


def _names(out: Imported) -> None:
    """People the file left unnamed are named by their family position after
    their nearest named relative, each pass naming after the people the passes
    before it named [Oracle: R-0867]. Nobody is left without a name: a person
    with no named relative at all is numbered in file order."""
    people = out.data["people"]
    by_id = {person["id"]: person for person in people}
    bonds = {bond["id"]: bond for bond in out.data["pair_bonds"]}
    bonds_of = collections.defaultdict(list)
    children = collections.defaultdict(list)
    for bond in bonds.values():
        bonds_of[bond["person_a"]].append(bond)
        bonds_of[bond["person_b"]].append(bond)
    for person in people:
        if "parents" in person:
            children[person["parents"]].append(person["id"])
    # Each generic name in use, to the person it was given after.
    taken = {key: None for key in map(generic_key, people) if key}

    def name(person: dict, given: str, after, reason: str) -> None:
        person["name"] = given
        if key := generic_key(person):
            taken[key] = after
        out.decide(f"person {person['id']}", "name", "", given, reason)

    unnamed = [p for p in people if not _named(p)]
    counted = False
    while unnamed:
        known = {p["id"] for p in people if _named(p)}
        left = []
        for person in unnamed:
            given = next(
                (
                    (form, anchor)
                    for anchor, word in _anchors(person, bonds, bonds_of, children)
                    if anchor in known
                    for form in _forms(by_id[anchor], word, counted, taken)
                    if generic_key({"name": form}) not in taken
                ),
                None,
            )
            if given is None:
                left.append(person)
                continue
            name(
                person,
                *given,
                "The file gives no name, so they are named by their place in the family.",
            )
        if len(left) == len(unnamed):
            if counted:
                break
            counted = True
        unnamed = left
    for n, person in enumerate(unnamed, 1):
        name(
            person,
            f"Unnamed person {n}",
            None,
            "The file gives no name and nobody in their family has one to name them by.",
        )


def _notes(fd: dict) -> str:
    """The words written on the diagram itself: its callouts and its layers'
    notes."""
    texts = [item.get("text") for item in fd.get("layerItems") or []]
    texts += [layer.get("notes") for layer in fd.get("layers") or []]
    return "\n\n".join(text for text in texts if _kept(text))


def convert(fd: dict) -> Imported:
    """The file's items mapped onto the app's, under the file's own ids."""
    out = Imported(data={"tags": list(fd.get("tags") or [])})
    chunks = fd.get("people") or []
    out.data["people"] = [_person(out, chunk) for chunk in chunks]
    bonds = fd.get("pair_bonds") or fd.get("marriages") or []
    out.data["pair_bonds"] = [_bond(out, chunk) for chunk in bonds]
    out.data["events"] = [_event(out, chunk) for chunk in fd.get("events") or []]
    by_id = {event["id"]: event for event in out.data["events"]}
    for chunk in fd.get("emotions") or []:
        made = _line(out, chunk, by_id)
        if made is not None:
            out.data["events"].append(made)
    _unaimed(out)
    _raw(out.data, "notes", _notes(fd))
    used = [
        item["id"]
        for name in (
            "people",
            "pair_bonds",
            "marriages",
            "events",
            "emotions",
            *DROPPED,
        )
        for item in fd.get(name) or []
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    _deaths(out, chunks, itertools.count(max(used + [fd.get("lastItemId") or 0]) + 1))
    _primary(out, chunks)
    _names(out)
    for name in DROPPED:
        out.dropped[name] += len(fd.get(name) or [])
    out.dropped = +out.dropped
    return out


def renumber(out: Imported) -> None:
    """Every item a new id past the ones the app reserves, each reference
    following it [Oracle: R-0850]."""
    data = out.data
    items = [item for name in COLLECTIONS for item in data[name]]
    new = {item["id"]: RESERVED_ITEM_IDS + n for n, item in enumerate(items, 1)}
    if len(new) != len(items):
        raise ValueError("two items in this file share an id")

    def ref(value, item: dict):
        if value is None:
            return None
        if value not in new:
            raise ValueError(
                f"item {item['id']} names item {value}, which is not in the file"
            )
        return new[value]

    for person in data["people"]:
        if "parents" in person:
            person["parents"] = ref(person["parents"], person)
    for bond in data["pair_bonds"]:
        for side in ("person_a", "person_b"):
            bond[side] = ref(bond[side], bond)
    for event in data["events"]:
        for key in PERSON_REFS:
            if key in event:
                event[key] = ref(event[key], event)
        for key in PERSON_LISTS:
            if key in event:
                event[key] = [ref(value, event) for value in event[key]]
    out.primaries = [new[pid] for pid in out.primaries]
    out.labels = {new[old]: label for old, label in out.labels.items() if old in new}
    out.joined = {label: new[old] for label, old in out.joined.items()}
    for item in items:
        item["id"] = new[item["id"]]


def _id(label: str) -> int | None:
    kind, _, number = label.rpartition(" ")
    return int(number) if kind == "event" and number.isdigit() else None


def _twins(out: Imported) -> None:
    """Events the record counts as one, the same kind, day, people and what
    moved, are made one: the first in the file keeps its place and the words
    of the others go into its notes."""
    kept = {}
    for event in list(out.data["events"]):
        first = kept.setdefault(record.twin_key(event), event)
        if first is event:
            continue
        words = [
            event.get(key) for key in ("title", "description", "location", "notes")
        ]
        said = "\n".join(dict.fromkeys(w for w in words if _kept(w)))
        first["notes"] = "\n\n".join(filter(None, (first.get("notes"), said)))
        _set(
            first,
            "tags",
            list(dict.fromkeys([*first.get("tags", []), *event.get("tags", [])])),
        )
        out.data["events"].remove(event)
        label = out.labels.pop(event["id"])
        out.joined[label] = first["id"]
        out.joined.update(
            {
                name: first["id"]
                for name, eid in out.joined.items()
                if eid == event["id"]
            }
        )
        out.decide(
            label,
            "notes",
            said,
            first["notes"],
            f"The app counts it as the same event as {out.labels[first['id']]}: the "
            "same kind, day, people and what moved. Its words go into that event's notes.",
        )


def build(fd: dict, model=fdcoding.ask) -> Imported:
    """Read the file's items, code what the mapping left, then renumber."""
    out = convert(fd)
    out.data, coded = fdcoding.code(out.data, model)
    # The pass names an event by its id; a relationship line's own event is
    # named in the ledger by the line it came from.
    out.decisions += [
        replace(one, item=out.labels.get(_id(one.item), one.item)) for one in coded
    ]
    # Read by the pass; the ledger holds them from the file itself.
    for item in (out.data, *(i for name in COLLECTIONS for i in out.data[name])):
        item.pop(RAW, None)
    _twins(out)
    renumber(out)
    return out


def became(out: Imported) -> dict[str, str]:
    """What each item of the file is in the new diagram, by its name there."""
    said = {}
    for name in COLLECTIONS:
        for item in out.data[name]:
            label = out.labels.get(item["id"])
            if label is None:
                continue
            if name == "people":
                text = " ".join(
                    item.get(key) or "" for key in ("name", "last_name")
                ).strip()
                said[label] = f"person {item['id']}, {text}"
            elif name == "pair_bonds":
                said[label] = (
                    f"pair-bond {item['id']}, between persons {item['person_a']} and {item['person_b']}"
                )
            else:
                title = item.get("title") or item.get("description")
                said[label] = f"event {item['id']}, {item['kind']}" + (
                    f": {title}" if title else ""
                )
    events = {item["id"]: out.labels.get(item["id"]) for item in out.data["events"]}
    for label, event in out.joined.items():
        said[label] = f"part of {said.get(events[event]) or f'event {event}'}"
    return said


def _removable(data: dict) -> list[tuple[ItemKind, dict]]:
    """People and pair-bonds in an order each can come off with nothing hanging
    on it: a bond after its children, a person after their bonds."""
    bonds_of = collections.Counter(
        bond[side] for bond in data["pair_bonds"] for side in ("person_a", "person_b")
    )
    children = collections.Counter(
        p["parents"] for p in data["people"] if "parents" in p
    )
    people, bonds, out = list(data["people"]), list(data["pair_bonds"]), []
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


def deltas(out: Imported) -> list[dict]:
    """Every item added whole, ordered so that undoing the turn, newest first,
    takes each off with nothing hanging on it."""
    items = [
        *reversed(_removable(out.data)),
        *((ItemKind.Event, event) for event in out.data["events"]),
    ]
    return [
        *(
            {
                "item_kind": ItemKind.Diagram.value,
                "item_id": None,
                "field": key,
                "after": value,
            }
            for key, value in out.data.items()
            if key not in COLLECTIONS
        ),
        *(
            {
                "item_kind": kind.value,
                "item_id": item["id"],
                "field": None,
                "after": item,
            }
            for kind, item in items
        ),
    ]


def save(user_id: int, name: str, out: Imported, *, yes: bool) -> Diagram | None:
    """A new diagram holding the import, checked by the record's own rules.
    Without `yes` the check runs and nothing is kept."""
    diagram = Diagram(user_id=user_id, name=name, data=diagramjson.dumps({}))
    db.session.add(diagram)
    db.session.flush()
    if not yes:
        try:
            record.preview(diagram.id, deltas(out), author=Author.Pro)
        finally:
            db.session.rollback()
        return None
    record.apply(
        diagram.id,
        deltas(out),
        author=Author.Pro,
        turn_id=TURN.format(diagram.id),
        user_id=user_id,
    )
    return diagram
