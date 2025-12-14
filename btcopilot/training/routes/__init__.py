import os.path
import logging
import datetime

from flask import (
    Blueprint,
    redirect,
    url_for,
    request,
    abort,
    jsonify,
    g,
    render_template,
    current_app,
    session,
)
from flask_wtf.csrf import CSRFError

import btcopilot
from btcopilot import auth as btcopilot_auth
from btcopilot.extensions import db
from btcopilot.pro.models import User, Session
from btcopilot.personal.chat import Response, ask
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.security import add_security_headers

from .audit import bp as audit_bp
from .admin import bp as admin_bp
from .stream import bp as stream_bp
from .speakers import bp as speakers_bp
from .prompts import bp as prompts_bp
from .discussions import bp as discussions_bp
from .feedback import bp as feedback_bp
from .diagrams import bp as diagrams_bp
from .auth import bp as auth_bp
from .analysis import bp as analysis_bp
from .synthetic import bp as synthetic_bp


_log = logging.getLogger(__name__)

bp = Blueprint(
    "training",
    __name__,
    url_prefix="/training",
    template_folder="../templates",
    static_folder="../static",
)


# Set up CSRF protection for the blueprint
@bp.before_request
def _csrf_protect():
    from btcopilot.extensions import csrf
    from btcopilot.auth import is_personal_app_request

    # if not is_personal_app_request():
    #     csrf.protect()


@bp.errorhandler(CSRFError)
def _csrf_error(e):
    _log.warning(f"CSRF error: {e.description} from {request.remote_addr}")
    return e.description, 400


# Register child blueprints at import time
bp.register_blueprint(audit_bp)
bp.register_blueprint(admin_bp)
bp.register_blueprint(stream_bp)
bp.register_blueprint(speakers_bp)
bp.register_blueprint(prompts_bp)
bp.register_blueprint(discussions_bp)
bp.register_blueprint(feedback_bp)
bp.register_blueprint(diagrams_bp)
bp.register_blueprint(auth_bp)
bp.register_blueprint(analysis_bp)
bp.register_blueprint(synthetic_bp)


@bp.before_request
def _():
    # Auto-authenticate for development/MCP testing
    if current_app.config.get("CONFIG") == "development":
        auto_auth_user = current_app.config.get("AUTO_AUTH_USER")
        if auto_auth_user and "user_id" not in session:
            from btcopilot.pro.models import User

            user = User.query.filter_by(username=auto_auth_user).first()
            if user:
                session["user_id"] = user.id
                session.permanent = True
                if not user.roles:
                    user.roles = btcopilot.ROLE_SUBSCRIBER
                    db.session.merge(user)
                    db.session.commit()

    # Skip authentication for auth routes and login endpoint (handled separately)
    if request.endpoint and (
        request.endpoint.startswith("training.auth.")
        or request.endpoint in ("training.auth.login", "training.login")
    ):
        return

    # Get the required role dynamically based on the hierarchy
    required_role = btcopilot_auth.get_required_role()

    # Require the appropriate role (handles both authentication and authorization)
    btcopilot_auth.require_role(required_role)


@bp.context_processor
def inject_globals():
    """Make btcopilot and version available in all templates"""
    from btcopilot import version
    from flask_wtf.csrf import generate_csrf

    theme = request.cookies.get("theme", "light")

    return {
        "btcopilot": btcopilot,
        "version": version(),
        "csrf_token": generate_csrf,
        "theme": theme,
    }


@bp.after_request
def add_security_and_cache_headers(response):
    response = add_security_headers(response)

    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def init_app(app):
    from btcopilot.training.security import init_app

    # Configure security
    init_app(app)

    # Set session timeout
    app.permanent_session_lifetime = datetime.timedelta(hours=8)

    # # Register auth routes directly with app (no authentication required)
    # app.register_blueprint(auth_bp)

    # Register parent blueprint with app (child blueprints already registered at import time)
    app.register_blueprint(bp)


@bp.route("/")
def training_root():
    """Redirect to appropriate page based on user role"""
    user = btcopilot_auth.current_user()
    if not user:
        return redirect(url_for("training.auth.login"))

    return redirect(btcopilot_auth.get_landing_page_for_user(user))


@bp.route("/subscriber")
def subscriber_landing():
    """Landing page for subscribers with limited functionality"""
    user = btcopilot_auth.current_user()
    if not user:
        return redirect(url_for("training.auth.login"))

    # Only allow subscribers to access this page
    if user.has_role(btcopilot.ROLE_ADMIN) or user.has_role(btcopilot.ROLE_AUDITOR):
        return redirect(url_for("training.training_root"))

    return render_template("subscriber_landing.html", current_user=user)


@bp.route("/account")
@btcopilot_auth.minimum_role(btcopilot.ROLE_AUDITOR)
def account():
    """Account page with user info and licenses"""
    from btcopilot.pro.models import License
    from btcopilot.training.utils import get_breadcrumbs

    current_user = btcopilot_auth.current_user()
    if not current_user:
        return redirect(url_for("training.auth.login"))

    user = User.query.options(
        db.subqueryload(User.licenses).subqueryload(License.policy),
        db.subqueryload(User.licenses).subqueryload(License.activations),
    ).get(current_user.id)

    breadcrumbs = get_breadcrumbs("account")

    return render_template(
        "account.html",
        user=user,
        current_user=current_user,
        btcopilot=btcopilot,
        breadcrumbs=breadcrumbs,
    )


@bp.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    user = User.query.filter_by(username=username.lower()).first()
    if not user or not user.check_password(password):
        return abort(401)
    session = (
        Session.query.filter_by(user_id=user.id)
        .order_by(Session.created_at.desc())
        .first()
    )
    if not session:
        session = Session(user_id=user.id)
        db.session.add(session)
        db.session.commit()
    data = session.account_editor_dict()
    g.user = session.user
    _log.info(f"Logged in user: {user}")
    return jsonify(data)
