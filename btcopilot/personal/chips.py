"""Chips: the one primitive both sides of the chat share [Oracle: R-0072].

A chip is a reference into the record, written inline as ``[[kind:id]]`` or
``[[kind:id|words to show]]``. The coach writes them into its reply; the user's
message carries them when they tap one. Every token is checked against the
record: the coach may only point at what is stored, and a token the record
cannot resolve never reaches the transcript.
"""

import enum
import logging
import re

from btcopilot.personal.intake import _enum_val
from btcopilot.personal.recordtext import date_text
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)


class ChipKind(enum.StrEnum):
    Event = "event"
    Cluster = "cluster"
    Person = "person"
    # What the coach offers to look at next. It carries the words themselves
    # rather than an id, so there is nothing to resolve and nothing to drop.
    Ask = "ask"


TOKEN = re.compile(
    r"\[\[(" + "|".join(k.value for k in ChipKind) + r"):([^|\]]+)(?:\|([^\]]*))?\]\]"
)

# A chip is one size on the page and never truncates, so a label longer than
# this is not shortened for display — it is refused here and replaced.
CHIP_MAX = 28


KIND_WORDS = {
    ChipKind.Event: "this",
    ChipKind.Cluster: "this stretch",
    ChipKind.Person: "them",
    ChipKind.Ask: "this",
}


def token(kind: ChipKind, target, label: str | None = None) -> str:
    return f"[[{kind.value}:{target}|{label}]]" if label else f"[[{kind.value}:{target}]]"


def _ids(data: DiagramData, kind: ChipKind) -> set[str]:
    collection = {
        ChipKind.Event: data.events,
        ChipKind.Cluster: data.clusters,
        ChipKind.Person: data.people,
    }[kind]
    return {
        str(item["id"])
        for item in collection
        if isinstance(item, dict) and item.get("id") is not None
    }


def resolves(kind: ChipKind, target: str, data: DiagramData) -> bool:
    if kind is ChipKind.Ask:
        return bool(str(target).strip())
    return str(target).strip() in _ids(data, kind)


def parse(text: str, data: DiagramData) -> list[tuple[ChipKind, str, str]]:
    """Every chip in `text` that the record resolves, as (kind, id, label)."""
    found = []
    for match in TOKEN.finditer(text):
        kind, target = ChipKind(match.group(1)), match.group(2).strip()
        if resolves(kind, target, data):
            found.append((kind, target, (match.group(3) or "").strip()))
    return found


def clip(words: str, limit: int = CHIP_MAX) -> str:
    """Cut at the last space inside the limit, so a chip never breaks a word."""
    words = " ".join(words.split())
    if len(words) <= limit:
        return words
    cut = words[:limit].rstrip()
    space = cut.rfind(" ")
    return cut[:space] if space > limit // 2 else cut


def label_of(kind: ChipKind, target: str, data: DiagramData) -> str:
    """What the record itself calls this thing — the label a chip falls back to."""
    if kind is ChipKind.Person:
        person = next(p for p in data.people if str(p.get("id")) == target)
        return person.get("name") or KIND_WORDS[kind]
    if kind is ChipKind.Event:
        event = next(e for e in data.events if str(e.get("id")) == target)
        return (
            event.get("description") or _enum_val(event.get("kind")) or KIND_WORDS[kind]
        )
    if kind is ChipKind.Cluster:
        cluster = next(c for c in data.clusters if str(c.get("id")) == target)
        return cluster.get("name") or cluster.get("title") or KIND_WORDS[kind]
    return target


def validate(text: str, data: DiagramData) -> str:
    """The words to persist.

    A chip the record cannot resolve becomes its own label, so the user never
    reads a reference that points at nothing. A label too long for one chip is
    replaced rather than shortened for display: a reference falls back to what
    the record calls the thing, an offer to its own first words.
    """

    def _keep(match):
        kind, target = ChipKind(match.group(1)), match.group(2).strip()
        label = (match.group(3) or "").strip()
        if not resolves(kind, target, data):
            words = label or KIND_WORDS[kind]
            _log.warning(
                f"Chip to unknown {kind.value} {target!r} replaced with {words!r}"
            )
            return words

        if kind is ChipKind.Ask:
            if len(target) <= CHIP_MAX:
                return match.group(0)
            short = clip(target)
            _log.warning(f"Offer chip {target!r} is too long; cut to {short!r}")
            return token(kind, short, label or None)

        if len(label) <= CHIP_MAX:
            return match.group(0)
        short = clip(label_of(kind, target, data))
        _log.warning(
            f"Chip label {label!r} on {kind.value} {target} is too long; "
            f"the record calls it {short!r}"
        )
        return token(kind, target, short)

    return TOKEN.sub(_keep, text)


def _describe(kind: ChipKind, target: str, data: DiagramData) -> str:
    if kind is ChipKind.Ask:
        return f"the offer to talk about {target}"
    if kind is ChipKind.Person:
        person = next(p for p in data.people if str(p.get("id")) == target)
        return f"person {target}: {person.get('name') or 'unnamed'}"
    if kind is ChipKind.Event:
        event = next(e for e in data.events if str(e.get("id")) == target)
        words = event.get("description") or _enum_val(event.get("kind")) or ""
        when = date_text(event.get("dateTime")) or "undated"
        return f"event {target}: {when} {words}".strip()
    cluster = next(c for c in data.clusters if str(c.get("id")) == target)
    return f"cluster {target}: {cluster.get('name') or cluster.get('title') or ''}".strip()


def context(text: str, data: DiagramData) -> str:
    """What the chips in a user's message point at, spelled out for the model.

    A message that is nothing but chips is the user asking about them.
    """
    found = parse(text, data)
    if not found:
        return ""
    lines = [_describe(kind, target, data) for kind, target, _ in found]
    bare = not TOKEN.sub("", text).strip()
    head = (
        "The user sent these references on their own, which means: tell me about this."
        if bare
        else "The user's message refers to:"
    )
    return head + "\n" + "\n".join(lines)
