import datetime
import logging

from flask import current_app, jsonify, redirect, render_template, request, session, url_for

from btcopilot.auth import emails
from btcopilot.auth.blueprint import bp
from btcopilot.auth.invitation import Invitation
from btcopilot.auth.logincode import LoginCode
from btcopilot.auth.signin import (
    chat_home,
    current_web_session,
    ensure_user,
    sign_in,
    sign_out,
)
from btcopilot.auth.websession import WebSession
from btcopilot.pro.models import User

_log = logging.getLogger(__name__)


def _signed_in_user() -> User | None:
    web_session = current_web_session()
    if web_session and web_session.live():
        return web_session.user
    return None


@bp.route("/invite/<token>")
def invite(token):
    invitation = Invitation.query.filter_by(token=token).first()
    if not invitation or not invitation.live():
        _log.warning(f"Dead invitation token used from {request.remote_addr}")
        return render_template("chatauth/login.html", error="That link has expired."), 400
    invitation.consume()
    sign_in(ensure_user(invitation.email))
    return redirect(chat_home())


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "GET":
        if _signed_in_user():
            return redirect(chat_home())
        return render_template("chatauth/login.html")

    email = request.form.get("email", "").strip().lower()
    if not email:
        return render_template("chatauth/login.html", error="Enter your email."), 400

    window = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    if LoginCode.issued_since(email, window) >= current_app.config["LOGIN_CODES_PER_HOUR"]:
        _log.warning(f"Login code rate limit hit for {email}")
        return (
            render_template(
                "chatauth/login.html",
                email=email,
                sent=True,
                error="Too many codes requested. Try again in an hour.",
            ),
            429,
        )

    minutes = current_app.config["LOGIN_CODE_MINUTES"]
    if User.query.filter_by(username=email).first():
        _, code = LoginCode.issue(email, minutes)
        emails.send_login_code(email, code, minutes)
    else:
        _log.warning(f"Login code requested for unknown address {email}")
    return render_template("chatauth/login.html", email=email, sent=True)


@bp.route("/login/verify", methods=("POST",))
def verify():
    email = request.form.get("email", "").strip().lower()
    code = request.form.get("code", "").strip()
    login_code = LoginCode.pending(email)
    if not login_code or not login_code.matches(code):
        _log.warning(f"Bad login code for {email} from {request.remote_addr}")
        return (
            render_template(
                "chatauth/login.html",
                email=email,
                sent=True,
                error="That code is wrong or expired.",
            ),
            401,
        )
    login_code.consume()
    sign_in(User.query.filter_by(username=email).first())
    return redirect(chat_home())


@bp.route("/logout", methods=("POST",))
def logout():
    sign_out()
    return redirect(url_for("chatauth.login"))


@bp.route("/me")
def me():
    user = _signed_in_user()
    if not user:
        return jsonify({"user": None}), 401
    return jsonify(
        {
            "user": {
                "id": user.id,
                "email": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "roles": user.roles.split(","),
            }
        }
    )


@bp.route("/sessions")
def sessions():
    user = _signed_in_user()
    if not user:
        return jsonify({"sessions": []}), 401
    current = session.get("web_session_token")
    return jsonify(
        {
            "sessions": [
                {
                    "id": x.id,
                    "created_at": x.created_at.isoformat(),
                    "last_seen_at": x.last_seen_at.isoformat(),
                    "expires_at": x.expires_at.isoformat(),
                    "user_agent": x.user_agent,
                    "current": x.token == current,
                }
                for x in WebSession.live_for(user)
            ]
        }
    )


@bp.route("/sessions/<int:web_session_id>/revoke", methods=("POST",))
def revoke(web_session_id):
    user = _signed_in_user()
    if not user:
        return jsonify({"revoked": False}), 401
    target = WebSession.query.filter_by(id=web_session_id, user_id=user.id).first()
    if not target:
        return jsonify({"revoked": False}), 404
    target.revoke()
    if target.token == session.get("web_session_token"):
        session.clear()
    return jsonify({"revoked": True})
