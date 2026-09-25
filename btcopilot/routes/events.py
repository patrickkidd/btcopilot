"""Event CRUD on the user's own diagram. Every field btcopilot.schema.Event
carries is writable except its server-allocated id. Writes go through the
record's command log authored by the user, the way the coach's do (R-0084).

The spec's editing rules are enforced on save, not by refusing the write: a
saved event drops the values that no longer apply to its kind (switching a
shift to a death clears the shift values), so a stored event can never violate
them. Unknown field names are refused outright."""

from dataclasses import fields

from flask import abort, jsonify, request

from btcopilot import diagramjson, record
from btcopilot.routes import bp, delta, edit, writable_diagram
from btcopilot.timeline import DATE_FIELDS, event_payload
from btcopilot.intake import _enum_val, _parse_iso_date
from btcopilot.schema import (
    DateCertainty,
    Event,
    EventKind,
    ItemKind,
    RelationshipKind,
    VariableShift,
    asdict,
    validatedDateTimeText,
)

WRITABLE = {f.name for f in fields(Event)} - {"id"}
PERSON_FIELDS = ("person", "spouse", "child")
PERSON_LIST_FIELDS = ("relationshipTargets", "relationshipTriangles")
SHIFT_VARIABLES = ("symptom", "anxiety", "functioning", "relationship")
TRIANGLE_KINDS = (RelationshipKind.Inside, RelationshipKind.Outside)

ENUMS = {
    "kind": EventKind,
    "dateCertainty": DateCertainty,
    "symptom": VariableShift,
    "anxiety": VariableShift,
    "functioning": VariableShift,
    "relationship": RelationshipKind,
}


def _coerce(body: dict, people: set) -> dict:
    unknown = set(body) - WRITABLE
    if unknown:
        raise ValueError(f"Unknown event field(s): {', '.join(sorted(unknown))}")

    values = dict(body)
    for name, enum_class in ENUMS.items():
        if values.get(name) is not None:
            values[name] = enum_class(values[name])
    for name in DATE_FIELDS:
        if values.get(name):
            date = _parse_iso_date(values[name])
            if date is None:
                raise ValueError(f"{name} is not a date: {values[name]!r}")
            values[name] = date.isoformat()
    for name in PERSON_FIELDS:
        if values.get(name) is not None and values[name] not in people:
            raise ValueError(f"{name} {values[name]} is not a person in this diagram")
    for name in PERSON_LIST_FIELDS:
        missing = [i for i in (values.get(name) or []) if i not in people]
        if missing:
            raise ValueError(
                f"{name} names people not in this diagram: "
                f"{', '.join(str(i) for i in missing)}"
            )
    return values


def _normalize(event: Event) -> Event:
    if event.kind is not EventKind.Shift:
        for name in SHIFT_VARIABLES:
            setattr(event, name, None)
    if event.relationship is None:
        event.relationshipTargets = []
    if event.relationship not in TRIANGLE_KINDS:
        event.relationshipTriangles = []
    return event


def _qt_dates(chunk: dict) -> dict:
    """Committed events hold Qt dates, matching what the commit path writes and
    what the Pro app's Scene reads."""
    for key in DATE_FIELDS:
        if chunk.get(key):
            chunk[key] = validatedDateTimeText(chunk[key])
    return chunk


def _people(data) -> set:
    return {p.get("id") for p in data.people if isinstance(p, dict)}


def _find(data, event_id: int) -> dict:
    for event in data.events:
        if event.get("id") == event_id:
            return event
    abort(404)


def _deltas(event_id: int, fields: dict) -> list[dict]:
    return [
        delta(ItemKind.Event, event_id, field, diagramjson.to_json(value))
        for field, value in fields.items()
    ]


@bp.route("/events", methods=["POST"])
def create():
    data = writable_diagram().get_diagram_data()
    values = _coerce(request.get_json(), _people(data))
    if "kind" not in values:
        raise ValueError("An event needs a kind")
    event_id = record.next_id(data)
    event = _qt_dates(asdict(_normalize(Event(id=event_id, **values))))
    del event["id"]
    edit(
        _deltas(event_id, event)
        + [delta(ItemKind.Diagram, None, "lastItemId", event_id)]
    )
    return (
        jsonify(event_payload(_find(writable_diagram().get_diagram_data(), event_id))),
        201,
    )


@bp.route("/events/<int:event_id>", methods=["PATCH"])
def update(event_id: int):
    data = writable_diagram().get_diagram_data()
    existing = _find(data, event_id)
    merged = {
        key: _enum_val(value) for key, value in existing.items() if key in WRITABLE
    }
    for key in DATE_FIELDS:
        date = _parse_iso_date(existing.get(key))
        merged[key] = date.isoformat() if date else None
    merged.update(request.get_json())
    event = _qt_dates(
        asdict(_normalize(Event(id=event_id, **_coerce(merged, _people(data)))))
    )
    was, now = event_payload(existing), event_payload(event)
    changed = {key: event[key] for key in WRITABLE if now[key] != was[key]}
    if changed:
        edit(_deltas(event_id, changed))
    return jsonify(
        event_payload(_find(writable_diagram().get_diagram_data(), event_id))
    )


@bp.route("/events/<int:event_id>", methods=["DELETE"])
def delete(event_id: int):
    _find(writable_diagram().get_diagram_data(), event_id)
    edit([delta(ItemKind.Event, event_id, None, None)])
    return "", 204
