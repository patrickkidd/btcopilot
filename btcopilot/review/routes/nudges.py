"""The one control that nudges the coders who are not done (R-0258)."""

from flask import jsonify, request

from btcopilot.auth.emails import send_nudge
from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.routes import admin, bp
from btcopilot.review.routes.coders import CoderState, roster, state_of
from btcopilot.review.routes.cuts import table_cuts

#: Who a nudge is for: everyone the meeting is still waiting on.
WAITING = (CoderState.NotStarted, CoderState.Coding)


@bp.route("/nudges", methods=["POST"])
def nudge_create():
    admin()
    body = request.get_json() or {}
    cuts = table_cuts(body.get("meeting_date"))
    if not cuts:
        raise ValueError("nothing is on the table to nudge anyone about")
    behind = [user for user in roster(cuts) if state_of(user, cuts) in WAITING]
    meeting = cuts[0].meeting_date
    when = meeting.strftime("%a %b %-d") if meeting else "the next meeting"
    for user in behind:
        send_nudge(user.username, [_name(cut) for cut in cuts], when)
    nudged_at = adapter.utcnow()
    for cut in cuts:
        cut.nudged_at = nudged_at
    db.session.commit()
    return jsonify(
        {
            "nudged": [user.id for user in behind],
            "nudged_at": nudged_at.isoformat(),
        }
    ), 201


def _name(cut) -> str:
    discussion = adapter.discussion_of(cut.discussion_id)
    return (discussion.title or "").strip() or "an untitled conversation"
