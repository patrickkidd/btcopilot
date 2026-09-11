"""The coach's first draft of the coding guidelines, written after a cut is
ratified.

The rules survive only as a first draft people may overwrite (R-0287), and
they come from what the meeting settled, never from the vote. A model that is
not reachable drafts nothing; the ratification still stands.
"""

import logging

import anthropic

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Item, ReviewStatus, Rule, RuleSource

_log = logging.getLogger(__name__)

PROMPT = """You are drafting coding guidelines for a family-systems research
review. Below is what a review meeting settled on, one item per line: what the
coders each wrote down and what the meeting decided.

Write one short guideline per recurring judgement call, each a single sentence
in plain words. Write nothing if the settles show no rule worth stating. One
guideline per line, no numbering, no preamble.

{settles}"""


def settled_items(cut) -> list[Item]:
    return Item.query.filter_by(cut_id=cut.id, status=ReviewStatus.Settled).all()


def draft(items: list[Item], model=None) -> list[str]:
    """Rule texts the coach proposes from what the meeting settled."""
    if not items:
        return []
    lines = [
        f"- {item.item_kind.value}: coders wrote {[t.get('item') for t in item.takes or []]}; "
        f"the meeting kept {item.item_id}"
        for item in items
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
        return []
    return [line.strip("-• ").strip() for line in said.splitlines() if line.strip()]


def draft_for(cut, model=None) -> list[Rule]:
    texts = draft(settled_items(cut), model=model)
    rules = [
        Rule(
            text=text,
            source={"cut_id": cut.id},
            drafted_by=RuleSource.Ai,
            flags=[],
        )
        for text in texts
    ]
    db.session.add_all(rules)
    db.session.flush()
    return rules
