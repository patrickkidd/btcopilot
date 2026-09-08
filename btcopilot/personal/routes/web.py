import json
import os

from flask import jsonify, send_from_directory
from flask_wtf.csrf import generate_csrf
from markupsafe import escape

from btcopilot import auth
from btcopilot.personal.routes import bp, current_session, diagram
from btcopilot.personal.routes.sessions import session_payload, statements_payload
from btcopilot.personal.timeline import build_timeline
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
    discussion = current_session(user)
    in_use = diagram()
    bootstrap = {
        "user": {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        },
        "session": session_payload(discussion) if discussion else None,
        "statements": statements_payload(discussion) if discussion else [],
        "diagram": (
            {"id": in_use.id, "name": in_use.name} if in_use else None
        ),
    }
    head = (
        f'<meta name="csrf-token" content="{escape(generate_csrf())}">'
        f"<script>window.BOOTSTRAP={json.dumps(bootstrap)}</script>"
    )
    return page.replace("</head>", head + "</head>", 1)


@bp.route("/")
def index():
    return _page()


@bp.route("/sw.js")
def service_worker():
    """Served from the blueprint root so the worker's scope covers the app."""
    return send_from_directory(BUNDLE, "sw.js", mimetype="text/javascript")


@bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        BUNDLE, "manifest.webmanifest", mimetype="application/manifest+json"
    )


@bp.route("/timeline")
def timeline():
    in_use = diagram()
    data = in_use.get_diagram_data() if in_use else DiagramData()
    return jsonify(build_timeline(data))


