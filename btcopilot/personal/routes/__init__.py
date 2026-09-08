import logging

from flask import Blueprint, abort, request
from flask_wtf.csrf import CSRFError, generate_csrf

from btcopilot import auth
from btcopilot.extensions import csrf, db
from btcopilot.personal.models import Discussion
from btcopilot.personal.discussions import create_discussion

_log = logging.getLogger(__name__)

bp = Blueprint(
    "personal",
    __name__,
    url_prefix="/personal",
    template_folder="templates",
    static_folder="../static",
)


@bp.before_request
def _authenticate():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf.protect()
    auth._authenticate_training_app()


@bp.errorhandler(CSRFError)
def _csrf_error(e):
    _log.warning(f"CSRF error: {e.description} from {request.remote_addr}")
    return e.description, 400


@bp.errorhandler(ValueError)
def _value_error(e):
    """A rejected value is the client's fault, not a server fault: every
    endpoint here validates by raising ValueError."""
    return str(e), 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}


def last_activity(discussion: Discussion):
    times = [s.created_at for s in discussion.statements if s.created_at]
    return max(times) if times else discussion.created_at


def user_sessions(user, diagram_id: int | None = None) -> list[Discussion]:
    """The user's sessions on one diagram, most recently active first — which
    makes the session they last spoke in the one they return to. Without a
    diagram it is the one the app is on."""
    found = Discussion.query.filter_by(
        user_id=user.id, diagram_id=diagram_id or user.diagram_in_use()
    ).all()
    return sorted(found, key=lambda d: (last_activity(d), d.id), reverse=True)


def current_session(user, create: bool = False) -> Discussion | None:
    found = user_sessions(user)
    if found:
        return found[0]
    return create_discussion({}, diagram()) if create else None


def owned_session(session_id: int) -> Discussion:
    """Another user's session is a 404, not a 403: the app never confirms that
    a session it will not show exists."""
    discussion = db.session.get(Discussion, session_id)
    if discussion is None or discussion.user_id != auth.current_user().id:
        abort(404)
    return discussion


def diagram():
    """The diagram every surface reads and writes: the one the app is
    on, which is the free one until the user switches."""
    user = auth.current_user()
    return user.current_diagram or user.free_diagram


from btcopilot.personal.routes import (  # noqa: E402  bp must exist first
    diagrams,
    events,
    fixtures,
    interactions,
    migrate,
    people,
    play,
    sessions,
    settings,
    web,
)


def init_app(app):
    app.register_blueprint(bp)
