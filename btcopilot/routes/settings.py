"""Two settings resources: the whole preferences object (coach, appearance and
the name/birthdate the coach uses), and the read-only account page."""

import datetime
import enum

from flask import abort, jsonify, request

import btcopilot
from btcopilot import auth, shadow
from btcopilot.routes import bp
from btcopilot.licence import professional
from btcopilot.routes.diagrams import diagrams_payload
from btcopilot.extensions import db
from btcopilot.models.preferences import SHADOW_CANDIDATES, PrefKey

PROFILE_FIELDS = ("first_name", "last_name", "birthdate")

# Patrick supplies the real numbers; nothing here may imply a price.
PLAN_PLACEHOLDER = "Beta — pricing has not been set yet."


class SignInMethod(enum.StrEnum):
    Password = "password"


def _preferences(user) -> dict:
    expires = shadow.expiry(user, datetime.datetime.utcnow())
    payload = {key.value: user.pref(key) for key in PrefKey}
    payload["shadow_expires_at"] = expires and expires.isoformat()
    payload["first_name"] = user.first_name
    payload["last_name"] = user.last_name
    payload["birthdate"] = user.birthdate.isoformat() if user.birthdate else None
    payload["shadow_candidates"] = SHADOW_CANDIDATES
    if user.has_role(btcopilot.ROLE_ADMIN):
        payload["shadow_cost"] = shadow.spend(datetime.datetime.utcnow())
    return payload


def _birthdate(value):
    return datetime.date.fromisoformat(value) if value else None


@bp.route("/preferences")
def preferences():
    return jsonify(_preferences(auth.current_user()))


@bp.route("/preferences", methods=["PATCH"])
def set_preferences():
    user = auth.current_user()
    body = request.get_json()
    known = {key.value for key in PrefKey} - {PrefKey.ShadowSince} | set(PROFILE_FIELDS)
    unknown = set(body) - known
    if unknown:
        raise ValueError(f"Unknown preference(s): {', '.join(sorted(unknown))}")
    # Shadows cost money nobody is charged for, so only staff may turn them on.
    if body.get(PrefKey.ShadowModels) and not user.has_role(btcopilot.ROLE_AUDITOR):
        abort(403)

    now = datetime.datetime.utcnow()
    shadow.expiry(user, now)
    if PrefKey.ShadowModels in body:
        shadow.switch(user, body.pop(PrefKey.ShadowModels), now)
    user.set_prefs(**{k: v for k, v in body.items() if k not in PROFILE_FIELDS})
    if "first_name" in body:
        user.first_name = body["first_name"]
    if "last_name" in body:
        user.last_name = body["last_name"]
    if "birthdate" in body:
        user.birthdate = _birthdate(body["birthdate"])
    db.session.commit()
    return jsonify(_preferences(user))


@bp.route("/account")
def account():
    user = auth.current_user()
    return jsonify(
        {
            "email": user.username,
            "sign_in_method": SignInMethod.Password,
            "plan": PLAN_PLACEHOLDER,
            "pro": professional(user),
            "diagrams": diagrams_payload(user),
            "licenses": [
                {
                    "id": l.id,
                    "policy": l.policy.name,
                    "status": l.status(),
                }
                for l in user.licenses
            ],
        }
    )
