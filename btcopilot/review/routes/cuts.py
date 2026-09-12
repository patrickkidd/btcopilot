"""Cuts: the windows Patrick puts on the table."""

import datetime

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import (
    adapter,
    divergence,
    export,
    ruledraft,
    settle,
    snapshot,
)
from btcopilot.review.models import Cut
from btcopilot.review.routes import admin, bp, coder, cut_or_404, open_items


def payload(cut: Cut) -> dict:
    """The row, plus what the table screen names it by: the session it cuts,
    the turn it ends on and whether anyone has started coding it."""
    data = cut.as_dict()
    discussion = adapter.discussion_of(cut.discussion_id)
    end = adapter.statement(cut.end_statement_id)
    when = adapter.cut_day(cut.discussion_id, cut.end_statement_id)
    # The day the meeting falls on, as a day and nothing else: the screen puts
    # it straight into the phone's own date picker.
    data["meeting_date"] = cut.meeting_date.isoformat() if cut.meeting_date else None
    data["session"] = (discussion.title or "").strip() or "an untitled conversation"
    data["end_order"] = end.order if end else None
    data["cut_day"] = when.strftime("%b %-d") if when else None
    data["started"] = len(cut.codings) > 0
    return data


def table_cuts(meeting_date: str | None) -> list[Cut]:
    """What is on the table for one meeting, or everything not yet ratified."""
    query = Cut.query.filter(Cut.ratified_at.is_(None))
    if meeting_date:
        query = query.filter(Cut.meeting_date == _date(meeting_date))
    return query.order_by(Cut.id).all()


@bp.route("/cuts")
def cut_index():
    coder()
    query = Cut.query
    discussion_id = request.args.get("discussion_id", type=int)
    if discussion_id is not None:
        query = query.filter_by(discussion_id=discussion_id)
    meeting_date = request.args.get("meeting_date")
    if meeting_date is not None:
        query = query.filter_by(meeting_date=_date(meeting_date))
    if request.args.get("on_table") == "true":
        query = query.filter(Cut.ratified_at.is_(None))
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
    _refuse_before_ratified(discussion_id, orders, end_statement_id)
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

    if "end_statement_id" in body:
        admin()
        if cut.codings:
            raise ValueError("someone is already coding to that line")
        end_statement_id = body["end_statement_id"]
        orders = adapter.statement_order(cut.discussion_id)
        _refuse_before_ratified(cut.discussion_id, orders, end_statement_id)
        window = _window(orders, cut.start_statement_id, end_statement_id)
        _refuse_overlap(cut.discussion_id, orders, window, except_id=cut.id)
        cut.end_statement_id = end_statement_id

    if body.get("vote_opened_at"):
        admin()
        if cut.vote_opened_at is not None:
            raise ValueError("that vote is already open")
        cut.vote_opened_at = adapter.utcnow()
        snapshot.build(cut)
        snapshot.recompute(cut)

    if body.get("ratified_at"):
        user = admin()
        if cut.vote_opened_at is None:
            raise ValueError("a cut is ratified after its vote, not before")
        waiting = len(open_items(cut))
        if waiting:
            raise ValueError(f"{waiting} items still need a choice")
        cut.ratified_at = adapter.utcnow()
        # What every coder already read the same way goes into the record too:
        # the room confirms those by ratifying rather than by choosing.
        settle.confirm_agreed(cut, user)
        snapshot.recompute(cut, snapshot.AgreementPhase.Ratified)
        export.write(cut)
        ruledraft.draft_for(cut)
        cut.audit = divergence.reasons(divergence.rows(cut))

    db.session.commit()
    return jsonify(payload(cut))


@bp.route("/cuts/<int:cut_id>", methods=["DELETE"])
def cut_delete(cut_id: int):
    """Taking a conversation off the table, which is one tap and only before
    anyone has started coding it."""
    admin()
    cut = cut_or_404(cut_id)
    if cut.codings:
        raise ValueError("someone has already started coding that one")
    db.session.delete(cut)
    db.session.commit()
    return jsonify({"id": cut_id})


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


def _refuse_before_ratified(discussion_id: int, orders: dict[int, int], end_id: int):
    """A cut can never be placed before the last point already ratified
    (R-0267)."""
    ratified = (
        Cut.query.filter(
            Cut.discussion_id == discussion_id, Cut.ratified_at.isnot(None)
        )
        .order_by(Cut.id.desc())
        .first()
    )
    if ratified is None:
        return
    line = orders.get(ratified.end_statement_id)
    here = orders.get(end_id)
    if line is not None and here is not None and here <= line:
        raise ValueError("that line was already ratified; cut below it")


def _refuse_overlap(
    discussion_id: int, orders: dict[int, int], window, except_id: int | None = None
):
    start, end = window
    for other in Cut.query.filter_by(discussion_id=discussion_id).all():
        if other.id == except_id:
            continue
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
