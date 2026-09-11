"""Codings: one coder's reading of one cut, on their own record of the case."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, snapshot
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
