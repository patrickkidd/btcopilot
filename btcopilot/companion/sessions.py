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
from btcopilot.companion.timeline import aimable
from btcopilot.extensions import db
from btcopilot.personal.chat import Response, ask
from btcopilot.personal.models import Discussion
from btcopilot.personal.refs import resolve
from btcopilot.personal.routes.discussions import (
    _create_discussion,
    _sync_chat_speakers,
)
from btcopilot.schema import DiagramData, asdict


def session_payload(discussion: Discussion) -> dict:
    return {
        "id": discussion.id,
        "title": discussion.title,
        "summary": discussion.summary,
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
    _sync_chat_speakers(discussion)
    response: Response = ask(discussion, statement)
    if discussion.title is None:
        discussion.update_title()
        discussion.update_summary()
    db.session.commit()
    data = (
        discussion.diagram.get_diagram_data() if discussion.diagram else DiagramData()
    )
    return {
        "statement": response.statement,
        "refs": [asdict(ref) for ref in aimable(resolve(response.refs, data), data)],
        "discussion_id": discussion.id,
        "session": session_payload(discussion),
    }


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
    return jsonify([session_payload(d) for d in sessions(auth.current_user())])


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
    db.session.commit()
    return jsonify(session_payload(discussion))


@bp.route("/sessions/<int:session_id>/statements", methods=["POST"])
def add_statement(session_id: int):
    statement = _statement_text()
    return jsonify(_reply(owned_session(session_id), statement))
