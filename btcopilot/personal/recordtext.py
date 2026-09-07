"""The record as the coach reads it.

One compact rendering of the whole family record, ids first, so every chip and
every tool argument the coach writes can only be an id it was shown. What the
picture draws lives in the record; who did what when lives beside it, which is
why the interactions render separately.
"""

from btcopilot.personal.intake import _enum_val, _parse_iso_date
from btcopilot.personal.models import Interaction
from btcopilot.schema import DiagramData

SHIFTS = ("anxiety", "symptom", "functioning")


def date_text(value) -> str | None:
    """A record date as YYYY-MM-DD. Pro writes Qt date objects, the chat app
    writes strings, and both mean the same day."""
    parsed = _parse_iso_date(value)
    return parsed.isoformat() if parsed else None


def _name(person: dict) -> str:
    return " ".join(
        part for part in (person.get("name"), person.get("last_name")) if part
    ) or "unnamed"


def person_line(person: dict) -> str:
    line = f"{person['id']} {_name(person)}"
    gender = _enum_val(person.get("gender"))
    if gender:
        line += f" ({gender})"
    if person.get("parents") is not None:
        line += f" parents={person['parents']}"
    return line


def bond_line(bond: dict) -> str:
    married = bond.get("married")
    state = "married" if married else ("partners" if married is False else "unknown")
    return f"{bond['id']} {bond.get('person_a')}+{bond.get('person_b')} {state}"


def event_line(event: dict) -> str:
    parts = [
        str(event["id"]),
        date_text(event.get("dateTime")) or "undated",
        f"[{_enum_val(event.get('kind')) or 'shift'}]",
    ]
    for key in ("person", "spouse", "child"):
        if event.get(key) is not None:
            parts.append(f"{key}={event[key]}")
    if event.get("description"):
        parts.append(f'"{event["description"]}"')
    for key in SHIFTS:
        value = _enum_val(event.get(key))
        if value:
            parts.append(f"{key}={value}")
    relationship = _enum_val(event.get("relationship"))
    if relationship:
        parts.append(f"relationship={relationship}")
    if event.get("relationshipTargets"):
        parts.append(f"targets={event['relationshipTargets']}")
    if event.get("relationshipTriangles"):
        parts.append(f"triangles={event['relationshipTriangles']}")
    certainty = _enum_val(event.get("dateCertainty"))
    if certainty and certainty != "certain":
        parts.append(f"date-{certainty}")
    return " ".join(parts)


def cluster_line(cluster: dict) -> str:
    words = cluster.get("name") or cluster.get("title") or ""

    source = _enum_val(cluster.get("source")) or "model"
    return f"{cluster['id']} \"{words}\" ({source}) events={cluster.get('eventIds') or []}"


def _section(title: str, lines: list[str]) -> str:
    return f"{title}\n" + "\n".join(lines) if lines else ""


def _rows(items: list[dict]) -> list[dict]:
    return [i for i in items if isinstance(i, dict) and i.get("id") is not None]


def render(data: DiagramData | None) -> str:
    """The whole record, ids first. Empty when nothing is stored yet."""
    if data is None:
        return ""
    events = sorted(
        _rows(data.events), key=lambda e: (date_text(e.get("dateTime")) or "", e["id"])
    )
    sections = [
        _section("PEOPLE", [person_line(p) for p in _rows(data.people)]),
        _section("PAIR BONDS", [bond_line(b) for b in _rows(data.pair_bonds)]),
        _section("EVENTS (date order)", [event_line(e) for e in events]),
        _section("CLUSTERS", [cluster_line(c) for c in _rows(data.clusters)]),
    ]
    return "\n\n".join(section for section in sections if section)


def interactions(rows: list[Interaction]) -> str:
    """What the user has been looking at, oldest first, as counts per item."""
    if not rows:
        return ""
    counts = {}
    for row in reversed(rows):
        key = (row.kind.value, row.item_kind.value, row.item_id)
        counts[key] = counts.get(key, 0) + 1
    lines = [
        f"{kind} {item_kind} {item_id}"
        + (f" x{count}" if count > 1 else "")
        for (kind, item_kind, item_id), count in counts.items()
    ]
    return "WHAT THE USER HAS BEEN DOING\n" + "\n".join(lines)
