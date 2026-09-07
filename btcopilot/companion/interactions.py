"""Every tap is learning data (R-0077): the looks that send nothing, the chips
that speak, the plays. One row per tap, against the item it touched.

The rows live in memory until the Change/Interaction models land beside
Discussion; this module is the only place that changes when they do."""

import datetime
import enum

from flask import jsonify, request

from btcopilot import auth
from btcopilot.companion.blueprint import bp


class InteractionKind(enum.StrEnum):
    Look = "look"
    Say = "say"
    ChipTap = "chip_tap"
    Play = "play"


class ItemKind(enum.StrEnum):
    Event = "event"
    Events = "events"
    Cluster = "cluster"
    Chapter = "chapter"
    Person = "person"
    Range = "range"


RECORDED: list[dict] = []


def record_interaction(
    user_id: int,
    kind: InteractionKind,
    item_kind: ItemKind | None,
    item_id: str | None,
) -> dict:
    row = {
        "user_id": user_id,
        "kind": kind.value,
        "item_kind": item_kind.value if item_kind else None,
        "item_id": item_id,
        "at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    RECORDED.append(row)
    return row


@bp.route("/interactions", methods=["POST"])
def create_interaction():
    body = request.get_json()
    unknown = set(body) - {"kind", "item_kind", "item_id"}
    if unknown:
        raise ValueError(f"Unknown interaction field(s): {', '.join(sorted(unknown))}")
    item_kind = body.get("item_kind")
    row = record_interaction(
        auth.current_user().id,
        InteractionKind(body["kind"]),
        ItemKind(item_kind) if item_kind else None,
        body.get("item_id"),
    )
    return jsonify(row), 201
