"""Blind pairs: two replies to the same words, shown in a random order with no
model named until Patrick has picked (R-0598). His pick is the only judgement;
no model judges another.

A pair is a shadow turn against the real reply it shadowed, or the same reply
of two replays of one discussion on different models, aligned by turn."""

import enum
import itertools
import json
import random

from flask import abort, jsonify, request

from btcopilot import ledger
from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Pick, PickChoice, PickSource
from btcopilot.review.models.pick import NOTE_CAP
from btcopilot.review.routes import admin, bp


class Who(enum.StrEnum):
    User = "user"
    Coach = "coach"


def _said(discussion_id: int) -> list:
    first = adapter.first_statement(discussion_id)
    if first is None:
        return []
    last = adapter.last_statement(discussion_id)
    return adapter.statements_between(discussion_id, first.id, last.id)


def _spoken(discussion, speaker_id: int) -> list:
    return [s for s in _said(discussion.id) if s.speaker_id == speaker_id]


def _shadows():
    rows = adapter.ShadowTurn.query.filter(
        adapter.ShadowTurn.text.isnot(None), adapter.ShadowTurn.error.is_(None)
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
    first = adapter.first_statement(discussion.id)
    return [
        {
            "who": (
                Who.Coach if s.speaker_id == discussion.chat_ai_speaker_id else Who.User
            ),
            "text": s.text,
        }
        for s in adapter.statements_between(discussion.id, first.id, said.id)
    ]


def blind(pick: Pick) -> dict:
    return {
        "id": pick.id,
        "source": pick.source,
        "context": _context(pick.left_ref["said"]),
        "left": _text(pick.left_ref),
        "right": _text(pick.right_ref),
    }


@bp.route("/pairs")
def pair_index():
    """Every pair not yet picked. A pair seen for the first time gets its side
    order here, at random, and keeps it."""
    admin()
    served = {pair for (pair,) in db.session.query(Pick.pair)}
    for pair, source, one, other in itertools.chain(_shadows(), _replays()):
        if pair in served:
            continue
        left, right = (one, other) if random.random() < 0.5 else (other, one)
        db.session.add(Pick(pair=pair, source=source, left_ref=left, right_ref=right))
    db.session.commit()
    waiting = Pick.query.filter(Pick.choice.is_(None)).order_by(Pick.id)
    return jsonify([blind(pick) for pick in waiting])


@bp.route("/picks/<int:pick_id>", methods=["PUT"])
def pick_put(pick_id: int):
    """The pick, and only then the two model names."""
    user = admin()
    pick = db.session.get(Pick, pick_id)
    if pick is None:
        abort(404)
    body = request.get_json() or {}
    note = (body.get("note") or "").strip()
    if len(note) > NOTE_CAP:
        raise ValueError(f"a note is at most {NOTE_CAP} characters")
    pick.choice = PickChoice(body.get("choice"))
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
    """Each model's picks: how often its reply won, lost or tied."""
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
