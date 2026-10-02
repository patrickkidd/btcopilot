"""A family's whole thread as the cut-placing screen reads it: every sitting's
lines in one scroll, the sittings to jump between, where the last ratified cut
fell, and where a cut already on the agenda falls (R-0267).

This is the same thread the coding screen shows, read before any coding of it
exists, so it is the family's lines rather than a coding's.
"""

from flask import jsonify, request

from btcopilot.review import adapter
from btcopilot.review.models import Cut
from btcopilot.review.routes import admin, bp, day, sitting_name


@bp.route("/turns")
def turn_index():
    """Placing the cut is Patrick's, so reading a thread whole is too. The
    sitting asked for is the one the screen opens at."""
    admin()
    discussion = adapter.discussion_of(request.args.get("discussion_id", type=int) or 0)
    if discussion is None:
        raise ValueError("no sitting by that id")
    lines = adapter.thread(discussion.diagram_id)
    if not lines:
        raise ValueError("that thread has no turns to cut")
    orders = adapter.statement_order(discussion.diagram_id)
    ratified = _last(discussion.diagram_id, Cut.ratified_at.isnot(None))
    standing = _last(discussion.diagram_id, Cut.ratified_at.is_(None))

    return jsonify(
        {
            "diagram_id": discussion.diagram_id,
            "sitting_id": discussion.id,
            "session": sitting_name(discussion),
            "agreed": _line(ratified, orders),
            "on_agenda": _line(standing, orders),
            "cut_id": standing.id if standing else None,
            "sittings": _sittings(lines),
            "turns": [
                {
                    "id": line.id,
                    "order": orders[line.id],
                    "sitting_id": line.discussion_id,
                    "client": _client(line),
                    "text": line.text or "",
                    "day": day(line.id),
                }
                for line in lines
            ],
        }
    )


def _sittings(lines) -> list[dict]:
    """Each sitting once, in thread order, with when it started and when the
    one before it started, which is what the chat app's divider is drawn from."""
    out: list[dict] = []
    for line in lines:
        if out and out[-1]["id"] == line.discussion_id:
            continue
        started = adapter.utc_iso(line.created_at)
        out.append(
            {
                "id": line.discussion_id,
                "title": (line.discussion.title or "").strip(),
                "started": started,
                "previous_started": out[-1]["started"] if out else None,
                "first_statement_id": line.id,
            }
        )
    return out


def _line(cut: Cut | None, orders: dict[int, int]) -> dict | None:
    if cut is None:
        return None
    return {
        "start_statement_id": cut.start_statement_id,
        "statement_id": cut.end_statement_id,
        "order": orders.get(cut.end_statement_id, 0),
        "day": day(cut.end_statement_id),
        "ratified": (
            cut.ratified_at.strftime("%b %-d") if cut.ratified_at else None
        ),
    }


def _last(diagram_id: int, state) -> Cut | None:
    return (
        Cut.query.filter(Cut.diagram_id == diagram_id, state)
        .order_by(Cut.id.desc())
        .first()
    )


def _client(statement) -> bool:
    speaker = statement.speaker
    return speaker is not None and speaker.type == adapter.SpeakerType.Subject
