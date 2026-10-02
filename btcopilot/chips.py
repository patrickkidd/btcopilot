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

import regex

from btcopilot import record
from btcopilot.extensions import db
from btcopilot.models import SpeakerType, Statement
from btcopilot.recordtext import date_text
from btcopilot.schema import DiagramData, enum_val

_log = logging.getLogger(__name__)


class ChipKind(enum.StrEnum):
    Event = "event"
    Cluster = "cluster"
    Person = "person"
    PairBond = "pair_bond"
    Question = "question"
    Impression = "impression"
    # What the coach offers to look at next. It carries the words themselves
    # rather than an id, so there is nothing to resolve and nothing to drop.
    Ask = "ask"
    # The question a coach message closed on, which the reader is answering
    # [Oracle: R-0587].
    Message = "message"
    # Two people who may be one, side by side: the kept person's id, then the
    # dropped one's. Tapped and sent, it is the person's yes.
    Merge = "merge"


TOKEN = re.compile(
    r"\[\[(" + "|".join(k.value for k in ChipKind) + r"):([^|\]]+)(?:\|([^\]]*))?\]\]"
)

# A chip is one size on the page and never truncates, so a label longer than
# this is refused. It is measured in what a reader sees as one character — a
# grapheme cluster — because an accent or a flag is several code points wide
# and none of them takes any more room on the chip.
CHIP_MAX = 28


KIND_WORDS = {
    ChipKind.Event: "this",
    ChipKind.Cluster: "this cluster",
    ChipKind.Person: "them",
    ChipKind.PairBond: "them",
    ChipKind.Question: "this question",
    ChipKind.Impression: "this impression",
    ChipKind.Ask: "this",
    ChipKind.Message: "this question",
    ChipKind.Merge: "same person",
}


def token(kind: ChipKind, target, label: str | None = None) -> str:
    return f"[[{kind.value}:{target}|{label}]]" if label else f"[[{kind.value}:{target}]]"


def _ids(data: DiagramData, kind: ChipKind) -> set[str]:
    collection = {
        ChipKind.Event: data.events,
        ChipKind.Cluster: data.clusters,
        ChipKind.Person: data.people,
        ChipKind.PairBond: data.pair_bonds,
        ChipKind.Question: [q for q in data.questions if record.note(q) is record.QUESTION],
        ChipKind.Impression: [q for q in data.questions if record.note(q) is record.IMPRESSION],
    }[kind]
    return {
        str(item["id"])
        for item in collection
        if isinstance(item, dict) and item.get("id") is not None
    }


# The question that closes a reply is its last sentence, when that sentence is
# a question; the page sets it apart the same way.
_CLOSING = re.compile(r"[^.?!]*\?\s*$")


def plain(text: str) -> str:
    """The words as a reader sees them, each chip as its label."""
    return TOKEN.sub(lambda m: m.group(3) or "", text)


def asked(statement: Statement) -> str | None:
    """The question a coach message ends on: a play's own, or the reply's last
    sentence when it is a question."""
    if statement.told_case:
        return statement.told_case["question"]
    closing = _CLOSING.search(plain(statement.text or ""))
    return closing.group(0).strip() if closing else None


def _message(target: str, diagram_id: int | None) -> Statement | None:
    """A coach message in this family's sessions that asked a question."""
    statement = db.session.get(Statement, int(target)) if target.isdigit() else None
    if (
        statement is None
        or statement.discussion.diagram_id != diagram_id
        or statement.speaker.type != SpeakerType.Expert
        or asked(statement) is None
    ):
        return None
    return statement


def _pair(target: str) -> list[str]:
    return [part.strip() for part in str(target).split(",")]


def resolves(kind: ChipKind, target: str, data: DiagramData, diagram_id: int | None) -> bool:
    if kind is ChipKind.Merge:
        ids = _pair(target)
        return len(set(ids)) == 2 and set(ids) <= _ids(data, ChipKind.Person)
    if kind is ChipKind.Ask:
        return bool(str(target).strip())
    if kind is ChipKind.Message:
        return _message(str(target).strip(), diagram_id) is not None
    return str(target).strip() in _ids(data, kind)


def parse(text: str, data: DiagramData, diagram_id: int | None) -> list[tuple[ChipKind, str, str]]:
    """Every chip in `text` that the record resolves, as (kind, id, label)."""
    found = []
    for match in TOKEN.finditer(text):
        kind, target = ChipKind(match.group(1)), match.group(2).strip()
        if resolves(kind, target, data, diagram_id):
            found.append((kind, target, (match.group(3) or "").strip()))
    return found


def length(words: str) -> int:
    """How wide a label reads, in grapheme clusters."""
    return len(regex.findall(r"\X", words))


# The coach speaks; a comma list of chips is not speech. Three chips with only
# punctuation and a joining word between them is a list, however it is dressed.
BARE_RUN = 3
_JOIN = re.compile(
    r"^[\s,;:—–-]*(?:and|then|and then|next|after that)?[\s,;:—–-]*$", re.I
)


def bare_list(text: str) -> bool:
    """Whether `text` puts three or more record chips in a row with nothing but
    separators between them. Offers are excluded: they are written as a run at
    the end by design."""
    run = 0
    end = None
    for match in TOKEN.finditer(text):
        if match.group(1) == ChipKind.Ask.value:
            run, end = 0, None
            continue
        run = (
            run + 1 if end is not None and _JOIN.match(text[end : match.start()]) else 1
        )
        if run >= BARE_RUN:
            return True
        end = match.end()
    return False


def validate(text: str, data: DiagramData, diagram_id: int | None) -> str:
    """The words to persist: a chip the record cannot resolve becomes its own
    label, so the user never reads a reference that points at nothing."""

    def _keep(match):
        kind, target = ChipKind(match.group(1)), match.group(2).strip()
        # Offered answers are dropped (Patrick, 2026-09-21): people type their
        # own words. The token is still parsed so an old transcript renders.
        if kind is ChipKind.Ask:
            return ""
        if resolves(kind, target, data, diagram_id):
            return match.group(0)
        label = (match.group(3) or "").strip() or KIND_WORDS[kind]
        _log.warning(f"Chip to unknown {kind.value} {target!r} replaced with {label!r}")
        return label

    return TOKEN.sub(_keep, text).rstrip()


def _describe(kind: ChipKind, target: str, data: DiagramData, diagram_id: int | None) -> str:
    if kind is ChipKind.Ask:
        return f"the offer to talk about {target}"
    if kind is ChipKind.Message:
        question = asked(_message(target, diagram_id))
        return f'the question you asked in message {target}: "{question}"'
    if kind is ChipKind.Person:
        person = next(p for p in data.people if str(p.get("id")) == target)
        return f"person {target}: {person.get('name') or 'unnamed'}"
    if kind is ChipKind.Merge:
        keep, drop = _pair(target)
        return (
            f"the card asking whether persons {keep} and {drop} are one person. "
            "Sent, it is their yes: join them with "
            f"merge_people(keep={keep}, drop={drop}), with what their own words "
            "say of which name or fact is right"
        )
    if kind is ChipKind.Event:
        event = next(e for e in data.events if str(e.get("id")) == target)
        words = event.get("description") or enum_val(event.get("kind")) or ""
        when = date_text(event.get("dateTime")) or "undated"
        return f"event {target}: {when} {words}".strip()
    if kind in (ChipKind.Question, ChipKind.Impression):
        question = next(q for q in data.questions if q["id"] == target)
        return f'{kind.value} {target}: "{question["text"]}"'
    if kind is ChipKind.PairBond:
        bond = next(b for b in data.pair_bonds if str(b.get("id")) == target)
        names = {str(p.get("id")): p.get("name") or "unnamed" for p in data.people}
        return (
            f"pair bond {target}: {names[str(bond['person_a'])]} & "
            f"{names[str(bond['person_b'])]}"
        )
    cluster = next(c for c in data.clusters if str(c.get("id")) == target)
    return f"cluster {target}: {cluster.get('name') or cluster.get('title') or ''}".strip()


def context(text: str, data: DiagramData, diagram_id: int | None) -> str:
    """What the chips in a user's message point at, spelled out for the model.

    A message that is nothing but chips is the user asking about them.
    """
    found = parse(text, data, diagram_id)
    if not found:
        return ""
    lines = [_describe(kind, target, data, diagram_id) for kind, target, _ in found]
    bare = not TOKEN.sub("", text).strip()
    head = (
        "The user sent these references on their own, which means: tell me about this."
        if bare
        else "The user's message refers to:"
    )
    return head + "\n" + "\n".join(lines)


def people(text: str, data: DiagramData, diagram_id: int | None) -> set[str]:
    """The people a message's chips name, the people of the events it names
    included."""
    named = set()
    for kind, target, _ in parse(text, data, diagram_id):
        if kind is ChipKind.Person:
            named.add(target)
        elif kind is ChipKind.Event:
            event = next(e for e in data.events if str(e.get("id")) == target)
            named |= {
                str(p.get("id")) for p in data.people if record.involves(event, p.get("id"))
            }
    return named
