import datetime
import logging

from flask import current_app, request, session

import btcopilot
from btcopilot.auth.websession import WebSession
from btcopilot.extensions import db
from btcopilot.pro.models import User

SESSION_TOKEN = "web_session_token"

_log = logging.getLogger(__name__)


def chat_home() -> str:
    return current_app.config["CHAT_HOME"]


def ensure_user(email: str) -> User:
    """Login is signup: an invited address with no account gets one."""
    user = User.query.filter_by(username=email).first()
    if user:
        return user
    user = User(username=email, status="confirmed", roles=btcopilot.ROLE_SUBSCRIBER)
    db.session.add(user)
    db.session.commit()
    user.set_free_diagram(_commit=True)
    _log.info(f"Created user {user.username} from an invitation")
    return user


def sign_in(user: User) -> WebSession:
    web_session = WebSession.start(
        user,
        current_app.config["CHAT_SESSION_DAYS"],
        request.user_agent.string if request.user_agent else "",
    )
    session.clear()
    session["user_id"] = user.id
    session[SESSION_TOKEN] = web_session.token
    # The training app ages a session by this stamp and clears the cookie when
    # it is missing, which would sign the chat user out on any shared route.
    session["logged_in_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    session.permanent = True
    return web_session


def current_web_session() -> WebSession | None:
    token = session.get(SESSION_TOKEN)
    if not token:
        return None
    return WebSession.query.filter_by(token=token).first()


def sign_out():
    web_session = current_web_session()
    if web_session:
        web_session.revoke()
    session.clear()
