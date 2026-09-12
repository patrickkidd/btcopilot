import datetime
import logging

import webauthn
from flask import current_app, jsonify, redirect, render_template, request, session, url_for
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from btcopilot.auth import emails
from btcopilot.auth.blueprint import bp
from btcopilot.auth.invitation import Invitation
from btcopilot.auth.logincode import LoginCode
from btcopilot.auth.passkey import Passkey
from btcopilot.auth.signin import (
    chat_home,
    current_web_session,
    ensure_user,
    sign_in,
    sign_out,
)
from btcopilot.auth.websession import WebSession
from btcopilot.extensions import db
from btcopilot.pro.models import User

REGISTER_CHALLENGE = "passkey_register_challenge"
LOGIN_CHALLENGE = "passkey_login_challenge"

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
        return (
            render_template(
                "chatauth/login.html",
                error="That link has been used or has expired. Sign in with your email instead.",
            ),
            400,
        )
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

    minutes = current_app.config["LOGIN_CODE_MINUTES"]
    window = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    if LoginCode.issued_since(email, window) >= current_app.config["LOGIN_CODES_PER_HOUR"]:
        _log.warning(f"Login code rate limit hit for {email}")
        return (
            render_template(
                "chatauth/login.html",
                email=email,
                sent=True,
                minutes=minutes,
                error="Too many codes requested. Try again in an hour.",
            ),
            429,
        )

    if User.query.filter_by(username=email).first():
        _, code = LoginCode.issue(email, minutes)
        emails.send_login_code(email, code, minutes)
    else:
        _log.warning(f"Login code requested for unknown address {email}")
    return render_template(
        "chatauth/login.html", email=email, sent=True, minutes=minutes
    )


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
                minutes=current_app.config["LOGIN_CODE_MINUTES"],
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


# The chat app owns /personal/sessions for its own sessions, so the devices a
# reader is signed in on are listed here.
@bp.route("/signins")
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


@bp.route("/signins/<int:web_session_id>/revoke", methods=("POST",))
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


def _rp_id() -> str:
    return current_app.config.get("RP_ID") or request.host.split(":")[0]


def _rp_origin() -> str:
    return current_app.config.get("RP_ORIGIN") or f"{request.scheme}://{request.host}"


@bp.route("/passkeys")
def passkeys():
    user = _signed_in_user()
    if not user:
        return jsonify({"passkeys": []}), 401
    return jsonify({"passkeys": [x.as_row() for x in Passkey.live_for(user)]})


@bp.route("/passkeys/register/options", methods=("POST",))
def passkey_register_options():
    user = _signed_in_user()
    if not user:
        return jsonify({"error": "Sign in first."}), 401
    options = webauthn.generate_registration_options(
        rp_id=_rp_id(),
        rp_name="Family Diagram",
        user_id=str(user.id).encode(),
        user_name=user.username,
        user_display_name=" ".join(
            x for x in (user.first_name, user.last_name) if x
        ) or user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(x.credential_id))
            for x in Passkey.live_for(user)
        ],
    )
    session[REGISTER_CHALLENGE] = bytes_to_base64url(options.challenge)
    return jsonify(options_to_json_dict(options))


@bp.route("/passkeys/register", methods=("POST",))
def passkey_register():
    user = _signed_in_user()
    if not user:
        return jsonify({"error": "Sign in first."}), 401
    challenge = session.pop(REGISTER_CHALLENGE, None)
    if not challenge:
        return jsonify({"error": "That took too long. Try again."}), 400
    try:
        verified = webauthn.verify_registration_response(
            credential=request.get_json(),
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=_rp_id(),
            expected_origin=_rp_origin(),
        )
    except InvalidRegistrationResponse as e:
        _log.warning(f"Passkey registration refused for {user.username}: {e}")
        return jsonify({"error": "That did not work."}), 400
    passkey = Passkey(
        user_id=user.id,
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=(request.get_json().get("response") or {}).get("transports") or [],
        name=(request.user_agent.string if request.user_agent else "")[:255],
    )
    db.session.add(passkey)
    db.session.commit()
    return jsonify({"passkey": passkey.as_row()})


@bp.route("/passkeys/login/options", methods=("POST",))
def passkey_login_options():
    """No email is asked for: the key on the device carries who it is."""
    options = webauthn.generate_authentication_options(
        rp_id=_rp_id(), user_verification=UserVerificationRequirement.REQUIRED
    )
    session[LOGIN_CHALLENGE] = bytes_to_base64url(options.challenge)
    return jsonify(options_to_json_dict(options))


@bp.route("/passkeys/login", methods=("POST",))
def passkey_login():
    challenge = session.get(LOGIN_CHALLENGE)
    if not challenge:
        return jsonify({"error": "That took too long. Try again."}), 400
    credential = request.get_json()
    passkey = Passkey.by_credential_id(credential.get("id", ""))
    if not passkey:
        _log.warning(f"Unknown or revoked passkey used from {request.remote_addr}")
        return jsonify({"error": "That did not work."}), 401
    try:
        verified = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=_rp_id(),
            expected_origin=_rp_origin(),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        _log.warning(f"Passkey sign-in refused from {request.remote_addr}: {e}")
        return jsonify({"error": "That did not work."}), 401
    user = passkey.user
    sign_in(user)
    passkey.used(verified.new_sign_count)
    return jsonify({"ok": True, "next": chat_home()})


@bp.route("/passkeys/<int:passkey_id>/revoke", methods=("POST",))
def passkey_revoke(passkey_id):
    user = _signed_in_user()
    if not user:
        return jsonify({"revoked": False}), 401
    target = Passkey.query.filter_by(id=passkey_id, user_id=user.id).first()
    if not target:
        return jsonify({"revoked": False}), 404
    target.revoke()
    return jsonify({"revoked": True})
