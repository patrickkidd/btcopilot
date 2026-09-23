import os
import sys
import logging
from typing import Union

from flask import g, request, session, redirect, url_for
from werkzeug.exceptions import HTTPException

from btcopilot.models import User
from btcopilot.auth import routes
from btcopilot.auth.blueprint import bp
from btcopilot.auth.longsessions import LongSessions
from btcopilot.auth.signin import SESSION_TOKEN
from btcopilot.auth.websession import WebSession


_log = logging.getLogger(__name__)


CONFIG_DEFAULTS = {
    "CHAT_HOME": "/app/",
    "CHAT_SESSION_DAYS": 180,
    "LOGIN_CODE_MINUTES": 10,
    "LOGIN_CODES_PER_HOUR": 5,
    "INVITATION_DAYS": 14,
    # A test sandbox sets this so a fixture link keeps working across windows
    # and devices until it expires; production links are used once.
    "INVITATION_REUSABLE": False,
    "SITE_URL": "http://127.0.0.1:8888",
}


def init_app(app):
    for key, value in CONFIG_DEFAULTS.items():
        app.config.setdefault(key, value)
    app.session_interface = LongSessions()
    # Sign-in belongs to the chat app the reader is signing in to, so its pages
    # live under the same path as the app itself.
    app.register_blueprint(bp, url_prefix="/app")


def is_chat_app_request() -> bool:
    return request.path.startswith("/app")


def login_url() -> str:
    return url_for("chatauth.login", next=request.url)


def _set_tracing_tags(user):
    """Set tracing tags for the current user if available."""
    if "ddtrace" in sys.modules:
        from ddtrace import tracer

        span = tracer.current_span()
        if span and not getattr(user, "IS_ANONYMOUS", False):
            span.set_tag("user.id", user.id)
            span.set_tag("user.username", user.username)
            span.set_tag("user.name", f"{user.first_name} {user.last_name}")


def current_user() -> Union[User, None]:
    return g.get("current_user")


def _web_session_ok() -> bool:
    """Passwordless sign-ins carry a server-side session record so they can be
    revoked."""
    token = session.get(SESSION_TOKEN)
    if not token:
        return True
    web_session = WebSession.query.filter_by(token=token).first()
    if not web_session or not web_session.live():
        return False
    web_session.touch()
    return True


def authenticate_web() -> User | None:
    # First, check for auto-auth environment variable (for testing/development)
    auto_auth_email = os.environ.get("FLASK_AUTO_AUTH_USER")
    if auto_auth_email:
        user = User.query.filter_by(username=auto_auth_email).first()
        if user:
            g.current_user = user
            _set_tracing_tags(user)
            return user

    # Next, try session-based authentication (for web users)
    user_id = session.get("user_id")
    if user_id:
        user = User.query.get(user_id)
        if user and _web_session_ok():
            g.current_user = user
            _set_tracing_tags(user)
            return user
        else:
            # Invalid session - clear it
            session.clear()

    redirect_response = redirect(login_url())
    # Create a proper HTTP exception with the redirect response
    exception = HTTPException()
    exception.response = redirect_response
    raise exception
