"""A report the person sends from the app: one observation of kind bug or
feedback on the diagram the app is on [Oracle: R-0056]."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.models import REPORTS, Observation, ObservationKind
from btcopilot.routes import bp, diagram

# What each kind carries: the person's words, and for a bug what broke and in
# which release of the app.
FIELDS = {
    ObservationKind.Bug: ("text", "error", "version"),
    ObservationKind.Feedback: ("text",),
}


@bp.route("/observations", methods=["POST"])
def create_observation():
    body = request.get_json()
    kind = ObservationKind(body["kind"])
    if kind not in REPORTS:
        raise ValueError(f"The app sends only {', '.join(REPORTS)}")
    unknown = set(body) - {"kind", "turn_id", *FIELDS[kind]}
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    row = Observation(
        diagram_id=diagram().id,
        turn_id=body["turn_id"],
        kind=kind,
        detail={field: body[field] for field in FIELDS[kind]},
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id}), 201
