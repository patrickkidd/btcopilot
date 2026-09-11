"""Cuts: the windows Patrick puts on the table."""

import datetime

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, export, ruledraft, snapshot
from btcopilot.review.models import Cut
from btcopilot.review.routes import admin, bp, coder, cut_or_404


def payload(cut: Cut) -> dict:
    return cut.as_dict()


@bp.route("/cuts")
def cut_index():
    coder()
    query = Cut.query
    discussion_id = request.args.get("discussion_id", type=int)
    if discussion_id is not None:
        query = query.filter_by(discussion_id=discussion_id)
    return jsonify([payload(c) for c in query.order_by(Cut.id).all()])


@bp.route("/cuts/<int:cut_id>")
def cut_read(cut_id: int):
    coder()
    return jsonify(payload(cut_or_404(cut_id)))


@bp.route("/cuts", methods=["POST"])
def cut_create():
    user = admin()
    body = request.get_json() or {}
    discussion_id = body.get("discussion_id")
    end_statement_id = body.get("end_statement_id")
    if not discussion_id or not end_statement_id:
        raise ValueError("a cut needs a session and the turn it ends on")

    start_statement_id = body.get("start_statement_id") or _default_start(
        discussion_id
    )
    if start_statement_id is None:
        raise ValueError("that session has no turns to cut")

    orders = adapter.statement_order(discussion_id)
    window = _window(orders, start_statement_id, end_statement_id)
    _refuse_overlap(discussion_id, orders, window)

    cut = Cut(
        discussion_id=discussion_id,
        start_statement_id=start_statement_id,
        end_statement_id=end_statement_id,
        user_id=user.id,
        meeting_date=_date(body.get("meeting_date")),
    )
    db.session.add(cut)
    db.session.commit()
    return jsonify(payload(cut)), 201


@bp.route("/cuts/<int:cut_id>", methods=["PATCH"])
def cut_patch(cut_id: int):
    cut = cut_or_404(cut_id)
    body = request.get_json() or {}

    if "meeting_date" in body:
        coder()
        cut.meeting_date = _date(body["meeting_date"])

    if body.get("vote_opened_at"):
        admin()
        if cut.vote_opened_at is not None:
            raise ValueError("that vote is already open")
        cut.vote_opened_at = adapter.utcnow()
        snapshot.build(cut)
        snapshot.recompute(cut)

    if body.get("ratified_at"):
        admin()
        if cut.vote_opened_at is None:
            raise ValueError("a cut is ratified after its vote, not before")
        cut.ratified_at = adapter.utcnow()
        snapshot.recompute(cut)
        export.write(cut)
        ruledraft.draft_for(cut)

    db.session.commit()
    return jsonify(payload(cut))


def _default_start(discussion_id: int) -> int | None:
    """The turn after the last cut's end, or the session's first turn."""
    previous = (
        Cut.query.filter_by(discussion_id=discussion_id)
        .order_by(Cut.id.desc())
        .first()
    )
    if previous is None:
        first = adapter.first_statement(discussion_id)
        return first.id if first else None
    following = adapter.next_statement(discussion_id, previous.end_statement_id)
    return following.id if following else None


def _window(orders: dict[int, int], start_id: int, end_id: int) -> tuple[int, int]:
    if start_id not in orders or end_id not in orders:
        raise ValueError("a cut's start and end must be turns of its own session")
    start, end = orders[start_id], orders[end_id]
    if start > end:
        raise ValueError("a cut cannot end before it starts")
    return start, end


def _refuse_overlap(discussion_id: int, orders: dict[int, int], window):
    start, end = window
    for other in Cut.query.filter_by(discussion_id=discussion_id).all():
        theirs = (
            orders.get(other.start_statement_id),
            orders.get(other.end_statement_id),
        )
        if None in theirs:
            continue
        if start <= theirs[1] and theirs[0] <= end:
            raise ValueError(f"that window overlaps cut {other.id}")


def _date(value) -> datetime.date | None:
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)
