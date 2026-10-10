"""The plain-text record of a desktop file's import, mailed to the person who
imported it: every field of every item in the file, what it became, and
every choice made bringing it over [Oracle: R-0873]."""

import collections
import datetime
from dataclasses import dataclass

from flask import current_app

from btcopilot.auth.emails import deliver


@dataclass
class Decision:
    item: str
    field: str
    before: str
    after: str
    reason: str


# The desktop's own lock on real names; never written out.
SECRET = {"password", "masterKey"}
# Given their own sections, so not repeated among the diagram's fields.
SECTIONS = {"people", "events", "pair_bonds", "marriages", "emotions", "items"}
# What only drew the old picture: where and how big, its colours, its layers,
# a pair-bond's drawn parts, and the switches for what was shown.
DRAWING = {
    "itemPos",
    "pos",
    "size",
    "color",
    "pencilColor",
    "layers",
    "layerPos",
    "nonLayerPos",
    "itemProperties",
    "detailsText",
    "detailsItem",
    "separationIndicator",
    "childOf",
    "includeOnDiagram",
    "scale",
    "scaleFactor",
    "width",
    "points",
    "order",
    "selected",
    "storeGeometry",
    "storePositionsInLayers",
    "centerPoint",
    "legendData",
    "exclusiveLayerSelection",
    "currentDateTime",
    "bigFont",
}
SWITCHES = ("hide", "show", "search_")
# Read first in each item; its other fields follow in the file's order.
FIRST = (
    "name",
    "middleName",
    "lastName",
    "nickName",
    "birthName",
    "alias",
    "kind",
    "dateTime",
    "endDateTime",
    "dateCertainty",
    "unsure",
    "startDate",
    "endDate",
    "gender",
    "deceased",
    "deceasedReason",
    "description",
    "notes",
    "diagramNotes",
    "person",
    "spouse",
    "child",
    "target",
    "person_a",
    "person_b",
)
DRAWN = "Drawing details from the desktop app"
# Births and adoptions are about the child; every other event about its person.
CHILD_KINDS = {"birth", "adopted"}
RULE = "=" * 40
SUBJECT = "Your Family Diagram file: a record of the import"
BODY = (
    "Attached is a record of everything in your file {file} and every choice "
    "made bringing it into the app as the diagram {name}.\n\n"
    "If something in the new diagram ever looks off, this record shows what "
    "your file said.\n\n"
    "Search it for a person's name: each person lists what the file held and "
    "what it became in the new diagram.\n\n"
    "Nothing in it needs any action from you. If you have questions, reply to "
    "this email.\n"
)


def attachment(name: str) -> str:
    return f"{name} - import record.txt"


def _value(value) -> str:
    if isinstance(value, (tuple, list)):
        return ", ".join(_value(one) for one in value)
    return str(value).replace("\n", "\n    ")


def _empty(value) -> bool:
    return value in (None, "", [], {}, ())


def fields(item: dict, prefix: str = "") -> list[str]:
    """Every field of an item as one "field: value" line, nested ones by a
    dotted name, empty ones left out."""
    lines = []
    for key, value in item.items():
        name = f"{prefix}{key}"
        if key in SECRET or _empty(value):
            continue
        if isinstance(value, dict):
            lines += fields(value, f"{name}.")
        elif isinstance(value, list) and any(isinstance(one, dict) for one in value):
            for n, one in enumerate(value, 1):
                lines += (
                    fields(one, f"{name} {n}.")
                    if isinstance(one, dict)
                    else [f"{name} {n}: {_value(one)}"]
                )
        else:
            lines.append(f"{name}: {_value(value)}")
    return lines


def _drawing(key: str) -> bool:
    return key in DRAWING or key.startswith(SWITCHES)


def _block(title: str, item: dict, became: dict, decided: dict) -> list[str]:
    said = {
        key: item[key]
        for key in sorted(
            item, key=lambda k: FIRST.index(k) if k in FIRST else len(FIRST)
        )
        if not _drawing(key)
    }
    lines = [f"-- {title} --", "In the file:", *(f"  {line}" for line in fields(said))]
    lines.append(f"In the new diagram: {became.get(title, 'not an item of its own')}")
    for one in decided.pop(title, []):
        lines.append(
            f'Choice on {one.field}: the file said "{one.before}"; the new diagram has "{one.after}". {one.reason}'
        )
    return [*lines, ""]


def _details(title: str, item: dict, whole: bool) -> list[str]:
    drawn = {key: value for key, value in item.items() if whole or _drawing(key)}
    lines = fields(drawn)
    return [f"{title}:", *(f"  {line}" for line in lines)] if lines else []


def _section(items: list[tuple[str, dict]], links: list[dict], became, decided):
    """Each item's meaningful fields, then what only drew the old picture:
    the items' drawing fields and the child-of links whole."""
    out = [
        line for title, item in items for line in _block(title, item, became, decided)
    ]
    drawn = [line for title, item in items for line in _details(title, item, False)]
    drawn += [line for link in links for line in _details(_drawn(link), link, True)]
    return out + ([DRAWN, *drawn, ""] if drawn else [])


def _about(event: dict) -> int | None:
    return (
        event.get("child") if event.get("kind") in CHILD_KINDS else event.get("person")
    )


def _drawn(item: dict) -> str:
    """The file's other items: a child's link to its parents, or a shape."""
    if item.get("person") is not None:
        return f"child-of link of person {item['person']}"
    return f"drawing item {item.get('id')}"


def _person(chunk: dict) -> str:
    name = " ".join(chunk.get(key) or "" for key in ("name", "lastName")).strip()
    return name or "no name in the file"


def text(
    file: str,
    fd: dict,
    became: dict[str, str],
    decisions: list[Decision],
    today: datetime.date,
) -> str:
    """The ledger, one person at a time in the file's own order, then the
    items tied to no one, then the diagram's own fields, then any choice
    about an item the file did not hold."""
    decided = collections.defaultdict(list)
    for one in decisions:
        decided[one.item].append(one)
    people = fd.get("people") or []
    events = fd.get("events") or []
    rels = fd.get("emotions") or []
    bonds = fd.get("pair_bonds") or fd.get("marriages") or []
    order = {chunk["id"]: n for n, chunk in enumerate(people)}
    by_event = {event["id"]: event for event in events}
    events_of = collections.defaultdict(list)
    for event in events:
        events_of[_about(event) if _about(event) in order else None].append(event)
    relsof = collections.defaultdict(list)
    for line in rels:
        owner = line.get("person")
        if owner is None and line.get("event") in by_event:
            owner = _about(by_event[line["event"]])
        relsof[owner if owner in order else None].append(line)
    bonds_of = collections.defaultdict(list)
    for bond in bonds:
        sides = [bond.get(side) for side in ("person_a", "person_b")]
        bonds_of[
            min((x for x in sides if x in order), key=order.get, default=None)
        ].append(bond)
    links = collections.defaultdict(list)
    for item in fd.get("items") or []:
        links[item.get("person") if item.get("person") in order else None].append(item)

    def items(pid) -> list[tuple[str, dict]]:
        return [
            *((f"event {event['id']}", event) for event in events_of[pid]),
            *((f"relationship line {one['id']}", one) for one in relsof[pid]),
            *((f"pair-bond {bond['id']}", bond) for bond in bonds_of[pid]),
        ]

    out = [
        "Family Diagram import record",
        f"File: {file}",
        f"Saved by Family Diagram {fd.get('version') or 'unknown version'}",
        f"Imported: {today.isoformat()}",
        f"In the file: {len(people)} people, {len(events)} events, {len(bonds)} pair-bonds, "
        f"{len(rels)} relationship lines",
        f"Choices made: {len(decisions)}",
        "The file's password and master key are left out of this record, for security.",
        "",
        "Each person below lists every field the file held for them, what they "
        "became in the new diagram, and any choice made; then their events, "
        "relationship lines and pair-bonds the same way. What only drew the old "
        f'picture comes last in each section, under "{DRAWN}".',
        "",
    ]
    for chunk in people:
        out += [RULE, f"{_person(chunk)} (person {chunk['id']})", RULE]
        out += _section(
            [(f"person {chunk['id']}", chunk), *items(chunk["id"])],
            links[chunk["id"]],
            became,
            decided,
        )
    out += [RULE, "Tied to no one person", RULE]
    out += _section(items(None), links[None], became, decided)
    out += [RULE, "The diagram", RULE]
    out += _section(
        [("diagram", {k: v for k, v in fd.items() if k not in SECTIONS})],
        [],
        became,
        decided,
    )
    rest = [one for ones in decided.values() for one in ones]
    if rest:
        out += [RULE, "Choices about items the file did not hold", RULE]
        out += [
            f'{one.item}, {one.field or "the item"}: was "{one.before}"; '
            f'the new diagram has "{one.after}". {one.reason}'
            for one in rest
        ]
    return "\n".join(out)


def send(email: str, file: str, name: str, ledger: str) -> None:
    """One email to the person who imported the file, the ledger attached."""
    deliver(
        email,
        SUBJECT,
        BODY.format(file=file, name=name),
        reply_to=current_app.config["ADMIN_EMAIL"],
        attachment=(attachment(name), ledger.encode(), "text/plain; charset=utf-8"),
    )
