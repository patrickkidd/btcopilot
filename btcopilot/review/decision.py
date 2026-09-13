"""Writing what the room agreed onto the case's own record.

One item of the review's snapshot becomes one item of the case, whether the
room chose between the opinions or every coder had already read it the same way.
Ratifying confirms the agreed ones, which is why they are collapsed on the
meeting screen rather than argued over (R-0257, R-0274).
"""

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Item, ReviewStatus


def value_of(item: Item, given) -> dict:
    """What the meeting decided on: a coder's opinion picked by its coding, or a
    written-out item of its own."""
    if isinstance(given, dict) and "coding_id" in given and "item" not in given:
        for opinion in item.opinions or []:
            if opinion.get("coding_id") == given["coding_id"]:
                return opinion["item"]
        raise ValueError("no opinion on this item from that coding")
    if isinstance(given, dict) and given:
        return given.get("item", given)
    opinions = item.opinions or []
    if len(opinions) != 1:
        raise ValueError("say which opinion or what to write")
    return opinions[0]["item"]


def write(item: Item, value: dict, user):
    case = adapter.case_diagram(
        db.session.get(adapter.Discussion, item.cut.discussion_id)
    )
    data = adapter.record_of(case)
    # A change is a rewording of the same moment, so it lands on the item the
    # opinions already name rather than adding a second one beside it.
    target = str(item.item_id or value.get("id") or _take_id(item) or _next_id(data))
    deltas = [
        {
            "item_kind": item.item_kind.value,
            "item_id": target,
            "field": field,
            "after": adapter.to_json(field_value),
        }
        for field, field_value in value.items()
        if field != "id"
    ]
    change = adapter.commit(case.id, deltas, user.id, f"review-decision-{item.id}")
    item.item_id = target
    return change


def confirm_agreed(cut, user) -> list[Item]:
    """Every item the coders already read the same way, written onto the case
    as it stands. The room chooses nothing here: ratifying is the confirming."""
    found = [
        item
        for item in cut.items
        if item.status is ReviewStatus.Agreed and item.item_id is None
    ]
    for item in found:
        # Agreed means every coder wrote it the same way, so any opinion is it.
        change = write(item, item.opinions[0]["item"], user)
        item.decision_change_id = change.id
    db.session.flush()
    return found


def _take_id(item: Item) -> str | None:
    """The id the coders' own records gave this moment, which the case record
    shares because every coding of a cut is written onto the same case."""
    for opinion in item.opinions or []:
        if opinion.get("item_id") is not None:
            return str(opinion["item_id"])
    return None


def _next_id(data: dict) -> int:
    ids = [
        int(entry.get("id"))
        for collection in ("people", "events", "pair_bonds")
        for entry in data.get(collection) or []
        if str(entry.get("id")).lstrip("-").isdigit()
    ]
    return max(ids, default=0) + 1
