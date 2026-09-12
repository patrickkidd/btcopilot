"""The one thing a coder is doing now, and what they have already finished.

Never a list to choose from (R-0265): one card, one button, and under it the
tasks that are done. What to code comes from what Patrick put on the table.
"""

import datetime

from flask import jsonify

from btcopilot.review import adapter
from btcopilot.review.models import Coding, Cut, Vote
from btcopilot.review.routes import bp, coder, my_coding

#: Roughly how long one turn takes to code, for the card's estimate.
MINUTES_PER_TURN = 0.8
ROUND_TO = 5


@bp.route("/tasks")
def task_index():
    """The card on top, and the finished tasks under it."""
    user = coder()
    return jsonify(
        {
            "task": _task(user),
            "done": [_finished(c) for c in _my_finished(user)],
        }
    )


def _task(user) -> dict | None:
    for cut in Cut.query.filter(Cut.ratified_at.is_(None)).order_by(Cut.id).all():
        mine = my_coding(cut, user)
        if cut.vote_opened_at is None:
            if mine is None or mine.done_at is None:
                return _to_code(cut, mine, user)
            return _to_vote(cut, mine, ready=False)
        if mine is not None and mine.done_at is not None and not _voted(cut, user):
            return _to_vote(cut, mine, ready=True)
    return None


def _to_code(cut: Cut, mine: Coding | None, user) -> dict:
    turns = adapter.statements_between(
        cut.discussion_id, cut.start_statement_id, cut.end_statement_id
    )
    return {
        "kind": "code",
        "cut_id": cut.id,
        "coding_id": mine.id if mine else None,
        "meeting_date": _iso(cut.meeting_date),
        "title": f"Code {_session_name(cut)} up to {_cut_day(cut)}",
        "detail": _since(cut, turns, user),
        "ready": True,
    }


def _to_vote(cut: Cut, mine: Coding, ready: bool) -> dict:
    waiting = "opens when Patrick opens the vote"
    return {
        "kind": "vote",
        "cut_id": cut.id,
        "coding_id": mine.id,
        "meeting_date": _iso(cut.meeting_date),
        "title": f"Vote on the disputed events of {_session_name(cut)}",
        "detail": "about 10 min" if ready else f"{waiting} · about 10 min",
        "ready": ready,
    }


def _since(cut: Cut, turns, user) -> str:
    """How much is new, and how long it will take."""
    orders = [t.order or 0 for t in turns]
    span = (
        f"turns {min(orders)} to {max(orders)} are new"
        if orders
        else "nothing new yet"
    )
    last = _last_done(cut.discussion_id, user)
    when = f" since you pressed Done on {_day(last.done_at)}" if last else ""
    minutes = max(
        ROUND_TO, round(len(turns) * MINUTES_PER_TURN / ROUND_TO) * ROUND_TO
    )
    return f"{span}{when} · about {minutes} min"


def _last_done(discussion_id: int, user) -> Coding | None:
    return (
        Coding.query.join(Cut, Coding.cut_id == Cut.id)
        .filter(
            Coding.user_id == user.id,
            Coding.done_at.isnot(None),
            Cut.discussion_id == discussion_id,
        )
        .order_by(Coding.done_at.desc())
        .first()
    )


def _my_finished(user) -> list[Coding]:
    return (
        Coding.query.filter(
            Coding.user_id == user.id, Coding.done_at.isnot(None)
        )
        .order_by(Coding.done_at.desc())
        .all()
    )


def _finished(coding: Coding) -> dict:
    cut = coding.cut
    ratified = cut.ratified_at
    return {
        "coding_id": coding.id,
        "cut_id": cut.id,
        "title": f"{_session_name(cut)} up to {_cut_day(cut)}",
        "detail": (
            f"ratified {_day(ratified)}" if ratified else f"done {_day(coding.done_at)}"
        ),
    }


def _voted(cut: Cut, user) -> bool:
    item_ids = [item.id for item in cut.items]
    if not item_ids:
        return False
    open_items = Vote.query.filter(
        Vote.review_item_id.in_(item_ids), Vote.user_id == user.id
    ).count()
    return open_items >= len(item_ids)


def _session_name(cut: Cut) -> str:
    discussion = adapter.discussion_of(cut.discussion_id)
    return (discussion.title or "").strip() or "an untitled conversation"


def _cut_day(cut: Cut) -> str:
    return _day(adapter.cut_day(cut.discussion_id, cut.end_statement_id))


def _day(when) -> str:
    if when is None:
        return "an unknown day"
    return when.strftime("%b %-d")


def _iso(value: datetime.date | None) -> str | None:
    return value.isoformat() if value else None
