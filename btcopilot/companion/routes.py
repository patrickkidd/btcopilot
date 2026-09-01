import logging

from flask import Blueprint, jsonify, render_template, request
from flask_wtf.csrf import CSRFError, generate_csrf

from btcopilot import auth
from btcopilot.auth import _authenticate_training_app
from btcopilot.companion.timeline import build_timeline
from btcopilot.extensions import csrf, db
from btcopilot.personal.chat import Response, ask
from btcopilot.personal.models import Discussion
from btcopilot.personal.routes.discussions import (
    _create_discussion,
    _sync_chat_speakers,
)
from btcopilot.schema import DiagramData, get_all_pdp_item_ids

_log = logging.getLogger(__name__)

bp = Blueprint(
    "companion",
    __name__,
    url_prefix="/companion",
    template_folder="templates",
    static_folder="static",
)


@bp.before_request
def _authenticate():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf.protect()
    _authenticate_training_app()


@bp.errorhandler(CSRFError)
def _csrf_error(e):
    _log.warning(f"CSRF error: {e.description} from {request.remote_addr}")
    return e.description, 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}


def _discussion(user, create: bool = False) -> Discussion | None:
    discussion = (
        Discussion.query.filter_by(user_id=user.id)
        .filter(Discussion.diagram_id == user.free_diagram_id)
        .order_by(Discussion.id.desc())
        .first()
    )
    if discussion is None and create:
        discussion = _create_discussion({})
    return discussion


@bp.route("/")
def index():
    user = auth.current_user()
    discussion = _discussion(user)
    statements = []
    if discussion:
        for s in discussion.statements:
            role = "coach" if s.speaker_id == discussion.chat_ai_speaker_id else "user"
            statements.append({"role": role, "text": s.text})
    return render_template("companion/index.html", statements=statements, user=user)


@bp.route("/chat", methods=["POST"])
def chat():
    if request.headers.get("Content-Type") != "application/json":
        return ("Only 'Content-Type: application/json' is supported", 415)
    user = auth.current_user()
    statement = request.json["statement"]
    discussion = _discussion(user, create=True)
    _sync_chat_speakers(discussion)
    response: Response = ask(discussion, statement)
    db.session.commit()
    return jsonify({"statement": response.statement, "discussion_id": discussion.id})


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


def init_app(app):
    app.register_blueprint(bp)
