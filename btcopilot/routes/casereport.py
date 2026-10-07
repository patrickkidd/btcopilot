"""The passages behind the case report's book buttons, read from the private
corpus the way the theory pages are and given only to a reader who may open
the diagram, never bundled in the page (R-0692, R-0715); and a new version of
the report, every card the coach writes written again (R-0825)."""

import json

from flask import abort, current_app, jsonify

from btcopilot import auth, casereport
from btcopilot.routes import asked_diagram, bp, writable_diagram

PASSAGES = "passages.json"


@bp.route("/case-report-passages")
def case_report_passages():
    if asked_diagram() is None:
        abort(404)
    return jsonify(json.loads(current_app.extensions["passages"].file(PASSAGES)))


@bp.route("/case-report", methods=["POST"])
def case_report_rewrite():
    """Every card the coach writes, written again from the diagram as it
    stands, in the worker; 202 with the turn to follow on /turns/<id>/events."""
    dia = writable_diagram()
    if dia is None:
        abort(404)
    try:
        return jsonify(casereport.start(dia, auth.current_user())), 202
    except (casereport.Busy, casereport.Sessionless) as refused:
        abort(409, description=str(refused))
