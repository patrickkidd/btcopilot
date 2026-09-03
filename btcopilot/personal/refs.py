"""Coach references ("chips"): the coach may point its reply at something
already in the record. It marks a reference inline as ``[[kind:target|label]]``;
the server parses those out of the reply, hands the client a structured list,
and shows the label alone in the bubble.

A reply that names nothing yields an empty list. Markup whose target will not
parse is dropped (its label survives as plain text) and logged — a reference is
never invented, and never fabricated from prose.
"""

import datetime
import enum
import logging
import re
from dataclasses import dataclass, field

from btcopilot.schema import DiagramData

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
