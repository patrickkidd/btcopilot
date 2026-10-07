"""An uncaught error or rejected promise in the page, written as one log line
so it reaches the box's journal like any other (doc/MONITORING.md). Like a
report it takes no CSRF token, so only a post from this site is taken."""

import enum
import json
import logging

from flask import request

from btcopilot import auth, reports
from btcopilot.routes import bp

_log = logging.getLogger(__name__)

FIELDS = {"source", "message", "stack", "address", "release"}
MAX_BYTES = 64 * 1024


class Source(enum.StrEnum):
    Error = "error"
    Rejection = "rejection"


@bp.route("/browser-errors", methods=["POST"])
def create_browser_error():
    user = auth.signed_in()
    if not reports.allowed(f"browser errors from {reports.sender(user)}"):
        return "Too many errors from here; try again in an hour", 429
    request.max_content_length = MAX_BYTES
    body = request.get_json()
    unknown = set(body) - FIELDS
    if unknown:
        raise ValueError(f"A browser error does not carry {', '.join(sorted(unknown))}")
    line = {
        "source": Source(body["source"]),
        "message": body["message"],
        "stack": body.get("stack"),
        "address": body.get("address"),
        "release": body.get("release"),
        "user_id": user.id if user else None,
        "agent": request.user_agent.string,
    }
    _log.error(f"Browser error {json.dumps(line)}")
    return "", 204
