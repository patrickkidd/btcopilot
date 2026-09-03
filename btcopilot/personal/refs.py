"""Coach references ("chips"): the coach may point its reply at something
already in the record. It marks a reference inline as ``[[kind:target|label]]``;
the server parses those out of the reply, hands the client a structured list,
and shows the label alone in the bubble.

A reply that names nothing yields an empty list. Markup whose target will not
parse is dropped (its label survives as plain text) and logged — a reference is
never invented, and never fabricated from prose.

`index` is the other half of the contract: the ids the coach is allowed to
cite, handed to it with the rest of the committed state.
"""

import datetime
import enum
import logging
import re
from dataclasses import dataclass, field

from btcopilot.personal.intake import _enum_val, _parse_iso_date
from btcopilot.schema import DateCertainty, DiagramData, EventKind

_log = logging.getLogger(__name__)


class RefKind(enum.StrEnum):
    Chapter = "chapter"
    Events = "events"
    Person = "person"
    Range = "range"


@dataclass
class Ref:
    kind: RefKind
    label: str
    cluster_id: str | None = None
    event_ids: list[int] = field(default_factory=list)
    person_id: int | None = None
    start: str | None = None
    end: str | None = None


MARKUP = re.compile(
    r"\[\[(" + "|".join(k.value for k in RefKind) + r"):([^|\]]+)\|([^\]]+)\]\]"
)
_LEFTOVER = re.compile(r"\[\[[^\]]*\]\]")


def _chapter(target: str, label: str) -> Ref:
    return Ref(kind=RefKind.Chapter, label=label, cluster_id=target.strip())


def _events(target: str, label: str) -> Ref:
    ids = [int(part) for part in target.split(",") if part.strip()]
    if not ids:
        raise ValueError("no event ids")
    return Ref(kind=RefKind.Events, label=label, event_ids=ids)


def _person(target: str, label: str) -> Ref:
    return Ref(kind=RefKind.Person, label=label, person_id=int(target))


def _range(target: str, label: str) -> Ref:
    start, _, end = target.partition("..")
    a = datetime.date.fromisoformat(start.strip())
    b = datetime.date.fromisoformat(end.strip())
    if b < a:
        raise ValueError(f"range ends before it starts: {target}")
    return Ref(kind=RefKind.Range, label=label, start=a.isoformat(), end=b.isoformat())


BUILDERS = {
    RefKind.Chapter: _chapter,
    RefKind.Events: _events,
    RefKind.Person: _person,
    RefKind.Range: _range,
}


def parse(text: str) -> tuple[str, list[Ref]]:
    """Split a coach reply into the words to show and the references it made."""
    refs = []

    def _sub(match):
        kind, target, label = RefKind(match.group(1)), match.group(2), match.group(3)
        try:
            refs.append(BUILDERS[kind](target, label))
        except ValueError as e:
            _log.warning(f"Unparseable {kind} reference {target!r}: {e}")
        return label

    clean = MARKUP.sub(_sub, text)
    for leftover in _LEFTOVER.findall(clean):
        _log.warning(f"Malformed reference markup left in reply: {leftover}")
    return clean, refs


def resolve(refs: list[Ref], data: DiagramData) -> list[Ref]:
    """Drop references the diagram cannot aim at, so no chip points at nothing."""
    people = {p.get("id") for p in data.people if isinstance(p, dict)}
    events = {e.get("id") for e in data.events if isinstance(e, dict)}
    clusters = {c.get("id") for c in data.clusters if isinstance(c, dict)}

    resolved = []
    for ref in refs:
        if ref.kind is RefKind.Person and ref.person_id not in people:
            _log.warning(f"Reference to unknown person {ref.person_id}")
            continue
        if ref.kind is RefKind.Events:
            ref.event_ids = [i for i in ref.event_ids if i in events]
            if not ref.event_ids:
                _log.warning("Reference to events none of which are in the diagram")
                continue
        if ref.kind is RefKind.Chapter and ref.cluster_id not in clusters:
            _log.warning(f"Reference to unknown chapter {ref.cluster_id}")
            continue
        resolved.append(ref)
    return resolved


# ── The ids the coach may cite ───────────────────────────────────────────────
#
# `resolve` and `companion.timeline.aimable` throw away every reference the
# picture cannot go to. The index is the same rule stated forwards, so the
# coach cites what will survive instead of guessing: a person who appears in a
# dated event, a chapter that starts inside the dated record, a dated event.
# Undated events and events whose date is Unknown are not on the line and are
# therefore not citable.

INDEX_BUDGET_TOKENS = 900
_CHARS_PER_TOKEN = 4
_LABEL_CHARS = 60

_INDEX_HEADER = "Reference index — the only ids you may cite in [[…]] markup."


def _dated(event: dict) -> datetime.date | None:
    if _enum_val(event.get("dateCertainty")) == DateCertainty.Unknown.value:
        return None
    return _parse_iso_date(event.get("dateTime"))


def _event_words(event: dict, people: dict) -> str:
    words = (event.get("description") or "").strip()
    if not words:
        kind = _enum_val(event.get("kind"))
        key = (
            "child"
            if kind in (EventKind.Birth.value, EventKind.Adopted.value)
            and event.get("child")
            else "person"
        )
        name = (people.get(event.get(key)) or {}).get("name") or ""
        words = f"{name} {kind or ''}".strip()
    return words[:_LABEL_CHARS]


def _people_entries(people: dict, dated: list[tuple[dict, datetime.date]]) -> list[str]:
    """Newest first: a person is ranked by the most recent event they touch."""
    seen = {}
    for event, date in dated:
        linked = [event.get(key) for key in ("person", "spouse", "child")]
        linked += event.get("relationshipTargets") or []
        for person_id in linked:
            if person_id in people and person_id not in seen:
                seen[person_id] = date
    ranked = sorted(seen, key=lambda i: (seen[i], i), reverse=True)
    entries = []
    for person_id in ranked:
        name = (people[person_id].get("name") or "").strip()
        if name:
            entries.append(f"{person_id} {name}")
    return entries


def _chapter_entries(
    clusters: list[dict], dated: list[tuple[dict, datetime.date]]
) -> list[str]:
    first, last = dated[-1][1], dated[0][1]
    entries = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        start = _parse_iso_date(cluster.get("startDate"))
        if start is None or not first <= start <= last:
            continue
        end = _parse_iso_date(cluster.get("endDate")) or start
        span = str(start.year) if start.year == end.year else f"{start.year}–{end.year}"
        title = (cluster.get("title") or "").strip()[:_LABEL_CHARS]
        entries.append((start, f"{cluster['id']} {span} {title}".strip()))
    entries.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in entries]


def index(data: DiagramData | None) -> str:
    """The citable ids, newest first, capped at INDEX_BUDGET_TOKENS."""
    if data is None:
        return ""
    people = {
        p["id"]: p
        for p in data.people
        if isinstance(p, dict) and p.get("id") is not None
    }
    dated = sorted(
        (
            (e, _dated(e))
            for e in data.events
            if isinstance(e, dict) and e.get("id") is not None and _dated(e)
        ),
        key=lambda pair: (pair[1], pair[0]["id"]),
        reverse=True,
    )
    if not dated:
        return ""

    sections = [
        ("People", _people_entries(people, dated)),
        ("Chapters", _chapter_entries(data.clusters, dated)),
        (
            "Events (newest first)",
            [
                f"{event['id']} {date.isoformat()} {_event_words(event, people)}".strip()
                for event, date in dated
            ],
        ),
    ]

    # Each section gets an equal share of what is left, and what it does not
    # spend rolls forward. A big cast therefore cannot crowd out the events,
    # which are the ids a reply cites most.
    budget = INDEX_BUDGET_TOKENS * _CHARS_PER_TOKEN - len(_INDEX_HEADER)
    filled = [(title, entries) for title, entries in sections if entries]
    out = [_INDEX_HEADER]
    for position, (title, entries) in enumerate(filled):
        head = f"\n{title}: "
        share = budget // (len(filled) - position)
        kept, used = [], 0
        for entry in entries:
            cost = len(head) if not kept else 2
            if used + cost + len(entry) > share:
                break
            kept.append(entry)
            used += cost + len(entry)
        if kept:
            out.append(head + "; ".join(kept))
        budget -= used
    return "".join(out)
