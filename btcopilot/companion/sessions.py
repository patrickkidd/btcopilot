"""Sessions are Discussions. One list, one resource per session, and one way
to add a statement to a session — the /chat form posts into whichever session
the user last spoke in."""

from flask import abort, jsonify, request

from btcopilot import auth
from btcopilot.companion.blueprint import (
    bp,
    current_session,
    last_activity,
    owned_session,
    sessions,
)
from btcopilot.companion.diagrams import readable
from btcopilot.extensions import db
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import Discussion
from btcopilot.personal.routes.discussions import (
    _create_discussion,
    _sync_chat_speakers,
)


def session_payload(discussion: Discussion) -> dict:
    return {
        "id": discussion.id,
        "title": discussion.title,
        "summary": discussion.summary,
        "title_set_by_user": discussion.title_set_by_user,
        "last_activity": last_activity(discussion).isoformat(),
        "message_count": len(discussion.statements),
    }


def statements_payload(discussion: Discussion) -> list[dict]:
    return [
        {
            "id": s.id,
            "role": (
                "coach" if s.speaker_id == discussion.chat_ai_speaker_id else "user"
            ),
            "text": s.text,
        }
        for s in discussion.statements
    ]


def _reply(discussion: Discussion, statement: str) -> dict:
    """One agent-loop turn. The words carry their own chips; `events` carries
    what the coach did behind them, in the order it happened, so the page can
    move the picture and the list from the same reply."""
    _sync_chat_speakers(discussion)
    db.session.commit()
    reply = CoachTurn(discussion, statement, session_id=str(discussion.id)).run()
    reply["discussion_id"] = discussion.id
    reply["session"] = session_payload(discussion)
    return reply


def _statement_text() -> str:
    if request.headers.get("Content-Type") != "application/json":
        abort(415, description="Only 'Content-Type: application/json' is supported")
    return request.json["statement"]


@bp.route("/chat", methods=["POST"])
def chat():
    statement = _statement_text()
    return jsonify(_reply(current_session(auth.current_user(), create=True), statement))


@bp.route("/sessions")
def session_index():
    """`?diagram_id=` lists another readable diagram's sessions, which is what
    the sessions sheet needs to show a professional's families in one scroll.
    A diagram the user cannot read is a 404, never a 403."""
    user = auth.current_user()
    asked = request.args.get("diagram_id", type=int)
    if asked is not None and asked not in {d.id for d in readable(user)}:
        abort(404)
    return jsonify([session_payload(d) for d in sessions(user, asked)])


@bp.route("/sessions", methods=["POST"])
def session_create():
    return jsonify(session_payload(_create_discussion({}))), 201


@bp.route("/sessions/<int:session_id>")
def session_get(session_id: int):
    discussion = owned_session(session_id)
    payload = session_payload(discussion)
    payload["statements"] = statements_payload(discussion)
    return jsonify(payload)


@bp.route("/sessions/<int:session_id>", methods=["PATCH"])
def session_rename(session_id: int):
    discussion = owned_session(session_id)
    body = request.get_json()
    unknown = set(body) - {"title"}
    if unknown:
        raise ValueError(f"Unknown session field(s): {', '.join(sorted(unknown))}")
    title = body["title"].strip()
    if not title:
        raise ValueError("A session title cannot be empty")
    discussion.title = title
    discussion.title_set_by_user = True
    db.session.commit()
    return jsonify(session_payload(discussion))


@bp.route("/sessions/<int:session_id>/statements", methods=["POST"])
def add_statement(session_id: int):
    statement = _statement_text()
    return jsonify(_reply(owned_session(session_id), statement))
