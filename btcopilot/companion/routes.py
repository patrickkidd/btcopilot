import json
import os

from flask import jsonify, send_from_directory
from flask_wtf.csrf import generate_csrf
from markupsafe import escape

from btcopilot import auth
from btcopilot.companion.blueprint import bp, current_session
from btcopilot.companion.sessions import session_payload, statements_payload
from btcopilot.companion.timeline import build_timeline
from btcopilot.personal.models import Discussion
from btcopilot.schema import DiagramData, get_all_pdp_item_ids

BUNDLE = os.path.join(os.path.dirname(__file__), "static", "web")


def _page() -> str:
    """The Vite bundle's own index.html is the page; the server adds only what
    it alone knows — the CSRF token and the session the user returns to."""
    path = os.path.join(BUNDLE, "index.html")
    if not os.path.exists(path):
        raise RuntimeError(f"The web bundle is not built: {path} is missing")
    with open(path) as file:
        page = file.read()
    user = auth.current_user()
    discussion = current_session(user)
    bootstrap = {
        "user": {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        },
        "session": session_payload(discussion) if discussion else None,
        "statements": statements_payload(discussion) if discussion else [],
    }
    head = (
        f'<meta name="csrf-token" content="{escape(generate_csrf())}">'
        f"<script>window.COMPANION={json.dumps(bootstrap)}</script>"
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
    user = auth.current_user()
    diagram = user.free_diagram
    data = diagram.get_diagram_data() if diagram else DiagramData()
    payload = build_timeline(data)
    payload["extraction"] = _extraction_status(user, diagram, data)
    return jsonify(payload)


def _extraction_status(user, diagram, data: DiagramData) -> dict:
    """The picture only reflects committed diagram state; never let it look
    fresher than it is. States: extracting (a background extraction is
    running), pending_review (extracted items staged but not committed),
    chat_ahead (conversation past the extraction cursor), current."""
    state = "current"
    if diagram:
        discussions = Discussion.query.filter_by(
            user_id=user.id, diagram_id=diagram.id
        ).all()
        if any(d.extracting for d in discussions):
            state = "extracting"
        elif get_all_pdp_item_ids(data.pdp):
            state = "pending_review"
        else:
            for d in discussions:
                orders = [s.order for s in d.statements if s.order is not None]
                if orders and max(orders) > (d.extracted_through_order or 0):
                    state = "chat_ahead"
                    break
    return {"state": state, "up_to_date": state == "current"}
