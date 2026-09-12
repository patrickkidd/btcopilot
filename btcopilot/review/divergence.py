"""Where the coach's reading differed from the room, read after ratification.

This is an audit and never a vote: nothing here changes the agreed record
(R-0254). The rows are worked out from the snapshot; the reason beside each is
the coach's own, asked for once. A model that is not reachable leaves the
reasons empty and the rows still stand.
"""

import logging
import re

import anthropic

from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Item, ReviewStatus

_log = logging.getLogger(__name__)

PROMPT = """You are auditing your own earlier reading of a family-systems
transcript against what a review meeting agreed. Below is one line per place
you read it differently.

For each, say in one plain sentence why you read it as you did. Begin every
line with its number in square brackets and write nothing else.

{rows}"""

#: What two readings of the same moment can differ by, in the order they read.
TELLING = ("dateTime", "kind", "description", "symptom", "anxiety", "functioning",
           "relationship")


def rows(cut) -> list[dict]:
    """One row per item the coach read differently from the room."""
    coding = snapshot.coach_coding(cut)
    if coding is None:
        return []
    people = {c.id for c in snapshot.voters(cut)}
    found = []
    for item in sorted(cut.items, key=lambda i: i.id):
        mine = next(
            (t for t in item.takes or [] if t["coding_id"] == coding.id), None
        )
        if mine is None:
            continue
        theirs = [t for t in item.takes or [] if t["coding_id"] in people]
        room = _room(item, theirs)
        apart = differs(mine["item"], room)
        if not apart:
            continue
        found.append(
            {
                "review_item_id": item.id,
                "item_kind": item.item_kind.value,
                "label": _label(mine["item"], room),
                "room": _words(room, apart) if room else "not an item at all",
                "coach": _words(mine["item"], apart),
                "reason": None,
            }
        )
    return found


def _room(item: Item, theirs: list[dict]) -> dict | None:
    """What the room ended with: nothing when it settled the item away or
    nobody but the coach wrote it down."""
    if item.status is ReviewStatus.Unresolved or not theirs:
        return None
    return theirs[0]["item"]


def differs(mine: dict, room: dict | None) -> list[str]:
    if room is None:
        return list(TELLING)
    return [
        field
        for field in TELLING
        if str(mine.get(field) or "") != str(room.get(field) or "")
    ]


def _words(value: dict, fields: list[str]) -> str:
    said = [str(value.get(field)) for field in fields if value.get(field)]
    return " · ".join(said) or "as written"


def _label(mine: dict, room: dict | None) -> str:
    source = room or mine
    return str(source.get("description") or source.get("kind") or "an item")


def reasons(found: list[dict], model=None) -> list[dict]:
    """The coach's own reason beside each row, asked for in one go."""
    if not found:
        return found
    lines = [
        f"[{index + 1}] {row['label']} — the room: {row['room']}; you: {row['coach']}"
        for index, row in enumerate(found)
    ]
    try:
        said = "".join(
            adapter.coach_model(model).turn(
                "",
                [{"role": "user", "content": PROMPT.format(rows="\n".join(lines))}],
                [],
            )
        )
    except (KeyError, anthropic.AnthropicError) as e:
        _log.warning(f"No reasons for the coach's divergences: {e}")
        return found
    for index, text in numbered(said).items():
        if 1 <= index <= len(found):
            found[index - 1]["reason"] = text
    return found


def numbered(said: str) -> dict[int, str]:
    """Lines the model wrote as "[n] words", which is how it is asked to
    attribute one answer to one row."""
    found = {}
    for line in said.splitlines():
        match = re.match(r"\s*\[(\d+)\]\s*(.+)", line)
        if match:
            found[int(match.group(1))] = match.group(2).strip()
    return found
