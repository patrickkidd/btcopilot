"""Codings: one coder's reading of one cut, on their own record of the case."""

from flask import abort, jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, scribe, snapshot
from btcopilot.review.models import Coding, Cut
from btcopilot.review.routes import (
    bp,
    coder,
    cut_or_404,
    my_coding,
    sees_others,
)


def payload(coding: Coding) -> dict:
    return coding.as_dict()


def blind_payload(coding: Coding) -> dict:
    """Who coded it is not shown while people are voting (R-0272)."""
    data = coding.as_dict()
    data.pop("user_id", None)
    return data


@bp.route("/codings")
def coding_index():
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not sees_others(cut, user):
        mine = my_coding(cut, user)
        return jsonify([payload(mine)] if mine else [])
    ratified = cut.ratified_at is not None
    shape = payload if ratified else blind_payload
    return jsonify([shape(c) for c in sorted(cut.codings, key=lambda c: c.id)])


@bp.route("/codings", methods=["POST"])
def coding_create():
    user = coder()
    body = request.get_json() or {}
    cut = cut_or_404(body.get("cut_id") or 0)
    existing = my_coding(cut, user)
    if existing is not None:
        return jsonify(payload(existing)), 200

    coding = Coding(
        cut_id=cut.id,
        user_id=user.id,
        diagram_id=_diagram_for(user, cut).id,
    )
    db.session.add(coding)
    db.session.commit()
    return jsonify(payload(coding)), 201


@bp.route("/codings/<int:coding_id>", methods=["PATCH"])
def coding_patch(coding_id: int):
    user = coder()
    coding = db.session.get(Coding, coding_id)
    if coding is None or coding.user_id != user.id:
        return "no coding of yours by that id", 404
    body = request.get_json() or {}

    if body.get("done_at"):
        if coding.done_at is None:
            coding.done_at = adapter.utcnow()
        if coding.cut.vote_opened_at is not None:
            snapshot.recompute(coding.cut)

    db.session.commit()
    return jsonify(payload(coding))


def _diagram_for(user, cut: Cut):
    """The coder's own record of this case: the one they built coding it last
    time, carried forward, or a fresh empty one (R-0267)."""
    discussion = db.session.get(adapter.Discussion, cut.discussion_id)
    case = adapter.case_diagram(discussion)
    previous = _previous_coding(user, case.id, cut.id)
    if previous is not None:
        return db.session.get(adapter.Diagram, previous.diagram_id)
    diagram = adapter.coding_diagram(user, f"coding of {case.name or case.id}")
    adapter.grant_write(diagram, user)
    db.session.flush()
    return diagram


def _previous_coding(user, case_diagram_id: int, cut_id: int) -> Coding | None:
    found = (
        Coding.query.join(Cut, Coding.cut_id == Cut.id)
        .join(adapter.Discussion, Cut.discussion_id == adapter.Discussion.id)
        .filter(
            Coding.user_id == user.id,
            Coding.cut_id != cut_id,
            adapter.Discussion.diagram_id == case_diagram_id,
        )
        .order_by(Coding.id.desc())
        .first()
    )
    return found


@bp.route("/codings/<int:coding_id>/thread")
def coding_thread(coding_id: int):
    """The conversation this coding is of: every turn from the session's first
    up to the cut, what this coder has already written from each, and the two
    lines across the thread — the last ratified cut and this one (R-0267)."""
    coding = _mine_or_404(coding_id)
    cut = coding.cut
    first = adapter.first_statement(cut.discussion_id)
    if first is None:
        raise ValueError("that session has no turns")
    turns = adapter.statements_between(
        cut.discussion_id, first.id, cut.end_statement_id
    )
    agreed = _last_ratified(cut)
    agreed_order = _order_of(agreed.end_statement_id) if agreed else None
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    written = _written_by_turn(coding.diagram_id, data)
    discussion = adapter.discussion_of(cut.discussion_id)

    return jsonify(
        {
            "coding_id": coding.id,
            "cut_id": cut.id,
            "diagram_id": coding.diagram_id,
            "done_at": coding.done_at.isoformat() if coding.done_at else None,
            "meeting_date": (
                cut.meeting_date.isoformat() if cut.meeting_date else None
            ),
            "session": (discussion.title or "").strip() or "an untitled conversation",
            "cut_day": _day(adapter.statement(cut.end_statement_id)),
            "agreed": (
                {
                    "order": agreed_order,
                    "day": _day(adapter.statement(agreed.end_statement_id)),
                    "ratified": agreed.ratified_at.strftime("%b %-d"),
                }
                if agreed
                else None
            ),
            "turns": [
                {
                    "id": turn.id,
                    "order": turn.order or 0,
                    "who": _who(turn),
                    "text": turn.text or "",
                    "lines": written.get(turn.id, []),
                    "above": agreed_order is not None
                    and (turn.order or 0) <= agreed_order,
                }
                for turn in turns
            ],
        }
    )


@bp.route("/codings/<int:coding_id>/scribe", methods=["POST"])
def coding_scribe(coding_id: int):
    """What the coder says one turn tells them happened, written into their own
    record by the scribe (R-0270)."""
    coding = _mine_or_404(coding_id)
    if coding.done_at is not None:
        raise ValueError("that coding is finished and cannot be added to")
    body = request.get_json() or {}
    said = (body.get("text") or "").strip()
    if not said:
        raise ValueError("say what the turn tells you happened")
    statement = adapter.statement(body.get("statement_id") or 0)
    if statement is None or statement.discussion_id != coding.cut.discussion_id:
        raise ValueError("that turn is not part of this conversation")
    if not _in_cut(coding.cut, statement):
        raise ValueError("coding happens between the last agreed line and the cut")

    written = scribe.write(coding, statement, said)
    db.session.commit()
    return jsonify(written)


def _mine_or_404(coding_id: int) -> Coding:
    user = coder()
    coding = db.session.get(Coding, coding_id)
    if coding is None or coding.user_id != user.id:
        abort(404)
    return coding


def _in_cut(cut: Cut, statement) -> bool:
    orders = adapter.statement_order(cut.discussion_id)
    start = orders.get(cut.start_statement_id)
    end = orders.get(cut.end_statement_id)
    here = orders.get(statement.id)
    return None not in (start, end, here) and start <= here <= end


def _last_ratified(cut: Cut) -> Cut | None:
    return (
        Cut.query.filter(
            Cut.discussion_id == cut.discussion_id,
            Cut.id != cut.id,
            Cut.ratified_at.isnot(None),
        )
        .order_by(Cut.id.desc())
        .first()
    )


def _order_of(statement_id: int) -> int | None:
    statement = adapter.statement(statement_id)
    return (statement.order or 0) if statement else None


def _written_by_turn(diagram_id: int, data: dict) -> dict[int, list[str]]:
    """What this coder wrote from each turn, in the record's own words."""
    by_turn: dict[int, list[int]] = {}
    for event_id, where in adapter.coded_in(diagram_id).items():
        statement_id = where.get("statement_id")
        if statement_id is not None:
            by_turn.setdefault(statement_id, []).append(event_id)
    return {
        statement_id: scribe.written(data, event_ids)
        for statement_id, event_ids in by_turn.items()
    }


def _who(statement) -> str:
    speaker = statement.speaker
    return (speaker.name if speaker and speaker.name else None) or "Someone"


def _day(statement) -> str:
    when = statement.created_at if statement else None
    return when.strftime("%b %-d") if when else "an unknown day"
