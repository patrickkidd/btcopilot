"""Following a running turn.

The page attaches here after it sends a message, and again whenever it comes
back — a reload, or the phone returning to the app. It says where it got to
with Last-Event-ID and is given everything since, then the rest as it happens.
"""

import json

from flask import Response, abort, request, stream_with_context

from btcopilot import auth
from btcopilot.extensions import db
from btcopilot import turnlog
from btcopilot.models import Discussion
from btcopilot.routes import bp

HEARTBEAT_TICKS = 15


def _mine(turn_id: str) -> None:
    """A turn belongs to the session it was started on; anyone else asking for
    it is told there is no such turn, the way a session they do not own is."""
    session_id = turnlog.owner(turn_id)
    if session_id is None:
        abort(404)
    discussion = db.session.get(Discussion, session_id)
    if discussion is None or discussion.user_id != auth.current_user().id:
        abort(404)


def _frame(seq: int, event: dict) -> str:
    return f"id: {seq}\ndata: {json.dumps(event)}\n\n"


@bp.route("/turns/<turn_id>/events")
def turn_events(turn_id: str):
    _mine(turn_id)
    last = request.headers.get("Last-Event-ID", type=int) or 0

    def stream():
        # Listening starts before the replay so an event landing between the
        # two is not lost; anything already replayed is skipped by sequence.
        following = turnlog.subscribe(turn_id)
        sent = last
        for seq, event in turnlog.read_from(turn_id, last):
            sent = seq
            yield _frame(seq, event)
            if turnlog.ended(event):
                return
        quiet = 0
        for carried in following:
            if carried is None:
                quiet += 1
                if quiet >= HEARTBEAT_TICKS:
                    quiet = 0
                    yield ": still here\n\n"
                continue
            quiet = 0
            seq, event = carried
            if seq <= sent:
                continue
            sent = seq
            yield _frame(seq, event)
            if turnlog.ended(event):
                return

    response = Response(stream_with_context(stream()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
