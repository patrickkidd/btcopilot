import json
import os

from flask import abort, jsonify, request, send_from_directory
from flask_wtf.csrf import generate_csrf
from markupsafe import escape

import btcopilot
from btcopilot import auth
from btcopilot.routes import asked_diagram, bp, current_session, diagram
from btcopilot.routes.diagrams import diagram_payload
from btcopilot.discussions import session_payload
from btcopilot.routes.sessions import thread
from btcopilot import casereport, place, playturn, questions, record, turnlog
from btcopilot.licence import professional
from btcopilot.timeline import build_timeline
from btcopilot.schema import DiagramData

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "web")


def _page() -> str:
    """The Vite bundle's own index.html is the page; the server adds only what
    it alone knows — the CSRF token and the session the user returns to."""
    path = os.path.join(BUNDLE, "index.html")
    if not os.path.exists(path):
        raise RuntimeError(
            f"The web bundle is not built ({path} is missing). "
            "Run: npm --prefix web install && npm --prefix web run build"
        )
    with open(path) as file:
        page = file.read()
    user = auth.current_user()
    in_use = diagram()
    discussion = current_session(user)
    bootstrap = {
        "user": {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "admin": user.has_role(btcopilot.ROLE_ADMIN),
            "coder": user.has_role(btcopilot.ROLE_AUDITOR)
            or user.has_role(btcopilot.ROLE_ADMIN),
            "pro": professional(user),
            "prefs": user.prefs(),
        },
        "session": session_payload(discussion) if discussion else None,
        "statements": thread(user, in_use),
        "diagram": diagram_payload(in_use, user) if in_use else None,
        "version": btcopilot.__version__,
        "beta": btcopilot.BETA,
    }
    head = (
        f'<meta name="csrf-token" content="{escape(generate_csrf())}">'
        f"<script>window.BOOTSTRAP={json.dumps(bootstrap)}</script>"
    )
    return page.replace("</head>", head + "</head>", 1)


# A home-screen app keeps the page it last loaded, so the page is asked for
# again on every load.
FRESH = {"Cache-Control": "no-cache"}


@bp.route("/")
def index():
    return _page(), FRESH


@bp.before_request
def _opened_at_address():
    """A browser opening an address in the app as a page gets the page there,
    even where the same path answers one of the page's own reads (R-0055)."""
    if (
        request.method == "GET"
        and request.headers.get("Sec-Fetch-Dest") == "document"
        and place.parse(request.path)
    ):
        return _page(), FRESH


@bp.after_request
def _told_apart(response):
    """A browser going back or forward shows the copy it kept of an address,
    and without this it kept one copy for the page and for the page's own read
    there, so forward to the account view showed the read's JSON (R-0055)."""
    if place.parse(request.path):
        response.vary.add("Sec-Fetch-Dest")
    return response


@bp.route("/<path:where>")
def address(where):
    """An address in the app that nothing else answers: the page, which puts
    itself where the address says."""
    if not place.parse(request.path):
        abort(404)
    return _page(), FRESH


@bp.route("/sw.js")
def service_worker():
    """Served from the blueprint root so the worker's scope covers the app."""
    return send_from_directory(BUNDLE, "sw.js", mimetype="text/javascript")


@bp.route("/apple-touch-icon.png")
def apple_touch_icon():
    """iOS reads the icon from the app's own path, not from the manifest."""
    return send_from_directory(BUNDLE, "apple-touch-icon.png", mimetype="image/png")


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        BUNDLE, "manifest.webmanifest", mimetype="application/manifest+json"
    )


@bp.route("/timeline")
def timeline():
    """The record `?diagram_id=` names — the diagram the page has open, or the
    record a coding is of — or without one the diagram the app is on."""
    in_use = asked_diagram()
    data = in_use.get_diagram_data() if in_use else DiagramData()
    payload = build_timeline(data)
    # what a play of each cluster told now would be told from, so the page
    # knows a kept play it may open again from one it must ask for anew
    told = playturn.digests(data, payload)
    for cluster in payload["clusters"]:
        cluster["digest"] = told[cluster["id"]]
    # Where each moment was written down comes from the command log, which is
    # the only place that knows: the coach stamps its own message on the
    # commands one turn made. What the record itself carries wins, for the
    # moments that were stamped before the log existed.
    if in_use:
        payload["coded_in"] = {
            **{str(k): v for k, v in record.coded_in(in_use.id).items()},
            **{str(k): v for k, v in payload["coded_in"].items()},
        }
    payload["asked_questions"] = questions.asked(in_use.id, data) if in_use else []
    # what changed since the coach wrote the case report, and its rewrite
    # running now (R-0825, R-0827)
    payload["case_report"] = {
        "out_of_date": casereport.stale(in_use.id, data) if in_use else None,
        "rewriting": turnlog.rewriting(in_use.id) if in_use else None,
    }
    return jsonify(payload)


