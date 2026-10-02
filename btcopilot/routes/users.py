"""The people with an account, for admins to find by name."""

from flask import abort, jsonify, request
from sqlalchemy import or_

import btcopilot
from btcopilot import auth
from btcopilot.models import User
from btcopilot.routes import bp

FOUND = 20
LEAST = 2


def require_admin() -> None:
    if not auth.current_user().has_role(btcopilot.ROLE_ADMIN):
        abort(403)


@bp.route("/users")
def user_index():
    """`?q=` matches the email and the name, any case, best few only."""
    require_admin()
    words = request.args.get("q", "").strip()
    if len(words) < LEAST:
        raise ValueError(f"A search needs at least {LEAST} letters")
    like = f"%{words}%"
    full = User.first_name + " " + User.last_name
    found = (
        User.query.filter(
            or_(User.username.ilike(like), full.ilike(like)),
        )
        .order_by(User.first_name, User.last_name, User.username)
        .limit(FOUND)
    )
    return jsonify(
        [{"id": u.id, "username": u.username, "name": u.full_name().strip()} for u in found]
    )
