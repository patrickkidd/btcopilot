"""The passages behind the case report's book buttons, read from the private
corpus the way the theory pages are and given only to a reader who may open
the diagram, never bundled in the page (R-0692, R-0715)."""

import json

from flask import abort, current_app, jsonify

from btcopilot.routes import asked_diagram, bp

PASSAGES = "passages.json"


@bp.route("/case-report-passages")
def case_report_passages():
    if asked_diagram() is None:
        abort(404)
    return jsonify(json.loads(current_app.extensions["passages"].file(PASSAGES)))
