"""Items: one event, person or pair bond as every coder saw it, and the
settle the meeting makes on it."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Item, ReviewStatus
from btcopilot.review.routes import (
    admin,
    bp,
    coder,
    cut_or_404,
    item_or_404,
    sees_others,
)

SETTLE_STATUS = {
    "keep": ReviewStatus.Settled,
    "change": ReviewStatus.Settled,
    "unresolved": ReviewStatus.Unresolved,
}


def payload(item: Item, named: bool) -> dict:
    data = item.as_dict()
    if not named:
        data["takes"] = [
            {k: v for k, v in take.items() if k != "user_id"}
            for take in (item.takes or [])
        ]
        data.pop("user_id", None)
    return data


@bp.route("/items")
def item_index():
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not sees_others(cut, user):
        return jsonify([])
    named = cut.ratified_at is not None
    rows = sorted(cut.items, key=lambda i: i.id)
    return jsonify([payload(i, named) for i in rows])


@bp.route("/items/<int:item_id>", methods=["PATCH"])
def item_patch(item_id: int):
    """The meeting's settle: keep what a coder had, change it, or leave it
    unresolved. Every item must carry one before a cut is ratified (R-0257)."""
    user = admin()
    item = item_or_404(item_id)
    body = request.get_json() or {}
    choice = body.get("choice")
    if choice not in SETTLE_STATUS:
        raise ValueError("a settle is keep, change or unresolved")

    item.status = SETTLE_STATUS[choice]
    item.user_id = user.id

    if choice != "unresolved":
        value = _value(item, body.get("value"))
        change = _write(item, value, user)
        item.settle_change_id = change.id

    db.session.commit()
    return jsonify(payload(item, True))


def _value(item: Item, given) -> dict:
    """What the meeting settled on: a coder's take picked by its coding, or a
    written-out item of its own."""
    if isinstance(given, dict) and "coding_id" in given and "item" not in given:
        for take in item.takes or []:
            if take.get("coding_id") == given["coding_id"]:
                return take["item"]
        raise ValueError("no take on this item from that coding")
    if isinstance(given, dict) and given:
        return given.get("item", given)
    takes = item.takes or []
    if len(takes) != 1:
        raise ValueError("say which take or what to write")
    return takes[0]["item"]


def _write(item: Item, value: dict, user):
    case = adapter.case_diagram(
        db.session.get(adapter.Discussion, item.cut.discussion_id)
    )
    data = adapter.record_of(case)
    target = str(item.item_id or value.get("id") or _next_id(data))
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
    change = adapter.commit(case.id, deltas, user.id, f"review-settle-{item.id}")
    item.item_id = target
    return change


def _next_id(data: dict) -> int:
    ids = [
        int(entry.get("id"))
        for collection in ("people", "events", "pair_bonds")
        for entry in data.get(collection) or []
        if str(entry.get("id")).lstrip("-").isdigit()
    ]
    return max(ids, default=0) + 1
