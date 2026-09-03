"""Two settings resources: the whole preferences object (coach, appearance and
the name/birthdate the coach uses), and the read-only account page."""

import datetime
import enum

from flask import jsonify, request

from btcopilot import auth
from btcopilot.companion.blueprint import bp
from btcopilot.extensions import db
from btcopilot.pro.models.preferences import PrefKey

PROFILE_FIELDS = ("first_name", "last_name", "birthdate")

# Patrick supplies the real numbers; nothing here may imply a price.
PLAN_PLACEHOLDER = "Beta — pricing has not been set yet."


class SignInMethod(enum.StrEnum):
    Password = "password"


def _preferences(user) -> dict:
    payload = {key.value: user.pref(key) for key in PrefKey}
    payload["first_name"] = user.first_name
    payload["last_name"] = user.last_name
    payload["birthdate"] = user.birthdate.isoformat() if user.birthdate else None
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
    known = {key.value for key in PrefKey} | set(PROFILE_FIELDS)
    unknown = set(body) - known
    if unknown:
        raise ValueError(f"Unknown preference(s): {', '.join(sorted(unknown))}")

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
            "diagrams": [
                {
                    "id": d.id,
                    "name": d.name,
                    "last_activity": d.saved_at().isoformat() if d.saved_at() else None,
                    "free": d.id == user.free_diagram_id,
                }
                for d in user.diagrams
            ],
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
