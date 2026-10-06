"""The record as the coach reads it.

One compact rendering of the whole family record, ids first, so every chip and
every tool argument the coach writes can only be an id it was shown. What the
picture draws lives in the record; who did what when lives beside it, which is
why the interactions render separately.
"""

import datetime
import json

from btcopilot import diagramjson, matching, record
from btcopilot.models import Change, Interaction
from btcopilot.schema import (
    DECLINED,
    DiagramData,
    EventKind,
    ItemKind,
    PairBond,
    Person,
    from_dict,
    QuestionOutcome,
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


def _event_head(event: dict) -> list[str]:
    """When an event was, what kind it is and who it is about: enough to tell
    it from another without saying what happened."""
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
    return parts


def event_line(event: dict) -> str:
    parts = _event_head(event)
    if event.get("title"):
        parts.append(f'title="{event["title"]}"')
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


def _refused(question: dict) -> bool:
    """Turned down by the user, or declined in chat: kept in view so it is
    never said again in those words."""
    return question.get("outcome") in (*DECLINED, QuestionOutcome.DoesntFit)


def on_map(question: dict) -> bool:
    """Open, or turned down: the ones the coach keeps in view."""
    return question["state"] != QuestionState.Resolved or _refused(question)


def question_order(question: dict) -> tuple:
    return _refused(question), int(question["id"][1:])


def _status(question: dict) -> str:
    if question.get("outcome") == QuestionOutcome.DoesntFit:
        return "doesn't fit"
    if _refused(question):
        return "declined"
    return " ".join(part for part in (question["state"], question.get("pushback")) if part)


def note_line(question: dict) -> str:
    """One question or impression as the map and the reads give it."""
    status = _status(question)
    if record.note(question) is record.TODO:
        line = f'{question["id"]} {status} todo "{question["text"]}"'
    elif record.note(question) is record.IMPRESSION:
        line = f'{question["id"]} {status} "{question["text"]}" on '
        line += ", ".join(f"{one['kind']} {one['id']}" for one in question["evidence"]) or "nothing"
    else:
        if question["state"] == QuestionState.Asked and question.get("asked_at"):
            status += f" {question['asked_at']}"
            again = question.get(record.ASKED_AGAIN) or []
            if again:
                status += f", again {', '.join(again)}"
            if len(again) >= record.PASSES:
                status += ", passed over: not waiting, asked only if the person brings it up"
        line = f'{question["id"]} {status} {question["kind"]} "{question["text"]}"'
        if question.get("item_kind"):
            line += f" about {question['item_kind']} {question['item_id']}"
    if status == QuestionState.Resolved:
        line += f" outcome={question['outcome']}"
    if question.get("answer"):
        line += f" answer=message {question['answer']['id']}"
    if question.get(record.CARD):
        line += f" card={question[record.CARD]}"
    return line


QUESTIONS = "QUESTIONS (open, then declined: never ask a declined one again)"
EVENTS = "EVENTS (date order)"
IMPRESSIONS = (
    "IMPRESSIONS (raised and held; one the user said doesn't fit is never raised "
    "again in those words)"
)


def _notes(data: DiagramData, rules) -> list[str]:
    return [
        note_line(q)
        for q in sorted(data.questions, key=question_order)
        if record.note(q) in rules and on_map(q)
    ]


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
        _section(EVENTS, [event_line(e) for e in events]),
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
    """A map of the record rather than the record (R-0479): who is in it, each
    event's date, kind and people, and the version it was drawn at. The chat
    before the latest words is not given back, so the map is how the coach
    knows an event is already down (R-0481). What happened is read with the
    tools. Only the version when nothing is stored yet."""
    if data is None:
        return version_line(version)
    events = sorted(
        _rows(data.events), key=lambda e: (date_text(e.get("dateTime")) or "", e["id"])
    )
    dates = {e["id"]: date_text(e.get("dateTime")) for e in events}
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
            _notes(data, (record.QUESTION, record.TODO)),
        ),
        _section(IMPRESSIONS, _notes(data, (record.IMPRESSION,))),
        _section(EVENTS, [" ".join(_event_head(e)) for e in events]),
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


NOTES = "YOUR NOTES FROM YOUR LAST TURN, written {day}"


def notes(args: dict, written: datetime.datetime) -> str:
    """The coach's last notes, one labelled line per field, as it wrote them."""
    lines = [
        f"{field}: "
        + (
            ", ".join(f"{key}={value}" for key, value in said.items())
            if isinstance(said, dict)
            else str(said)
        )
        for field, said in args.items()
    ]
    return _section(NOTES.format(day=written.date().isoformat()), lines)


def _fuller(person: dict, events: list[dict]) -> tuple:
    """Which of two records of one person is fuller: named, dated, then busier."""
    return (
        bool(person.get("last_name")),
        _year(_life_event(person["id"], events, EventKind.Birth)) is not None,
        sum(record.involves(e, person["id"]) for e in events),
    )


def pairs(data: DiagramData, words: str, named: set[str]) -> str:
    """The pairs of people who may be one person written twice, when this
    turn's words touch one of them: by a chip naming them or an event of
    theirs, or by a word of their name. One line each, the fuller record first,
    with the facts the two disagree on and the card that asks."""
    people = _rows(data.people)
    events = _rows(data.events)
    said = set(matching.normalize_name_for_matching(words).split())
    data_dict = record.collections(data)
    lines = []
    for a, b in matching.likely_same(
        [from_dict(Person, p) for p in people], [from_dict(PairBond, x) for x in _rows(data.pair_bonds)]
    ):
        one, two = (next(p for p in people if p["id"] == x.id) for x in (a, b))
        if any(record.generic_key(p) for p in (one, two)) or record.kin(data_dict, a.id, b.id):
            continue
        if not any(
            str(p["id"]) in named or said & set(matching.full_name(x).split())
            for p, x in ((one, a), (two, b))
        ):
            continue
        keep, drop = sorted((one, two), key=lambda p: _fuller(p, events), reverse=True)
        differ = record.differing(data_dict, keep["id"], drop["id"])
        apart = "; ".join(f"{fact.value} {ours} and {theirs}" for fact, (ours, theirs) in differ.items())
        lines.append(
            f"Persons {person_line(keep, facts=_facts(keep, events))} and "
            f"{person_line(drop, facts=_facts(drop, events))} may be one person"
            + (f"; they differ on {apart}" if apart else "")
            + f". Their card: [[merge:{keep['id']},{drop['id']}]]"
        )
    return "\n".join(lines)
