"""The next meeting's agenda, derived and never stored: the rules somebody
flagged, and nothing else (R-0276, R-0308). An event the room left unresolved
stays unresolved as data and is never brought back to a later meeting
(R-0312). Who has not finished a coding is the coder list's own line.
"""

from flask import jsonify, request

from btcopilot.review.models import Cut, Rule
from btcopilot.review.routes import bp, coder
from btcopilot.review.routes.rules import payload as rule_payload


@bp.route("/agenda")
def agenda_read():
    coder()
    meeting_date = request.args.get("meeting_date")
    cuts = _cuts(meeting_date)
    flagged = [
        r
        for r in Rule.query.filter(Rule.retired_at.is_(None)).all()
        if r.open_flags()
    ]

    return jsonify(
        {
            "meeting_date": meeting_date,
            "cut_ids": [c.id for c in cuts],
            "flagged_rules": [rule_payload(r) for r in flagged],
        }
    )


def _cuts(meeting_date: str | None) -> list[Cut]:
    """The cuts of the meeting asked for, or every cut not yet ratified."""
    if meeting_date:
        return Cut.query.filter_by(meeting_date=meeting_date).all()
    return Cut.query.filter(Cut.ratified_at.is_(None)).all()
