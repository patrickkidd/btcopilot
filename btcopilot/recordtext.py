"""The record as the coach reads it.

One compact rendering of the whole family record, ids first, so every chip and
every tool argument the coach writes can only be an id it was shown. What the
picture draws lives in the record; who did what when lives beside it, which is
why the interactions render separately.
"""

import json
from collections import Counter

from btcopilot import diagramjson, record
from btcopilot.models import Change, Interaction
from btcopilot.schema import (
    DECLINED,
    DiagramData,
    EventKind,
    ItemKind,
    QuestionState,
    enum_val,
    parse_date,
)
from btcopilot.timeline import _life_event

SHIFTS = ("anxiety", "symptom", "functioning")


def date_text(value) -> str | None:
    """A record date as YYYY-MM-DD.

    Three writers, one day: Pro writes a Qt date object, the chat app writes a
    string, and an undecoded record blob carries the converter's tagged form
    (btcopilot.diagramjson).
    """
    if isinstance(value, dict) and diagramjson.TAG in value:
        value = value["v"]
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def _name(person: dict) -> str:
    return " ".join(
        part for part in (person.get("name"), person.get("last_name")) if part
    ) or "unnamed"


SPEAKER = " — the person you are talking with"


def person_line(person: dict, speaker: bool = False, facts=()) -> str:
    line = f"{person['id']} {_name(person)}"
    gender = enum_val(person.get("gender"))
    if gender:
        line += f" ({gender})"
    if person.get("parents") is not None:
        line += f" parents={person['parents']}"
    line = " ".join([line, *facts])
    return line + SPEAKER if speaker else line


def bond_line(bond: dict) -> str:
    married = bond.get("married")
    state = "married" if married else ("partners" if married is False else "unknown")
    return f"{bond['id']} {bond.get('person_a')}+{bond.get('person_b')} {state}"


def event_line(event: dict) -> str:
    parts = [
        str(event["id"]),
        date_text(event.get("dateTime")) or "undated",
        f"[{enum_val(event.get('kind')) or 'shift'}]",
    ]
    end = date_text(event.get("endDateTime"))
    if end:
        parts.insert(2, f"to {end}")
    for key in ("person", "spouse", "child"):
        if event.get(key) is not None:
            parts.append(f"{key}={event[key]}")
    if event.get("description"):
        parts.append(f'"{event["description"]}"')
    if event.get("notes"):
        parts.append("(has notes)")
    for key in SHIFTS:
        value = enum_val(event.get(key))
        if value:
            parts.append(f"{key}={value}")
    relationship = enum_val(event.get("relationship"))
    if relationship:
        parts.append(f"relationship={relationship}")
    if event.get("relationshipTargets"):
        parts.append(f"targets={event['relationshipTargets']}")
    if event.get("relationshipTriangles"):
        parts.append(f"triangles={event['relationshipTriangles']}")
    certainty = enum_val(event.get("dateCertainty"))
    if certainty and certainty != "certain":
        parts.append(f"date-{certainty}")
    return " ".join(parts)


def _cluster_head(cluster: dict) -> str:
    words = cluster.get("name") or cluster.get("title") or ""

    # Never guess "model" here: source is what says whether a cluster may be
    # regrouped or renamed, and telling the coach the model made a grouping the
    # user may have named costs the user their name.
    source = enum_val(cluster.get("source")) or "unknown"
    return f"{cluster['id']} \"{words}\" ({source})"


def cluster_line(cluster: dict) -> str:
    line = f"{_cluster_head(cluster)} events={cluster.get('eventIds') or []}"
    reason = cluster.get("reason")
    return f"{line} — {reason}" if reason else line


def _declined(question: dict) -> bool:
    return question.get("outcome") in DECLINED


def on_map(question: dict) -> bool:
    """Open, or declined: the ones the coach keeps in view."""
    return question["state"] != QuestionState.Resolved or _declined(question)


def question_order(question: dict) -> tuple:
    return _declined(question), int(question["id"][1:])


def question_line(question: dict) -> str:
    status = "declined" if _declined(question) else question["state"]
    line = f'{question["id"]} {status} {question["kind"]} "{question["text"]}"'
    if question.get("item_kind"):
        line += f" about {question['item_kind']} {question['item_id']}"
    if status == QuestionState.Resolved:
        line += f" outcome={question['outcome']}"
    return line


QUESTIONS = "QUESTIONS (open, then declined: never ask a declined one again)"


def version_line(version: int) -> str:
    return f"Record version {version}."


def _field(field: str, value) -> str:
    return f"{field}={json.dumps(value, ensure_ascii=False)}"


def change_line(change: Change) -> str:
    """One write to the record: the version it made, who made it, and what each
    item it touched was set to."""
    items: dict[tuple, list[str]] = {}
    for delta in change.deltas:
        if delta["item_kind"] == ItemKind.Diagram.value:
            continue
        said = items.setdefault((delta["item_kind"], delta["item_id"]), [])
        after = delta.get("after")
        if delta["field"] is None and after is None:
            said.append("removed")
        elif delta["field"] is None:
            # A thing made or put back is logged whole.
            said.append("put back" if change.turn_id.startswith("undo:") else "added")
            said += [_field(field, value) for field, value in after.items() if field != "id"]
        else:
            said.append(_field(delta["field"], after))
    head = "Unversioned" if change.version is None else f"Version {change.version}"
    return f"{head}, {change.author}: " + "; ".join(
        f"{kind} {item_id} {' '.join(said)}" for (kind, item_id), said in items.items()
    )


def _section(title: str, lines: list[str]) -> str:
    return f"{title}\n" + "\n".join(lines) if lines else ""


def _rows(items: list[dict]) -> list[dict]:
    return [i for i in items if isinstance(i, dict) and i.get("id") is not None]


def render(data: DiagramData | None, speaker: int | None = None) -> str:
    """The whole record, ids first, the person the coach is talking with marked
    (R-0438). Empty when nothing is stored yet."""
    if data is None:
        return ""
    events = sorted(
        _rows(data.events), key=lambda e: (date_text(e.get("dateTime")) or "", e["id"])
    )
    sections = [
        _section(
            "PEOPLE",
            [person_line(p, p["id"] == speaker) for p in _rows(data.people)],
        ),
        _section("PAIR BONDS", [bond_line(b) for b in _rows(data.pair_bonds)]),
        _section("EVENTS (date order)", [event_line(e) for e in events]),
        _section("CLUSTERS", [cluster_line(c) for c in _rows(data.clusters)]),
    ]
    return "\n\n".join(section for section in sections if section)


def _year(event: dict | None) -> str | None:
    date = date_text(event.get("dateTime")) if event else None
    return date[:4] if date else None


def _facts(person: dict, events: list[dict]) -> list[str]:
    facts = [
        f"{word}={year}"
        for word, kind in (("born", EventKind.Birth), ("died", EventKind.Death))
        for year in [_year(_life_event(person["id"], events, kind))]
        if year
    ]
    return facts + [f"events={sum(record.involves(e, person['id']) for e in events)}"]


def _span(cluster: dict, dates: dict) -> str:
    years = sorted(dates[i][:4] for i in cluster.get("eventIds") or [] if dates.get(i))
    span = f" {years[0]}-{years[-1]}" if years else ""
    return f"{_cluster_head(cluster)}{span} events={len(cluster.get('eventIds') or [])}"


def outline(data: DiagramData | None, version: int, speaker: int | None = None) -> str:
    """A map of the record rather than the record (R-0479): who is in it, how
    the events spread over time, and the version it was drawn at. The coach
    reads the rest with its tools. Only the version when nothing is stored yet."""
    if data is None:
        return version_line(version)
    events = _rows(data.events)
    dates = {e["id"]: date_text(e.get("dateTime")) for e in events}
    decades = Counter(f"{d[:3]}0s" if d else "undated" for d in dates.values())
    sections = [
        _section(
            "PEOPLE",
            [
                person_line(p, p["id"] == speaker, _facts(p, events))
                for p in _rows(data.people)
            ],
        ),
        _section("PAIR BONDS", [bond_line(b) for b in _rows(data.pair_bonds)]),
        _section("CLUSTERS", [_span(c, dates) for c in _rows(data.clusters)]),
        _section(
            QUESTIONS,
            [
                question_line(q)
                for q in sorted(filter(on_map, data.questions), key=question_order)
            ],
        ),
        _section(
            "EVENTS PER DECADE",
            [", ".join(f"{d} {n}" for d, n in sorted(decades.items()))] if events else [],
        ),
    ]
    return "\n\n".join(s for s in [*sections, version_line(version)] if s)


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
