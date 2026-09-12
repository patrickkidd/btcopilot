"""The review's door: one resource per table, nothing shaped like a verb.

A coder is any signed-in user who can reach the review. Opening a vote and
ratifying are Patrick's, so they need the admin role (R-0273).
"""

import logging

from flask import Blueprint, abort, request
from flask_wtf.csrf import CSRFError, generate_csrf

import btcopilot
from btcopilot import auth
from btcopilot.extensions import csrf, db
from btcopilot.review.models import Coding, Cut, Item, Vote

_log = logging.getLogger(__name__)

bp = Blueprint("review", __name__, url_prefix="/review")


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
    """A rejected value is the client's fault: every endpoint here validates
    by raising ValueError."""
    return str(e), 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}


def coder():
    """The signed-in user, whoever reaches the review."""
    user = auth.current_user()
    if user is None:
        abort(403)
    return user


def admin():
    user = coder()
    if not user.has_role(btcopilot.ROLE_ADMIN):
        abort(403)
    return user


def cut_or_404(cut_id: int) -> Cut:
    cut = db.session.get(Cut, cut_id)
    if cut is None:
        abort(404)
    return cut


def item_or_404(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    return item


def my_coding(cut: Cut, user) -> Coding | None:
    return Coding.query.filter_by(cut_id=cut.id, user_id=user.id).first()


def voted(cut: Cut, user) -> bool:
    """Voted on every disputed item of that cut, which is what closes a coder
    out of the meeting's work."""
    item_ids = [item.id for item in cut.items]
    if not item_ids:
        return False
    mine = Vote.query.filter(
        Vote.review_item_id.in_(item_ids), Vote.user_id == user.id
    ).count()
    return mine >= len(item_ids)


def sees_others(cut: Cut, user) -> bool:
    """Blind until your own Done: a coder sees the pool only once their own
    coding of that cut is finished (R-0242). Patrick sees it throughout."""
    if user.has_role(btcopilot.ROLE_ADMIN):
        return True
    mine = my_coding(cut, user)
    return mine is not None and mine.done_at is not None


from btcopilot.review.routes import (  # noqa: E402  bp must exist first
    agenda,
    coders,
    codings,
    cuts,
    nudges,
    items,
    rules,
    tasks,
    turns,
    votes,
)


def init_app(app):
    app.register_blueprint(bp)
