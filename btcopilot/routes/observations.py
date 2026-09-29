"""A report the person sends from the app: one observation of kind bug or
feedback on the diagram the app is on [Oracle: R-0056]."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.models import REPORTS, Observation, ObservationKind
from btcopilot.routes import bp, diagram

# What each kind carries, as one of these sets of fields: the person's own
# words about the app; for a bug, what broke and in which release of the app,
# or the request the server broke on and the id its answer carried.
SHAPES = {
    ObservationKind.Feedback: ({"text"},),
    ObservationKind.Bug: (
        {"text"},
        {"text", "error", "version"},
        {"status", "method", "path", "request_id", "version"},
    ),
}


@bp.route("/observations", methods=["POST"])
def create_observation():
    body = request.get_json()
    kind = ObservationKind(body["kind"])
    if kind not in REPORTS:
        raise ValueError(f"The app sends only {', '.join(REPORTS)}")
    fields = set(body) - {"kind", "turn_id"}
    if fields not in SHAPES[kind]:
        raise ValueError(f"A {kind} does not carry {', '.join(sorted(fields))}")
    row = Observation(
        diagram_id=diagram().id,
        turn_id=body["turn_id"],
        kind=kind,
        detail={field: body[field] for field in fields},
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id}), 201
