"""The plain-text record of a desktop file's import, mailed to the person who
imported it: every field of every item in the file, what it became, and
every choice made bringing it over [Oracle: R-0873]."""

import collections
import datetime
from dataclasses import dataclass

from flask import current_app
from flask_mail import Message

from btcopilot import extensions
from btcopilot.config import Config


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


def _block(title: str, item: dict, became: dict, decided: dict) -> list[str]:
    lines = [f"-- {title} --", "In the file:", *(f"  {line}" for line in fields(item))]
    lines.append(f"In the new diagram: {became.get(title, 'not an item of its own')}")
    for one in decided.get(title, []):
        lines.append(
            f'Choice on {one.field}: the file said "{one.before}"; the new diagram has "{one.after}". {one.reason}'
        )
    return [*lines, ""]


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
    items tied to no one, then the diagram's own fields."""
    decided = collections.defaultdict(list)
    for one in decisions:
        decided[one.item].append(one)
    people = fd.get("people") or []
    events = fd.get("events") or []
    rels = fd.get("emotions") or []
    bonds = fd.get("pair_bonds") or fd.get("marriages") or []
    ids = {chunk["id"] for chunk in people}
    by_event = {event["id"]: event for event in events}
    events_of = collections.defaultdict(list)
    for event in events:
        events_of[_about(event) if _about(event) in ids else None].append(event)
    relsof = collections.defaultdict(list)
    for line in rels:
        owner = line.get("person")
        if owner is None and line.get("event") in by_event:
            owner = _about(by_event[line["event"]])
        relsof[owner if owner in ids else None].append(line)
    links = collections.defaultdict(list)
    for item in fd.get("items") or []:
        links[item.get("person") if item.get("person") in ids else None].append(item)

    out = [
        "Family Diagram import record",
        f"File: {file}",
        f"Saved by Family Diagram {fd.get('version') or 'unknown version'}",
        f"Imported: {today.isoformat()}",
        f"In the file: {len(people)} people, {len(events)} events, {len(bonds)} pair-bonds, "
        f"{len(rels)} relationship lines",
        f"Choices made: {len(decisions)}",
        "",
        "Each person below lists every field the file held for them, what they "
        "became in the new diagram, and any choice made; then their events and "
        "relationship lines the same way.",
        "",
    ]
    for chunk in people:
        out += [RULE, f"{_person(chunk)} (person {chunk['id']})", RULE]
        out += _block(f"person {chunk['id']}", chunk, became, decided)
        out += [
            line
            for event in events_of[chunk["id"]]
            for line in _block(f"event {event['id']}", event, became, decided)
        ]
        out += [
            line
            for one in relsof[chunk["id"]]
            for line in _block(f"relationship line {one['id']}", one, became, decided)
        ]
        out += [
            line
            for one in links[chunk["id"]]
            for line in _block(_drawn(one), one, became, decided)
        ]
    out += [RULE, "Tied to no one person", RULE]
    out += [
        line
        for bond in bonds
        for line in _block(f"pair-bond {bond['id']}", bond, became, decided)
    ]
    out += [
        line
        for event in events_of[None]
        for line in _block(f"event {event['id']}", event, became, decided)
    ]
    out += [
        line
        for one in relsof[None]
        for line in _block(f"relationship line {one['id']}", one, became, decided)
    ]
    out += [
        line
        for one in links[None]
        for line in _block(_drawn(one), one, became, decided)
    ]
    out += [RULE, "The diagram", RULE]
    out += _block(
        "diagram", {k: v for k, v in fd.items() if k not in SECTIONS}, became, decided
    )
    return "\n".join(out)


def send(email: str, file: str, name: str, ledger: str) -> None:
    """One email to the person who imported the file, the ledger attached;
    a development server with no mail server writes it to the log instead."""
    config = current_app.config
    body = BODY.format(file=file, name=name)
    if config["CONFIG"] == Config.Development and "MAIL_SERVER" not in config:
        current_app.logger.warning(f"[dev mail] {email} — {SUBJECT}\n{body}")
        return
    message = Message(
        SUBJECT,
        recipients=[email],
        sender=config["MAIL_DEFAULT_SENDER"],
        reply_to=config["ADMIN_EMAIL"],
    )
    message.body = body
    message.attach(attachment(name), "text/plain", ledger)
    extensions.mail.send(message)
