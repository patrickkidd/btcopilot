"""One session's turns as the cut-placing screen reads them: the whole
conversation, where the last ratified cut fell, and where a cut already on the
table falls (R-0267).

This is the same thread the coding screen shows, read before any coding of it
exists, so it is the session's turns rather than a coding's.
"""

from flask import jsonify, request

from btcopilot.review import adapter
from btcopilot.review.models import Cut
from btcopilot.review.routes import admin, bp


@bp.route("/turns")
def turn_index():
    """Placing the cut is Patrick's, so reading a session whole is too."""
    admin()
    discussion_id = request.args.get("discussion_id", type=int)
    if not discussion_id:
        raise ValueError("say which session's turns")
    discussion = adapter.discussion_of(discussion_id)
    if discussion is None:
        raise ValueError("no session by that id")
    first = adapter.first_statement(discussion_id)
    last = adapter.last_statement(discussion_id)
    if first is None or last is None:
        raise ValueError("that session has no turns to cut")
    ratified = _last_ratified(discussion_id)
    standing = _on_table(discussion_id)

    return jsonify(
        {
            "discussion_id": discussion_id,
            "session": (discussion.title or "").strip()
            or "an untitled conversation",
            "agreed": _line(ratified),
            "on_table": _line(standing),
            "cut_id": standing.id if standing else None,
            "turns": [
                {
                    "id": turn.id,
                    "order": turn.order or 0,
                    "client": _client(turn),
                    "text": turn.text or "",
                    "day": _day(discussion_id, turn.id),
                }
                for turn in adapter.statements_between(
                    discussion_id, first.id, last.id
                )
            ],
        }
    )


def _line(cut: Cut | None) -> dict | None:
    if cut is None:
        return None
    end = adapter.statement(cut.end_statement_id)
    return {
        "statement_id": cut.end_statement_id,
        "order": (end.order or 0) if end else 0,
        "day": _day(cut.discussion_id, cut.end_statement_id),
        "ratified": (
            cut.ratified_at.strftime("%b %-d") if cut.ratified_at else None
        ),
    }


def _last_ratified(discussion_id: int) -> Cut | None:
    return (
        Cut.query.filter(
            Cut.discussion_id == discussion_id, Cut.ratified_at.isnot(None)
        )
        .order_by(Cut.id.desc())
        .first()
    )


def _on_table(discussion_id: int) -> Cut | None:
    return (
        Cut.query.filter(
            Cut.discussion_id == discussion_id, Cut.ratified_at.is_(None)
        )
        .order_by(Cut.id.desc())
        .first()
    )


def _client(statement) -> bool:
    speaker = statement.speaker
    return speaker is not None and speaker.type == adapter.SpeakerType.Subject


def _day(discussion_id: int, statement_id: int) -> str:
    when = adapter.cut_day(discussion_id, statement_id)
    return when.strftime("%b %-d") if when else "an unknown day"
