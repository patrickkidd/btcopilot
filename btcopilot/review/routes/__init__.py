"""The review's door: one resource per table, nothing shaped like a verb.

A coder is a signed-in user with the auditor role (R-0311). Opening a vote and
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
    """A decision the record itself refuses — a shift with no variable, say. The
    room chose it, so it is told in the record's own words rather than shown a
    server error."""
    return str(e), 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}


def coder():
    """A coder is a user with the auditor role (R-0311). A professional licence
    is not a coder, and neither is a plain subscriber. Patrick is admin, and
    the review is his, so admin counts too."""
    user = auth.current_user()
    if user is None:
        abort(403)
    if not user.has_role(btcopilot.ROLE_AUDITOR) and not user.has_role(
        btcopilot.ROLE_ADMIN
    ):
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
    """What the ballot asks and the meeting has to decide — the same set: every
    disputed item of the cut a person wrote, people and bonds among them,
    because an event about somebody nobody has agreed on yet cannot be settled
    (R-0257, R-0326). What the coders already read the same way is not in it,
    and neither is an item only the coach wrote down (R-0254)."""
    people = human_codings(cut)
    return [
        item
        for item in cut.items
        if item.status is ReviewStatus.Disputed
        and any(opinion.get("coding_id") in people for opinion in item.opinions or [])
    ]


def voted(cut: Cut, user) -> bool:
    """Voted on every item of that cut's ballot, which is what closes a coder
    out of the meeting's work."""
    item_ids = [item.id for item in open_items(cut)]
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


def session_name(cut: Cut) -> str:
    """What the conversation a cut was taken from is called on screen."""
    discussion = adapter.discussion_of(cut.discussion_id)
    return (discussion.title or "").strip() or "an untitled conversation"


from btcopilot.review.routes import (  # noqa: E402  bp must exist first
    agenda,
    coders,
    codings,
    cuts,
    nudges,
    items,
    records,
    result,
    rules,
    tasks,
    turns,
    votes,
)


def init_app(app):
    app.register_blueprint(bp)
