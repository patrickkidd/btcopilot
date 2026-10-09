"""The chat's vote: a coach turn's replies, the real one and its shadows,
shown in a random order with no model named until the reader has picked
(R-0636). The reader's pick is the only judgement; no model judges another.

A pair is a shadow turn against the real reply it shadowed."""

import enum
import random
import string

from flask import abort, jsonify, request

import btcopilot
from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Pick, PickChoice, PickSource
from btcopilot.review.models.pick import NOTE_CAP
from btcopilot.review.routes import bp, coder


class Ref(enum.StrEnum):
    Shadow = "shadow"
    Statement = "statement"


def _shadows(*where):
    rows = adapter.ShadowTurn.query.filter(
        adapter.ShadowTurn.text.isnot(None), adapter.ShadowTurn.error.is_(None), *where
    )
    for row in rows:
        discussion = adapter.discussion_of(row.discussion_id)
        real = adapter.Statement.query.filter_by(
            turn_id=row.turn_id, speaker_id=discussion.chat_ai_speaker_id
        ).one()
        call = (
            adapter.ModelCall.query.filter_by(turn_id=row.turn_id)
            .order_by(adapter.ModelCall.id)
            .first()
        )
        if call.model == row.model:
            continue
        said = row.statement_id
        yield (
            f"shadow:{row.id}",
            PickSource.Shadow,
            {"model": call.model, "statement_id": real.id, "said": said},
            {"model": row.model, "shadow_id": row.id, "said": said},
        )


def _text(ref: dict) -> str:
    if "shadow_id" in ref:
        return db.session.get(adapter.ShadowTurn, ref["shadow_id"]).text
    return adapter.statement(ref["statement_id"]).text


def _serve(pairs) -> list[Pick]:
    """The pick of each pair, made the first time the pair is seen: its side
    order is fixed here, at random, with the two replies' texts as served."""
    served = {pick.pair: pick for pick in Pick.query}
    picks = []
    for pair, source, one, other in pairs:
        if pair in served:
            picks.append(served[pair])
            continue
        left, right = (one, other) if random.random() < 0.5 else (other, one)
        pick = Pick(
            pair=pair,
            source=source,
            left_ref=left,
            right_ref=right,
            left_text=_text(left),
            right_text=_text(right),
        )
        db.session.add(pick)
        picks.append(pick)
    db.session.commit()
    return picks


def _owner(user, discussion):
    if discussion.user_id != user.id:
        abort(403)


def _ref_key(ref: dict) -> tuple:
    if "shadow_id" in ref:
        return (Ref.Shadow, ref["shadow_id"])
    return (Ref.Statement, ref["statement_id"])


def _turn(turn_id: str):
    """One coach turn's replies keyed a, b, c in a random order, the real one
    among them, and a pick for each shadow against the real reply with how it
    was voted, if it was, and how many shadows are still running out of how
    many were started (R-0636). No model is named."""
    user = coder()
    said = adapter.Statement.query.filter_by(turn_id=turn_id).first()
    if said is None:
        abort(404)
    _owner(user, adapter.discussion_of(said.discussion_id))
    picks = _serve(_shadows(adapter.ShadowTurn.turn_id == turn_id))
    refs = {_ref_key(pick.left_ref): pick.left_text for pick in picks}
    refs.update({_ref_key(pick.right_ref): pick.right_text for pick in picks})
    order = random.sample(sorted(refs), len(refs))
    keys = dict(zip(order, string.ascii_lowercase))
    real = next((ref for ref in keys if ref[0] is Ref.Statement), None)
    rows = adapter.ShadowTurn.query.filter_by(turn_id=turn_id)
    return jsonify(
        {
            "replies": [{"key": keys[ref], "text": refs[ref]} for ref in order],
            "real_key": keys.get(real),
            "picks": [
                {
                    "id": pick.id,
                    "left_key": keys[_ref_key(pick.left_ref)],
                    "right_key": keys[_ref_key(pick.right_ref)],
                    "choice": pick.choice,
                    "left_acceptable": pick.left_acceptable,
                    "right_acceptable": pick.right_acceptable,
                    "note": pick.note,
                    "shown": _shown(pick),
                }
                for pick in picks
            ],
            "pending": rows.filter(
                adapter.ShadowTurn.text.is_(None), adapter.ShadowTurn.error.is_(None)
            ).count(),
            "expected": rows.count(),
        }
    )


def _shown(pick: Pick) -> PickChoice | None:
    """Which side was on screen first when it was voted (R-0640)."""
    for side, ref in (
        (PickChoice.Left, pick.left_ref),
        (PickChoice.Right, pick.right_ref),
    ):
        if ref.get("shown_first"):
            return side
    return None


def _check(choice: PickChoice, left: bool | None, right: bool | None):
    """An unacceptable reply never wins; with only one acceptable, it wins;
    with neither, the pick is a tie (R-0640)."""
    if any(value is not None and not isinstance(value, bool) for value in (left, right)):
        raise ValueError("acceptable is true or false")
    for side, acceptable in ((PickChoice.Left, left), (PickChoice.Right, right)):
        if choice is side and acceptable is False:
            raise ValueError("an unacceptable reply cannot win")
    if {left, right} == {True, False}:
        if choice is not (PickChoice.Left if left else PickChoice.Right):
            raise ValueError("the one acceptable reply wins")


@bp.route("/picks/<int:pick_id>", methods=["PUT"])
def pick_put(pick_id: int):
    """The pick, and only then the two model names. A pick made in the chat is
    its owner's, admin or auditor; `shown` is the side on screen first
    (R-0640)."""
    user = coder()
    pick = db.session.get(Pick, pick_id)
    if pick is None:
        abort(404)
    if not user.has_role(btcopilot.ROLE_ADMIN):
        said = adapter.statement(pick.left_ref["said"])
        _owner(user, adapter.discussion_of(said.discussion_id))
    body = request.get_json() or {}
    note = (body.get("note") or "").strip()
    if len(note) > NOTE_CAP:
        raise ValueError(f"a note is at most {NOTE_CAP} characters")
    choice = PickChoice(body.get("choice"))
    left, right = body.get("left_acceptable"), body.get("right_acceptable")
    _check(choice, left, right)
    if body.get("source") is not None:
        if PickSource(body["source"]) is not PickSource.Chat:
            raise ValueError("a pick can only move to the chat")
        pick.source = PickSource.Chat
    if body.get("shown") is not None:
        shown = PickChoice(body["shown"])
        if shown is PickChoice.Tie:
            raise ValueError("shown is left or right")
        pick.left_ref = {**pick.left_ref, "shown_first": shown is PickChoice.Left}
        pick.right_ref = {**pick.right_ref, "shown_first": shown is PickChoice.Right}
    pick.update(
        choice=choice,
        left_acceptable=left,
        right_acceptable=right,
        note=note or None,
        user_id=user.id,
        _commit=True,
    )
    return jsonify(
        {
            "id": pick.id,
            "choice": pick.choice,
            "note": pick.note,
            "left": pick.left_ref["model"],
            "right": pick.right_ref["model"],
        }
    )


@bp.route("/picks")
def pick_index():
    """One coach turn's replies to vote on blind, named by `?turn=`."""
    return _turn(request.args["turn"])
