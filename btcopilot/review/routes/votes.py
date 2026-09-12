"""Votes: one per item per coder, before the meeting. Names are hidden while
people are voting (R-0272); the vote informs, the meeting settles (R-0274)."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review.adapter import User
from btcopilot.review.models import Item, Vote, VoteChoice
from btcopilot.review.routes.coders import initials
from btcopilot.review.routes import (
    admin,
    bp,
    coder,
    cut_or_404,
    item_or_404,
    on_ballot,
)


def payload(vote: Vote) -> dict:
    return vote.as_dict()


@bp.route("/votes")
def vote_index():
    """A coder reads their own votes on a cut, never anyone else's."""
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    item_ids = [i.id for i in cut.items]
    if not item_ids:
        return jsonify([])
    found = Vote.query.filter(
        Vote.review_item_id.in_(item_ids), Vote.user_id == user.id
    ).all()
    return jsonify([payload(v) for v in sorted(found, key=lambda v: v.id)])


@bp.route("/items/<int:item_id>/vote", methods=["PUT"])
def vote_put(item_id: int):
    user = coder()
    item = item_or_404(item_id)
    if item.cut.vote_opened_at is None:
        raise ValueError("that vote is not open")
    if item not in on_ballot(item.cut):
        raise ValueError("that item is not on the ballot")
    body = request.get_json() or {}
    choice = VoteChoice(body.get("choice"))

    vote = Vote.query.filter_by(review_item_id=item.id, user_id=user.id).first()
    if vote is None:
        vote = Vote(review_item_id=item.id, user_id=user.id)
        db.session.add(vote)
    vote.choice = choice
    vote.value = body.get("value")
    vote.reason = body.get("reason")
    db.session.commit()
    return jsonify(payload(vote))


@bp.route("/tallies")
def tally_index():
    """What the meeting screen reads: the counts per choice, and every vote
    with the name of the coder who cast it. The meeting is where names appear
    for the first time (R-0252)."""
    me = admin()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    rows = Item.query.filter_by(cut_id=cut.id).all()
    names = _names(me)
    return jsonify(
        [
            {
                "review_item_id": item.id,
                "counts": _counts(item),
                "votes": [
                    {
                        "user_id": vote.user_id,
                        "name": names.get(vote.user_id, "someone"),
                        "choice": vote.choice.value,
                        "value": vote.value,
                        "reason": vote.reason,
                    }
                    for vote in sorted(item.votes, key=lambda v: v.id)
                ],
            }
            for item in sorted(rows, key=lambda i: i.id)
        ]
    )


def _names(me) -> dict[int, str]:
    return {
        user.id: "you" if user.id == me.id else initials(user)
        for user in User.query.all()
    }


def _counts(item: Item) -> dict:
    counts = {choice.value: 0 for choice in VoteChoice}
    for vote in item.votes:
        counts[vote.choice.value] += 1
    return counts
