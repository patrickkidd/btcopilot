"""A desktop Family Diagram file made into a new diagram in the chat app.

What the person entered is copied as it stands; what only drew the old
picture is dropped. The coding pass then reads what the mapping left for it,
the ids are renumbered, and the whole import is one change-log turn, so one
undo takes it back [Oracle: R-0850]. Every choice made along the way is a
Decision, for the ledger the person is sent [Oracle: R-0873]."""

import collections
import copy
import itertools
import uuid
from dataclasses import dataclass, field, replace

# fdmerge renumbers with this module and this module merges with fdmerge;
# neither uses the other at import time.
from btcopilot import diagramjson, fdcoding, fdmerge, record
from btcopilot.coverage import CHILD_ROLE
from btcopilot.extensions import db
from btcopilot.familymatch import unnamed
from btcopilot.fdcoding import RAW
from btcopilot.fdledger import Decision
from btcopilot.metered import Metered
from btcopilot.models import Author, Diagram, Observation, ObservationKind
from btcopilot.models.modelcall import ModelCall, Purpose
from btcopilot.prompts import Role
from btcopilot.record import generic_key
from btcopilot.schema import (
    ITEM_COLLECTIONS,
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
# A couple the file ticks separated or divorced, to the event the app records it as.
PARTED = {"divorced": EventKind.Divorced.value, "separated": EventKind.Separated.value}
BOND_USED = {"kind", "id", "notes", "diagramNotes", *BOND, *PARTED}
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
ADDED = (*COLLECTIONS, "questions")
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
    # The diagram it was built into, its version and its data as read then.
    into: int | None = None
    version: int | None = None
    base: dict | None = None
    # The merge's questions for the coach, held on the file's people.
    held: list[dict] = field(default_factory=list)
    # How many people, events and pair-bonds the file brought, how many of
    # the events the coding pass drew from its notes, and how its people and
    # events found their place; into a new diagram, all by the rules.
    brought: dict[str, int] = field(default_factory=dict)
    placed: dict[fdmerge.Placed, collections.Counter] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "people": len(self.data["people"]),
            "events": len(self.data["events"]),
            "pair_bonds": len(self.data["pair_bonds"]),
            "relationship_lines": self.lines,
            "choices": len(self.decisions),
            "dropped": sum(self.dropped.values()),
            "held_questions": len(self.held),
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


def _partings(out: Imported, chunks: list[dict], ids) -> None:
    """A couple ticked divorced has a divorce event, one ticked only separated
    a separation event, each date unknown where the file has none, so the
    tick is not lost [Oracle: R-0870]."""
    for chunk in chunks:
        flag = next((flag for flag in PARTED if chunk.get(flag)), None)
        if flag is None:
            continue
        couple = {chunk["person_a"], chunk["person_b"]}
        kinds = {
            e["kind"]
            for e in out.data["events"]
            if {e.get("person"), e.get("spouse")} == couple
        }
        if {PARTED[flag], PARTED["divorced"]} & kinds:
            continue
        out.data["events"].append(
            {
                "id": next(ids),
                "kind": PARTED[flag],
                "person": chunk["person_a"],
                "spouse": chunk["person_b"],
                "dateCertainty": DateCertainty.Unknown.value,
            }
        )
        out.decide(
            f"pair-bond {chunk['id']}",
            flag,
            True,
            f"a {PARTED[flag]} event, date unknown",
            f"The file ticks the couple {flag} with no {PARTED[flag]} event.",
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
    ids = itertools.count(max(used + [fd.get("lastItemId") or 0]) + 1)
    _deaths(out, chunks, ids)
    _partings(out, bonds, ids)
    _primary(out, chunks)
    _names(out)
    for name in DROPPED:
        out.dropped[name] += len(fd.get(name) or [])
    out.dropped = +out.dropped
    return out


def renumber(data: dict, start: int) -> dict[int, int]:
    """Every item a new id from `start` on, each reference following it;
    returns each old id's new one [Oracle: R-0850]."""
    items = [item for name in COLLECTIONS for item in data[name]]
    new = {item["id"]: start + n for n, item in enumerate(items)}
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
    for item in items:
        item["id"] = new[item["id"]]
    return new


def _id(label: str) -> int | None:
    kind, _, number = label.rpartition(" ")
    return int(number) if kind == "event" and number.isdigit() else None


#: An event's own words besides its notes, kept in the notes of the event it merges into.
WORDS = ("title", "description", "location")
#: What a refused event no longer says when it falls back to a noted event.
MOVED_FIELDS = (*fdcoding.VARIABLES, "relationship", *fdcoding.MOVES)
#: Of the events the file brought, those the coding pass drew from its notes.
DRAWN = "drawn"


def _twins(out: Imported) -> None:
    """Events the record counts as one, the same kind, day, people, what
    moved and item, are made one: the first in the file keeps its place, and
    its notes are followed by the others' words it does not already hold."""
    kept = {}
    for event in list(out.data["events"]):
        first = kept.setdefault(record.twin_key(event), event)
        if first is event:
            continue
        held = {first.get(key) for key in WORDS}
        words = [event.get(key) for key in WORDS if event.get(key) not in held]
        said = "\n".join(
            dict.fromkeys(w for w in (*words, event.get("notes")) if _kept(w))
        )
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
            "same kind, day, people, what moved and item. Its words go into that event's notes.",
        )


def build(fd: dict, model, into: Diagram | None = None) -> Imported:
    """Read the file's items, code what the mapping left, then renumber; with
    `into`, the items are brought into that diagram [Oracle: R-0851]."""
    out = convert(fd)
    filed = {event["id"] for event in out.data["events"]}
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
    drawn = sum(event["id"] not in filed for event in out.data["events"])
    new = renumber(out.data, RESERVED_ITEM_IDS + 1)
    _moved(out, new)
    out.brought = {name: len(out.data[name]) for name in COLLECTIONS}
    out.brought[DRAWN] = drawn
    out.placed = {way: collections.Counter() for way in fdmerge.Placed}
    out.placed[fdmerge.Placed.Rules].update(
        people=out.brought["people"], events=out.brought["events"]
    )
    if into is not None:
        _merge(out, into, model)
    _settle(out)
    return out


def _moved(out: Imported, new: dict[int, int], part=lambda i: i) -> None:
    """The file's names follow each item to its new id, or, where `part`
    says it was joined to another item, to that one."""
    ids = {item["id"] for name in COLLECTIONS for item in out.data[name]}

    def to(old: int) -> int | None:
        return part(new[old]) if old in new else None

    out.primaries = [to(pid) for pid in out.primaries if to(pid) in ids]
    out.joined = {label: to(old) for label, old in out.joined.items() if to(old) in ids}
    labels = {}
    for old, label in out.labels.items():
        if new.get(old) in ids:
            labels[new[old]] = label
        elif to(old) in ids:
            out.joined[label] = to(old)
    out.labels = labels


def _merge(out: Imported, into: Diagram, model) -> None:
    """The coded file merged into the diagram as it stands; the merge's
    choices name the file's items by their names in the file."""
    out.into, out.version = into.id, into.version
    out.base = diagramjson.loads(into.data)
    merge = fdmerge.Merge(out.base, out.data, model)
    out.data, decisions, out.held = merge.run()
    out.placed = merge.placed
    out.data["questions"] = [*(out.data.get("questions") or []), *out.held]
    out.decisions += [replace(one, item=_filed(out, one.item)) for one in decisions]
    if any(p.get("primary") and not unnamed(p.get("name")) for p in out.base["people"]):
        out.primaries = []
    _moved(out, {old: new for new, old in merge.old.items()}, merge.final)


def _refused(out: Imported) -> dict[tuple[ItemKind, str], record.Invalid]:
    """Each item the record's rules refuse on the diagram as the import would
    leave it, with why; checked item by item only when the whole is refused."""
    data = copy.deepcopy(out.base or {})
    applied = record.compress(
        [d for delta in deltas(out) for d in record.enact(data, delta)]
    )
    try:
        record.validate(data, applied, Author.Pro, undoing=False)
        return {}
    except record.Invalid as invalid:
        whole = invalid
    items = collections.defaultdict(list)
    for delta in applied:
        if delta["item_id"] is not None:
            items[ItemKind(delta["item_kind"]), str(delta["item_id"])].append(delta)
    found = {}
    for key, group in items.items():
        try:
            record.validate(data, group, Author.Pro, undoing=False)
        except record.Invalid as invalid:
            found[key] = invalid
    if not found:
        raise whole
    return found


def _settle(out: Imported) -> None:
    """One refusal never stops the import: each item the record's rules
    refuse falls back by itself, a step at a time, each step a choice in the
    ledger [Oracle: R-0868]. A refusal no step answers stops it."""
    steps = collections.Counter()
    while refused := _refused(out):
        for key, invalid in refused.items():
            while not _fall(out, *key, steps[key], invalid):
                steps[key] += 1
            steps[key] += 1


def _fall(
    out: Imported, kind: ItemKind, item_id: str, step: int, invalid: record.Invalid
) -> bool:
    """Step `step` of an item's fall back; False when it changes nothing. The
    diagram's own item keeps what it had; the file's event takes the coding
    pass's fallback, then becomes a noted event keeping its words, then is left
    out with its words in the ledger; the file's person takes a counted name;
    the import's question is left out."""
    name = ITEM_COLLECTIONS[kind]
    item = next(i for i in out.data[name] if str(i["id"]) == item_id)
    own = next(
        (i for i in (out.base or {}).get(name) or [] if str(i["id"]) == item_id),
        None,
    )
    why = f"The record's rules refused it: {invalid.plain}"
    if own is not None:
        steps = [lambda: _restore(out, kind, item, own, why)]
    elif kind is ItemKind.Event:
        steps = [
            lambda: _change(out, item, fdcoding.fallback(out.data, item), why),
            lambda: _noted(out, item, why),
            lambda: _left(out, kind, item, why),
        ]
    elif kind is ItemKind.Person:
        steps = [lambda: _counted(out, item, why)]
    elif kind is ItemKind.Question:
        steps = [lambda: _left(out, kind, item, why)]
    else:
        steps = []
    if step >= len(steps):
        raise invalid
    return steps[step]()


def _label(out: Imported, kind: ItemKind, item: dict) -> str:
    return out.labels.get(item["id"]) or f"{_noun(kind)} {item['id']}"


def _noun(kind: ItemKind) -> str:
    return kind.value.replace("_", "-")


def _change(out: Imported, event: dict, changes: dict, why: str) -> bool:
    label = _label(out, ItemKind.Event, event)
    fdcoding.change(out.decisions, label, event, changes, why)
    return bool(changes)


def _restore(out: Imported, kind: ItemKind, item: dict, own: dict, why: str) -> bool:
    items = out.data[ITEM_COLLECTIONS[kind]]
    items[items.index(item)] = copy.deepcopy(own)
    out.decide(
        f"{_noun(kind)} {own['id']} of the diagram",
        "",
        "",
        "",
        f"{why} The diagram's own item keeps what it had.",
    )
    return True


def _noted(out: Imported, event: dict, why: str) -> bool:
    if event["kind"] not in fdcoding.WORDED:
        return False
    changes = {key: None for key in MOVED_FIELDS if event.get(key)}
    if event["kind"] != EventKind.Noted.value:
        changes["kind"] = EventKind.Noted.value
    if not changes:
        return False
    changes |= fdcoding.plain(out.data, {**event, **changes})
    return _change(
        out,
        event,
        changes,
        f"{why} It is kept as a noted event with the file's words, so nothing is lost.",
    )


def _left(out: Imported, kind: ItemKind, item: dict, why: str) -> bool:
    out.data[ITEM_COLLECTIONS[kind]].remove(item)
    if item in out.held:
        out.held.remove(item)
    label = _label(out, kind, item)
    out.labels.pop(item["id"], None)
    out.joined = {k: v for k, v in out.joined.items() if v != item["id"]}
    words = [item.get(key) for key in ("title", "description", "notes", "text")]
    out.decide(
        label,
        "",
        "\n".join(dict.fromkeys(w for w in words if _kept(w))),
        "left out",
        f"{why} It is left out of the diagram; what the file said is in this record.",
    )
    return True


def _counted(out: Imported, person: dict, why: str) -> bool:
    taken = {p.get("name") for p in out.data["people"]}
    given = next(
        f"{person['name']} {n}"
        for n in itertools.count(2)
        if f"{person['name']} {n}" not in taken
    )
    out.decide(_label(out, ItemKind.Person, person), "name", person["name"], given, why)
    person["name"] = given
    return True


def _filed(out: Imported, item: str) -> str:
    """A merge choice's item, named by the file's item it came from."""
    number = item.rpartition(" ")[2]
    return out.labels.get(int(number), item) if number.isdigit() else item


def _said(name: str, item: dict) -> str:
    if name == "people":
        text = " ".join(item.get(key) or "" for key in ("name", "last_name")).strip()
        return f"person {item['id']}, {text}"
    if name == "pair_bonds":
        return f"pair-bond {item['id']}, between persons {item['person_a']} and {item['person_b']}"
    title = item.get("title") or item.get("description")
    return f"event {item['id']}, {item['kind']}" + (f": {title}" if title else "")


def became(out: Imported) -> dict[str, str]:
    """What each item of the file is in the diagram, by its name there."""
    items = {
        item["id"]: (name, item) for name in COLLECTIONS for item in out.data[name]
    }
    said = {label: _said(*items[i]) for i, label in out.labels.items()}
    for label, i in out.joined.items():
        name, item = items[i]
        said[label] = ("the same as " if name == "people" else "part of ") + _said(
            name, item
        )
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
    """Every item the import adds, added whole and ordered so that undoing the
    turn, newest first, takes each off with nothing hanging on it; then what
    it changes on the diagram's own items, and the questions it holds."""
    base = out.base or {}
    had = {(name, item["id"]) for name in ADDED for item in base.get(name) or []}
    added = {
        name: [i for i in out.data.get(name) or [] if (name, i["id"]) not in had]
        for name in ADDED
    }
    items = [
        *reversed(_removable(added)),
        *((ItemKind.Event, event) for event in added["events"]),
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
            if key not in ITEM_COLLECTIONS.values() and value != base.get(key)
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
        *record.diff(
            {name: base.get(name) or [] for name in COLLECTIONS},
            {
                name: [i for i in out.data[name] if (name, i["id"]) in had]
                for name in COLLECTIONS
            },
        ),
        *(
            {
                "item_kind": ItemKind.Question.value,
                "item_id": question["id"],
                "field": None,
                "after": question,
            }
            for question in added["questions"]
        ),
    ]


def meter(user_id: int, into: Diagram | None = None, key: str | None = None) -> Metered:
    """The model as the import calls it: each call on the model-call ledger,
    under the import's own turn [Oracle: R-0876]; `key` names that turn, so
    the chat turn that brought a file in finds its import again."""
    return Metered(
        user_id,
        None if into is None else into.id,
        TURN.format(key or uuid.uuid4().hex),
        Purpose.Import,
    )


def save(
    user_id: int,
    name: str,
    out: Imported,
    *,
    yes: bool,
    turn: str | None = None,
) -> Diagram | None:
    """A new diagram holding the import, or the diagram it was built into,
    checked by the record's own rules and written as one change-log turn.
    Without `yes` the check runs and nothing is kept. `turn` is the meter's,
    so the model calls made for a new diagram are put on it once it exists."""
    turn = turn or TURN.format(uuid.uuid4().hex)
    if out.into is None:
        diagram = Diagram(user_id=user_id, name=name, data=diagramjson.dumps({}))
        db.session.add(diagram)
        db.session.flush()
    else:
        diagram = db.session.get(Diagram, out.into)
        if diagram.version != out.version:
            raise ValueError(f"diagram {diagram.id} changed since the import read it")
    if not yes:
        try:
            record.preview(diagram.id, deltas(out), author=Author.Pro)
        finally:
            db.session.rollback()
        return None
    ModelCall.query.filter_by(turn_id=turn, diagram_id=None).update(
        {"diagram_id": diagram.id}
    )
    record.apply(
        diagram.id,
        deltas(out),
        author=Author.Pro,
        turn_id=turn,
        user_id=user_id,
    )
    db.session.add(
        Observation(
            diagram_id=diagram.id,
            turn_id=turn,
            kind=ObservationKind.Import,
            detail={
                **{name: out.brought[name] for name in COLLECTIONS},
                **{
                    way.value: {name: counts[name] for name in ("people", "events")}
                    for way, counts in out.placed.items()
                },
            },
        )
    )
    db.session.commit()
    return diagram
