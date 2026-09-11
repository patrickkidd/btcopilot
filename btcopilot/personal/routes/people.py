"""People on the user's own diagram, written the way the coach writes them:
through the record's command log, authored by the user.

The record's Person carries a name, a last name, a gender and the bond it was
born into. When someone was born, and whether they have died, are events about
them rather than fields on them, so they are edited on the timeline.
"""

import uuid

from flask import abort, jsonify, request

from btcopilot import auth
from btcopilot.personal import record
from btcopilot.personal.models import Author
from btcopilot.personal.routes import bp, diagram, writable_diagram
from btcopilot.schema import ItemKind, PersonKind

WRITABLE = ("name", "last_name", "gender")


def _payload(person: dict) -> dict:
    return {field: person.get(field) for field in ("id", *WRITABLE)}


def _fields(body: dict) -> dict:
    unknown = set(body) - set(WRITABLE)
    if unknown:
        raise ValueError(f"Unknown person field(s): {', '.join(sorted(unknown))}")
    values = {key: body[key] for key in WRITABLE if key in body}
    if values.get("gender") is not None:
        values["gender"] = PersonKind(values["gender"]).value
    for key in ("name", "last_name"):
        if isinstance(values.get(key), str) and not values[key].strip():
            values[key] = None
    return values


def _find(data, person_id: int) -> dict:
    for person in data.people:
        if person.get("id") == person_id:
            return person
    abort(404, description=f"No person {person_id} on this diagram")


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


def _delta(person_id, field, after) -> dict:
    return {
        "item_kind": ItemKind.Person.value,
        "item_id": person_id,
        "field": field,
        "after": after,
    }


@bp.route("/people", methods=["POST"])
def create_person():
    values = _fields(request.get_json())
    if not values.get("name"):
        raise ValueError("A person needs a name")
    dia = diagram()
    if dia is None:
        abort(404)
    data = dia.get_diagram_data()
    person_id = (data.lastItemId or 0) + 1
    deltas = [_delta(person_id, field, value) for field, value in values.items()]
    deltas.append(
        {
            "item_kind": ItemKind.Diagram.value,
            "item_id": None,
            "field": "lastItemId",
            "after": person_id,
        }
    )
    _apply(deltas)
    return jsonify(_payload(_find(diagram().get_diagram_data(), person_id))), 201


@bp.route("/people/<int:person_id>", methods=["PATCH"])
def update_person(person_id: int):
    values = _fields(request.get_json())
    _find(diagram().get_diagram_data(), person_id)
    if not values:
        raise ValueError("Nothing to change on that person")
    _apply([_delta(person_id, field, value) for field, value in values.items()])
    return jsonify(_payload(_find(diagram().get_diagram_data(), person_id)))


@bp.route("/people/<int:person_id>", methods=["DELETE"])
def delete_person(person_id: int):
    """Removing someone cascades the way the app's own scene does: the record
    takes their bonds and the events that name them with them."""
    _find(diagram().get_diagram_data(), person_id)
    _apply([_delta(person_id, None, None)])
    return "", 204
