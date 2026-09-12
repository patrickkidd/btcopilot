"""Items: one event, person or pair bond as every coder saw it, and the
settle the meeting makes on it."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Item, ReviewStatus
from btcopilot.schema import ItemKind
from btcopilot.review.routes import (
    admin,
    bp,
    coder,
    cut_or_404,
    human_codings,
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


def read(cut) -> dict:
    """What every take needs beside its own words: the turn the coder wrote it
    from, and the people of the record they wrote it on. Read once per cut, and
    only for the codings people made (R-0254)."""
    people = human_codings(cut)
    found = {}
    for coding in snapshot.done_codings(cut):
        if coding.id not in people:
            continue
        record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
        found[coding.id] = {
            "turns": adapter.coded_in(coding.diagram_id),
            "people": record.get("people") or [],
        }
    return found


def voting_payload(item: Item, records: dict) -> dict:
    """One item as the ballot reads it: the takes without names, each with the
    turn it came from and the name of the person it is about, and how many
    coders left the item out (R-0252, R-0257)."""
    data = payload(item, named=False)
    raws = [one for one in item.takes or [] if one["coding_id"] in records]
    data["takes"] = [
        take
        for raw, take in zip(item.takes or [], data["takes"])
        if raw["coding_id"] in records
    ]
    coders = len(records)
    data["coders"] = coders
    data["not_coded"] = max(coders - len(raws), 0)
    for raw, take in zip(raws, data["takes"]):
        record = records[raw["coding_id"]]
        take["statement_id"] = _turn_of(item, raw, record)
        take["person_name"] = _name_of(raw["item"], record)
    data["people"] = _people_of(item, records)
    data["line"] = _line(data["takes"])
    return data


def _turn_of(item: Item, raw: dict, record: dict) -> int | None:
    """Which turn of the conversation the coder wrote this take from. Only
    events carry that: the record stamps the turn on the event it wrote."""
    if item.item_kind is not ItemKind.Event:
        return None
    try:
        event_id = int(raw["item_id"])
    except (KeyError, TypeError, ValueError):
        return None
    return (record.get("turns") or {}).get(event_id, {}).get("statement_id")


def _name_of(value: dict, record: dict) -> str | None:
    about = value.get("child") if value.get("child") is not None else value.get("person")
    if about is None:
        return None
    for one in record.get("people") or []:
        if str(one.get("id")) == str(about):
            return one.get("name")
    return None


def _people_of(item: Item, records: dict) -> list[dict]:
    """The people of the record the first take was written on, so a take of
    your own can name one of them (R-0257)."""
    takes = [one for one in item.takes or [] if one["coding_id"] in records]
    if not takes:
        return []
    record = records[takes[0]["coding_id"]]
    return [
        {"id": one.get("id"), "name": one.get("name")}
        for one in record.get("people") or []
    ]


def _line(takes: list[dict]) -> dict | None:
    """The transcript line the item came from, which the ballot shows and can
    open, and which is never edited there."""
    ids = [t.get("statement_id") for t in takes if t.get("statement_id")]
    if not ids:
        return None
    said = adapter.statement(ids[0])
    if said is None:
        return None
    speaker = said.speaker
    return {
        "statement_id": said.id,
        "who": (speaker.name if speaker and speaker.name else None) or "Someone",
        "text": said.text or "",
    }


@bp.route("/items")
def item_index():
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not sees_others(cut, user):
        return jsonify([])
    rows = sorted(cut.items, key=lambda i: i.id)
    if cut.ratified_at is not None:
        return jsonify([payload(i, True) for i in rows])
    records = read(cut)
    return jsonify([voting_payload(i, records) for i in rows])


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
