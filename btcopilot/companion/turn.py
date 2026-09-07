"""One coach turn, streamed.

The page posts what the user said and reads the turn as it happens: words as
they are written, the tool calls behind them, the deltas already in the record,
and the views the picture should take. The last event carries the persisted
statement, which is what the page keeps.

The turn runs inside its own application context. A streamed body outlives the
request that started it, and the session the request opened is gone by then, so
the loop re-reads what it needs by id.
"""

import contextlib
import json
import logging

from flask import Response, current_app, has_app_context, request

from btcopilot import auth
from btcopilot.companion.blueprint import bp, current_session, owned_session
from btcopilot.companion.sessions import session_payload
from btcopilot.extensions import db
from btcopilot.personal.coachturn import CoachTurn, EventKind
from btcopilot.personal.models import Discussion
from btcopilot.personal.routes.discussions import _sync_chat_speakers

_log = logging.getLogger(__name__)


def _frame(kind: EventKind, payload: dict) -> str:
    return f"event: {kind.value}\ndata: {json.dumps(payload)}\n\n"


@bp.route("/turn", methods=["POST"])
def turn():
    body = request.get_json()
    unknown = set(body) - {"statement", "session_id"}
    if unknown:
        raise ValueError(f"Unknown turn field(s): {', '.join(sorted(unknown))}")
    discussion = (
        owned_session(body["session_id"])
        if body.get("session_id")
        else current_session(auth.current_user(), create=True)
    )
    db.session.commit()
    app = current_app._get_current_object()
    discussion_id = discussion.id
    statement = body["statement"]

    def stream():
        # A streamed body normally outlives its request and needs a context of
        # its own; a caller that drains it in place already has one.
        with contextlib.nullcontext() if has_app_context() else app.app_context():
            session = db.session.get(Discussion, discussion_id)
            _sync_chat_speakers(session)
            db.session.commit()
            coach = CoachTurn(session, statement, session_id=str(discussion_id))
            for kind, payload in coach.run():
                if kind is EventKind.Statement:
                    payload["session"] = session_payload(session)
                yield _frame(kind, payload)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
