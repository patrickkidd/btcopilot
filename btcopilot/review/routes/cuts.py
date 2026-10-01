"""Cuts: the windows Patrick puts on the agenda."""

import datetime

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import (
    adapter,
    divergence,
    export,
    notify,
    ruledraft,
    decision,
    snapshot,
)
from btcopilot.review.models import Cut
from btcopilot.review.routes import (
    admin,
    bp,
    coder,
    cut_or_404,
    open_items,
    session_name,
)


def payload(cut: Cut) -> dict:
    """The row, plus what the agenda screen names it by: the sitting it ends
    in, the turn it ends on and whether anyone has started coding it, and the
    sitting its first line was said in, which is where the picker opens."""
    data = cut.as_dict()
    when = adapter.cut_day(cut.end_statement_id)
    # The day the meeting falls on, as a day and nothing else: the screen puts
    # it straight into the phone's own date picker.
    data["meeting_date"] = cut.meeting_date.isoformat() if cut.meeting_date else None
    data["session"] = session_name(cut)
    data["sitting_id"] = adapter.statement(cut.start_statement_id).discussion_id
    data["end_order"] = adapter.statement_order(cut.diagram_id).get(cut.end_statement_id)
    data["cut_day"] = when.strftime("%b %-d") if when else None
    data["started"] = len(cut.codings) > 0
    return data


def agenda_cuts(meeting_date: str | None) -> list[Cut]:
    """What is on the agenda for one meeting, or everything not yet ratified."""
    query = Cut.query.filter(Cut.ratified_at.is_(None))
    if meeting_date:
        query = query.filter(Cut.meeting_date == _date(meeting_date))
    return query.order_by(Cut.id).all()


@bp.route("/cuts")
def cut_index():
    coder()
    query = Cut.query
    diagram_id = request.args.get("diagram_id", type=int)
    if diagram_id is not None:
        query = query.filter_by(diagram_id=diagram_id)
    meeting_date = request.args.get("meeting_date")
    if meeting_date is not None:
        query = query.filter_by(meeting_date=_date(meeting_date))
    if request.args.get("on_agenda") == "true":
        query = query.filter(Cut.ratified_at.is_(None))
    return jsonify([payload(c) for c in query.order_by(Cut.id).all()])


@bp.route("/cuts/<int:cut_id>")
def cut_read(cut_id: int):
    coder()
    return jsonify(payload(cut_or_404(cut_id)))


@bp.route("/cuts", methods=["POST"])
def cut_create():
    """A cut is a first and a last line of one family's thread, in one sitting
    or across several; without a first line it starts right after the last
    cut."""
    user = admin()
    body = request.get_json() or {}
    end = adapter.statement(body.get("end_statement_id") or 0)
    if end is None:
        raise ValueError("a cut needs the line it ends on")
    diagram_id = end.discussion.diagram_id
    start_statement_id = body.get("start_statement_id") or _default_start(diagram_id)
    if start_statement_id is None:
        raise ValueError("that thread has no lines left to cut")

    orders = adapter.statement_order(diagram_id)
    _refuse_before_ratified(diagram_id, orders, start_statement_id, end.id)
    window = _window(orders, start_statement_id, end.id)
    _refuse_overlap(diagram_id, orders, window)

    cut = Cut(
        diagram_id=diagram_id,
        start_statement_id=start_statement_id,
        end_statement_id=end.id,
        user_id=user.id,
        meeting_date=_date(body.get("meeting_date")),
    )
    db.session.add(cut)
    db.session.flush()
    _tell(cut)
    db.session.commit()
    return jsonify(payload(cut)), 201


@bp.route("/cuts/<int:cut_id>", methods=["PATCH"])
def cut_patch(cut_id: int):
    cut = cut_or_404(cut_id)
    body = request.get_json() or {}

    if "meeting_date" in body:
        admin()
        cut.meeting_date = _date(body["meeting_date"])
        _tell(cut)

    if "start_statement_id" in body or "end_statement_id" in body:
        admin()
        if cut.codings:
            raise ValueError("someone is already coding to that line")
        start_id = body.get("start_statement_id", cut.start_statement_id)
        end_id = body.get("end_statement_id", cut.end_statement_id)
        orders = adapter.statement_order(cut.diagram_id)
        _refuse_before_ratified(cut.diagram_id, orders, start_id, end_id)
        window = _window(orders, start_id, end_id)
        _refuse_overlap(cut.diagram_id, orders, window, except_id=cut.id)
        cut.start_statement_id, cut.end_statement_id = start_id, end_id

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
        decision.confirm_agreed(cut, user)
        snapshot.recompute(cut, snapshot.AgreementPhase.Ratified)
        export.write(cut)
        ruledraft.draft_for(cut, user.id)
        cut.audit = divergence.reasons(divergence.rows(cut), cut, user.id)

    db.session.commit()
    return jsonify(payload(cut))


@bp.route("/cuts/<int:cut_id>", methods=["DELETE"])
def cut_delete(cut_id: int):
    """Taking a conversation off the agenda, which is one tap and only before
    anyone has started coding it."""
    admin()
    cut = cut_or_404(cut_id)
    if cut.codings:
        raise ValueError("someone has already started coding that one")
    db.session.delete(cut)
    db.session.commit()
    return jsonify({"id": cut_id})


def _tell(cut: Cut):
    """A cut is due once it has a meeting date, which is when its coders hear
    of it (the app places a cut first and dates it after)."""
    if cut.meeting_date:
        notify.told(cut, adapter.utcnow())


def _default_start(diagram_id: int) -> int | None:
    """The line after the last cut's end, or the thread's first line."""
    previous = (
        Cut.query.filter_by(diagram_id=diagram_id).order_by(Cut.id.desc()).first()
    )
    if previous is None:
        first = adapter.first_statement(diagram_id)
        return first.id if first else None
    following = adapter.next_statement(diagram_id, previous.end_statement_id)
    return following.id if following else None


def _window(orders: dict[int, int], start_id: int, end_id: int) -> tuple[int, int]:
    if start_id not in orders or end_id not in orders:
        raise ValueError("a cut's first and last lines must be lines of one thread")
    start, end = orders[start_id], orders[end_id]
    if start > end:
        raise ValueError("a cut cannot end before it starts")
    return start, end


def _refuse_before_ratified(diagram_id: int, orders: dict[int, int], *ends: int):
    """No end of a cut can sit at or before the last point already ratified
    (R-0267)."""
    ratified = (
        Cut.query.filter(Cut.diagram_id == diagram_id, Cut.ratified_at.isnot(None))
        .order_by(Cut.id.desc())
        .first()
    )
    if ratified is None:
        return
    line = orders.get(ratified.end_statement_id)
    if line is not None and any(orders.get(end, line + 1) <= line for end in ends):
        raise ValueError("that line was already ratified; cut below it")


def _refuse_overlap(
    diagram_id: int, orders: dict[int, int], window, except_id: int | None = None
):
    start, end = window
    for other in Cut.query.filter_by(diagram_id=diagram_id).all():
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
