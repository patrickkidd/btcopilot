"""Pair bonds on the user's own diagram: the bond between two people, which is
also what a child is born into.

There is one bond ever between any two people, and it carries whether they
married; when it started and when it ended are events about the two of them.
The record refuses a bond with one side, a bond of somebody with themselves, and
a second bond between the same two (R-0326).
"""

import uuid

from flask import abort, jsonify, request

from btcopilot import auth
from btcopilot.personal import record
from btcopilot.personal.models import Author
from btcopilot.personal.routes import asked_diagram, bp, writable_diagram
from btcopilot.schema import ItemKind

WRITABLE = ("person_a", "person_b", "married")


def _payload(bond: dict) -> dict:
    return {field: bond.get(field) for field in ("id", *WRITABLE)}


def _fields(body: dict) -> dict:
    unknown = set(body) - set(WRITABLE)
    if unknown:
        raise ValueError(f"Unknown pair bond field(s): {', '.join(sorted(unknown))}")
    values = {key: body[key] for key in WRITABLE if key in body}
    if "married" in values:
        values["married"] = bool(values["married"])
    return values


def _find(data, bond_id: int) -> dict:
    for bond in data.pair_bonds:
        if bond.get("id") == bond_id:
            return bond
    abort(404, description=f"No pair bond {bond_id} on this diagram")


def _apply(deltas: list[dict]):
    dia = writable_diagram()
    if dia is None:
        abort(404)
    return record.apply(
        dia.id,
        deltas,
        author=Author.User,
        turn_id=uuid.uuid4().hex,
        user_id=auth.current_user().id,
    )


def _delta(bond_id, field, after) -> dict:
    return {
        "item_kind": ItemKind.PairBond.value,
        "item_id": bond_id,
        "field": field,
        "after": after,
    }


@bp.route("/pair_bonds", methods=["POST"])
def create_pair_bond():
    values = _fields(request.get_json())
    if values.get("person_a") is None or values.get("person_b") is None:
        raise ValueError("A pair bond is between two people")
    dia = asked_diagram()
    if dia is None:
        abort(404)
    data = dia.get_diagram_data()
    bond_id = (data.lastItemId or 0) + 1
    deltas = [_delta(bond_id, field, value) for field, value in values.items()]
    deltas.append(
        {
            "item_kind": ItemKind.Diagram.value,
            "item_id": None,
            "field": "lastItemId",
            "after": bond_id,
        }
    )
    _apply(deltas)
    return jsonify(_payload(_find(asked_diagram().get_diagram_data(), bond_id))), 201


@bp.route("/pair_bonds/<int:bond_id>", methods=["PATCH"])
def update_pair_bond(bond_id: int):
    values = _fields(request.get_json())
    _find(asked_diagram().get_diagram_data(), bond_id)
    if not values:
        raise ValueError("Nothing to change on that pair bond")
    _apply([_delta(bond_id, field, value) for field, value in values.items()])
    return jsonify(_payload(_find(asked_diagram().get_diagram_data(), bond_id)))


@bp.route("/pair_bonds/<int:bond_id>", methods=["DELETE"])
def delete_pair_bond(bond_id: int):
    """Removing a bond leaves the children of it without parents, the way the
    app's own scene does."""
    _find(asked_diagram().get_diagram_data(), bond_id)
    _apply([_delta(bond_id, None, None)])
    return "", 204
