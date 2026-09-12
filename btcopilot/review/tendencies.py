"""What each coder tends to do differently from the others.

Worked out from the snapshot rows and nothing else, so every line is a count
somebody can go back and check (R-0262).
"""

from btcopilot.extensions import db
from btcopilot.review import adapter, divergence, snapshot
from btcopilot.review.models import Item, ReviewStatus

#: A coder is only said to lean a way when they did it more than once.
LEAST = 2


def rows(cut) -> list[dict]:
    people = snapshot.voters(cut)
    ids = {c.id for c in people}
    items = [
        item
        for item in sorted(cut.items, key=lambda i: i.id)
        if any(t["coding_id"] in ids for t in item.takes or [])
    ]
    agreed = _agreed(cut)
    return [_coder(coding, items, agreed) for coding in people]


def _agreed(cut) -> dict[str, dict]:
    """The case as it stands, by item id, read once for the whole cut."""
    record = adapter.record_of(
        adapter.case_diagram(db.session.get(adapter.Discussion, cut.discussion_id))
    )
    return {
        str(entry.get("id")): entry
        for collection in ("people", "events", "pair_bonds")
        for entry in record.get(collection) or []
    }


def _coder(coding, items: list[Item], agreed: dict[str, dict]) -> dict:
    mine = {
        item.id: next(
            (t["item"] for t in item.takes or [] if t["coding_id"] == coding.id), None
        )
        for item in items
    }
    fields: dict[str, int] = {}
    apart = 0
    for item in items:
        theirs = mine[item.id]
        room = (
            agreed.get(str(item.item_id))
            if item.status is ReviewStatus.Settled
            else None
        )
        if theirs is None or room is None:
            continue
        differs = divergence.differs(theirs, room)
        if differs:
            apart += 1
            fields[differs[0]] = fields.get(differs[0], 0) + 1
    leans = max(fields.items(), key=lambda pair: pair[1], default=None)
    enough = leans is not None and leans[1] >= LEAST
    return {
        "user_id": coding.user_id,
        "name": adapter.initials(db.session.get(adapter.User, coding.user_id)),
        "items": len(items),
        "left_out": sum(1 for value in mine.values() if value is None),
        "apart": apart,
        "leans": leans[0] if enough else None,
        "leans_count": leans[1] if enough else 0,
    }
