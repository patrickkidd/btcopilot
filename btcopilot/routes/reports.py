"""A bug or feedback the coach offered and the person answered on the page.
It takes no CSRF token, so only a post from this site is taken
[Oracle: R-0056]."""

from flask import jsonify, request

from btcopilot import auth, reports
from btcopilot.routes import bp


@bp.route("/reports", methods=["POST"])
def create_report():
    user = auth.signed_in()
    if not reports.allowed(reports.sender(user)):
        return "Too many reports from here; try again in an hour", 429
    body = request.get_json()
    row = reports.take(body, user, reports.about(body, user))
    return jsonify({"id": row.id}), 201
