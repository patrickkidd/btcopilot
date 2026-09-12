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
from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Coding, Cut, Item, ReviewStatus, Vote
from btcopilot.schema import ItemKind

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


@bp.errorhandler(adapter.Invalid)
def _invalid_record(e):
    """A settle the record itself refuses — a shift with no variable, say. The
    room chose it, so it is told in the record's own words rather than shown a
    server error."""
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


def human_codings(cut: Cut) -> set[int]:
    """The finished codings people made. The coach's replay is a coding like
    any other, but nothing it thinks is in the ballot at all (R-0254)."""
    return {coding.id for coding in snapshot.voters(cut)}


def open_items(cut: Cut) -> list[Item]:
    """What the meeting has to settle: every disputed item of the cut that a
    person wrote, of any kind. People and pair bonds never reach the ballot;
    they wait for the room (R-0250). An item only the coach wrote is not the
    room's to settle (R-0254)."""
    people = human_codings(cut)
    return [
        item
        for item in cut.items
        if item.status is ReviewStatus.Disputed
        and any(take.get("coding_id") in people for take in item.takes or [])
    ]


def on_ballot(cut: Cut) -> list[Item]:
    """What a coder votes on: the disputed events of the cut, one per screen
    (R-0257). What the coders already read the same way is not voted on,
    people and pair bonds are settled at the meeting, and an item only the
    coach wrote down is not on the ballot."""
    return [
        item for item in open_items(cut) if item.item_kind is ItemKind.Event
    ]


def voted(cut: Cut, user) -> bool:
    """Voted on every item of that cut's ballot, which is what closes a coder
    out of the meeting's work."""
    item_ids = [item.id for item in on_ballot(cut)]
    if not item_ids:
        return True
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
    result,
    rules,
    tasks,
    turns,
    votes,
)


def init_app(app):
    app.register_blueprint(bp)
