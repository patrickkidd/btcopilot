"""Blind pairs: two replies to the same words, shown in a random order with no
model named until Patrick has picked (R-0599). His pick is the only judgement;
no model judges another.

A pair is a shadow turn against the real reply it shadowed, or the same reply
of two replays of one discussion on different models, aligned by turn."""

import enum
import itertools
import json
import random
import string

from flask import abort, jsonify, request

import btcopilot
from btcopilot import ledger
from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Pick, PickChoice, PickSource
from btcopilot.review.models.pick import NOTE_CAP
from btcopilot.review.routes import admin, bp, coder


class Who(enum.StrEnum):
    User = "user"
    Coach = "coach"


def _spoken(discussion, speaker_id: int) -> list:
    return [s for s in adapter.sitting(discussion.id) if s.speaker_id == speaker_id]


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


def _replays():
    path = ledger.PATH
    lines = (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )
    replays = sorted(
        (line for line in lines if line["kind"] == ledger.LedgerKind.Replay),
        key=lambda line: line["discussion_id"],
    )
    for discussion_id, group in itertools.groupby(
        replays, key=lambda line: line["discussion_id"]
    ):
        real = adapter.discussion_of(discussion_id)
        said = _spoken(real, real.chat_user_speaker_id)
        for one, other in itertools.combinations(list(group), 2):
            if one["model"] == other["model"]:
                continue
            ones, others = (
                _spoken(scratch, scratch.chat_ai_speaker_id)
                for scratch in (
                    adapter.discussion_of(one["scratch_discussion_id"]),
                    adapter.discussion_of(other["scratch_discussion_id"]),
                )
            )
            for words, mine, theirs in zip(said, ones, others):
                yield (
                    f"replay:{mine.id}:{theirs.id}",
                    PickSource.Replay,
                    {"model": one["model"], "statement_id": mine.id, "said": words.id},
                    {
                        "model": other["model"],
                        "statement_id": theirs.id,
                        "said": words.id,
                    },
                )


def _text(ref: dict) -> str:
    if "shadow_id" in ref:
        return db.session.get(adapter.ShadowTurn, ref["shadow_id"]).text
    return adapter.statement(ref["statement_id"]).text


def _context(said_id: int) -> list[dict]:
    """The conversation up to and including the words both replies answer."""
    said = adapter.statement(said_id)
    discussion = adapter.discussion_of(said.discussion_id)
    lines = adapter.sitting(discussion.id)
    return [
        {
            "who": (
                Who.Coach if s.speaker_id == discussion.chat_ai_speaker_id else Who.User
            ),
            "text": s.text,
        }
        for s in lines[: lines.index(said) + 1]
    ]


def blind(pick: Pick) -> dict:
    return {
        "id": pick.id,
        "source": pick.source,
        "context": _context(pick.left_ref["said"]),
        "left": pick.left_text,
        "right": pick.right_text,
    }


def _thread(pick: Pick) -> tuple:
    said = adapter.statement(pick.left_ref["said"])
    return (said.discussion_id, said.order or 0, said.id, pick.id)


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


@bp.route("/pairs")
def pair_index():
    """Every pair not yet picked, a conversation at a time in the order it was
    said."""
    admin()
    _serve(itertools.chain(_shadows(), _replays()))
    waiting = sorted(Pick.query.filter(Pick.choice.is_(None)), key=_thread)
    return jsonify([blind(pick) for pick in waiting])


def _owner(user, discussion):
    if discussion.user_id != user.id:
        abort(403)


def _ref_key(ref: dict) -> tuple:
    if "shadow_id" in ref:
        return ("shadow", ref["shadow_id"])
    return ("statement", ref["statement_id"])


def _turn(turn_id: str):
    """One coach turn's replies keyed a, b, c in a random order, the real one
    among them, and a pick for each shadow against the real reply (R-0636).
    No model is named."""
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
    real = next((ref for ref in keys if ref[0] == "statement"), None)
    return jsonify(
        {
            "replies": [{"key": keys[ref], "text": refs[ref]} for ref in order],
            "real_key": keys.get(real),
            "picks": [
                {
                    "id": pick.id,
                    "left_key": keys[_ref_key(pick.left_ref)],
                    "right_key": keys[_ref_key(pick.right_ref)],
                }
                for pick in picks
            ],
        }
    )


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
    its owner's, admin or auditor (R-0640)."""
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
    pick.choice = choice
    pick.left_acceptable = left
    pick.right_acceptable = right
    pick.note = note or None
    pick.user_id = user.id
    db.session.commit()
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
    """Each model's picks: how often its reply won, lost or tied; or, with
    `?turn=`, one coach turn's replies to vote on blind."""
    if "turn" in request.args:
        return _turn(request.args["turn"])
    admin()
    tally: dict[str, dict] = {}
    for pick in Pick.query.filter(Pick.choice.isnot(None)):
        for side, ref in (
            (PickChoice.Left, pick.left_ref),
            (PickChoice.Right, pick.right_ref),
        ):
            row = tally.setdefault(
                ref["model"], {"model": ref["model"], "won": 0, "lost": 0, "tied": 0}
            )
            if pick.choice is PickChoice.Tie:
                row["tied"] += 1
            elif pick.choice is side:
                row["won"] += 1
            else:
                row["lost"] += 1
    return jsonify(sorted(tally.values(), key=lambda row: row["model"]))
