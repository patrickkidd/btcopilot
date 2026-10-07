"""The passages behind the case report's book buttons, read from the private
corpus the way the theory pages are and given only to a reader who may open
the diagram, never bundled in the page (R-0692, R-0715); and a new version of
the report, every card the coach writes written again (R-0825)."""

import json

from flask import abort, current_app, jsonify

from btcopilot import auth, casereport, turnlog
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.routes import asked_diagram, bp, opens, writable_diagram

PASSAGES = "passages.json"


@bp.route("/case-report-passages")
def case_report_passages():
    if asked_diagram() is None:
        abort(404)
    return jsonify(json.loads(current_app.extensions["passages"].file(PASSAGES)))


@bp.route("/case-report-rewrites", methods=["POST"])
def case_report_rewrite():
    """Every card the coach writes, written again from the diagram as it
    stands, in the worker; 202 with the rewrite to poll."""
    dia = writable_diagram()
    if dia is None:
        abort(404)
    try:
        return jsonify(casereport.start(dia, auth.current_user())), 202
    except (casereport.Busy, casereport.Sessionless) as refused:
        abort(409, description=str(refused))


@bp.route("/case-report-rewrites/<rewrite_id>")
def case_report_rewrite_state(rewrite_id: str):
    """Running, done or failed; a rewrite of a family the reader may not open
    is a 404, as is one too old to remember."""
    family = turnlog.report(rewrite_id)
    found = db.session.get(Diagram, family) if family is not None else None
    if found is None or not opens(found, auth.current_user()):
        abort(404)
    return jsonify({"id": rewrite_id, "state": casereport.state(rewrite_id, found.id).value})
