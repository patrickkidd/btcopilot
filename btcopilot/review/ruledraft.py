"""The coach's first draft of the coding guidelines, written after a cut is
ratified.

The rules survive only as a first draft people may overwrite (R-0287), and
they come from what the meeting settled, never from the vote. A model that is
not reachable drafts nothing; the ratification still stands.
"""

import logging

import anthropic

from btcopilot.extensions import db
from btcopilot.review import adapter, divergence
from btcopilot.review.models import Item, ReviewStatus, Rule, RuleSource

_log = logging.getLogger(__name__)

PROMPT = """You are drafting coding guidelines for a family-systems research
review. Below is what a review meeting settled on, one numbered item per line:
what the coders each wrote down and what the meeting decided.

Write one short guideline per recurring judgement call, each a single sentence
in plain words. Write nothing if the settles show no rule worth stating. One
guideline per line, no preamble. Begin every line with the number of the settle
it came from in square brackets.

{settles}"""


def settled_items(cut) -> list[Item]:
    return Item.query.filter_by(cut_id=cut.id, status=ReviewStatus.Settled).all()


def draft(items: list[Item], model=None) -> dict[int, str]:
    """Rule texts the coach proposes, each against the settle it came from."""
    if not items:
        return {}
    lines = [
        f"[{index + 1}] {item.item_kind.value}: coders wrote "
        f"{[t.get('item') for t in item.takes or []]}; "
        f"the meeting kept {item.item_id}"
        for index, item in enumerate(items)
    ]
    try:
        said = "".join(
            adapter.coach_model(model).turn(
                "",
                [
                    {
                        "role": "user",
                        "content": PROMPT.format(settles="\n".join(lines)),
                    }
                ],
                [],
            )
        )
    except (KeyError, anthropic.AnthropicError) as e:
        _log.warning(f"No rule draft for cut: {e}")
        return {}
    return {
        index: text.strip("-• ").strip()
        for index, text in divergence.numbered(said).items()
        if 1 <= index <= len(items) and text.strip("-• ").strip()
    }


def source_of(cut, item: Item) -> dict:
    """Where a rule came from: the settled item, what it says and the margin
    the room settled it by, so a reader can go back to the argument
    (R-0259)."""
    counts: dict[str, int] = {}
    for vote in item.votes:
        counts[vote.choice.value] = counts.get(vote.choice.value, 0) + 1
    margin = sorted(counts.values(), reverse=True)
    return {
        "cut_id": cut.id,
        "meeting_date": cut.meeting_date.isoformat() if cut.meeting_date else None,
        "review_item_id": item.id,
        "item_id": item.item_id,
        "label": _label(item),
        "margin": " to ".join(str(n) for n in margin) if margin else None,
    }


def _label(item: Item) -> str:
    first = (item.takes or [{}])[0].get("item") or {}
    return str(first.get("description") or first.get("name") or item.item_kind.value)


def draft_for(cut, model=None) -> list[Rule]:
    items = settled_items(cut)
    rules = [
        Rule(
            text=text,
            source=source_of(cut, items[index - 1]),
            drafted_by=RuleSource.Ai,
            flags=[],
            # Live the moment the cut is ratified: there is nothing to choose
            # on the result screen (R-0259).
            ratified_at=adapter.utcnow(),
        )
        for index, text in sorted(draft(items, model=model).items())
    ]
    db.session.add_all(rules)
    db.session.flush()
    return rules
