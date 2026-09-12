"""Sessions are Discussions. One list, one resource per session, and one way
to add a statement to a session — the /chat form posts into whichever session
the user last spoke in."""

from flask import abort, jsonify, request

from btcopilot import auth
from btcopilot.personal.routes import (
    bp,
    current_session,
    last_activity,
    owned_session,
    require_write_access,
    user_sessions,
    writable_diagram,
)
from btcopilot.personal.routes.diagrams import readable
from btcopilot.extensions import db
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.licence import require_professional
from btcopilot.personal.models import Discussion, DiscussionKind, StatementKind
from btcopilot.personal.discussions import (
    create_discussion,
    sync_chat_speakers,
)


def session_payload(discussion: Discussion) -> dict:
    return {
        "id": discussion.id,
        "title": discussion.title,
        "summary": discussion.summary,
        "title_set_by_user": discussion.title_set_by_user,
        "last_activity": last_activity(discussion).isoformat(),
        "message_count": len(discussion.statements),
        "kind": DiscussionKind(discussion.kind).value,
        "date": (
            discussion.discussion_date.isoformat()
            if discussion.discussion_date
            else None
        ),
    }


def statements_payload(discussion: Discussion) -> list[dict]:
    return [
        {
            "id": s.id,
            "role": (
                "coach" if s.speaker_id == discussion.chat_ai_speaker_id else "user"
            ),
            "text": s.text,
            "kind": (s.kind or StatementKind.Turn).value,
            "cluster_id": s.cluster_id,
        }
        for s in discussion.statements
    ]


def _reply(discussion: Discussion, statement: str) -> dict:
    """One agent-loop turn. The words carry their own chips; `events` carries
    what the coach did behind them, in the order it happened, so the page can
    move the picture and the list from the same reply."""
    require_write_access(discussion.diagram)
    sync_chat_speakers(discussion)
    db.session.commit()
    reply = CoachTurn(discussion, statement, session_id=str(discussion.id)).run()
    reply["kind"] = StatementKind.Turn.value
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
    return jsonify([session_payload(d) for d in user_sessions(user, asked)])


@bp.route("/sessions", methods=["POST"])
def session_create():
    """A new session belongs to the diagram the app is on, not to whichever one
    happens to be free. A note is a session of its own, which only a
    professional starts (R-0281); a recording arrives by its own route because
    it carries a transcript with it."""
    body = request.get_json(silent=True) or {}
    unknown = set(body) - {"kind"}
    if unknown:
        raise ValueError(f"Unknown session field(s): {', '.join(sorted(unknown))}")
    kind = DiscussionKind(body.get("kind", DiscussionKind.Chat))
    if kind is DiscussionKind.Recording:
        raise ValueError("A recording is created from its transcript")
    if kind is DiscussionKind.Note:
        require_professional()
    made = create_discussion({}, writable_diagram())
    made.kind = kind
    db.session.commit()
    return jsonify(session_payload(made)), 201


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


@bp.route("/sessions/<int:session_id>", methods=["DELETE"])
def session_delete(session_id: int):
    """A session goes; the record it coded stays. What the coach wrote into the
    diagram is the record's, not the conversation's."""
    discussion = owned_session(session_id)
    discussion.chat_user_speaker_id = None
    discussion.chat_ai_speaker_id = None
    db.session.flush()
    db.session.delete(discussion)
    db.session.commit()
    return "", 204


@bp.route("/sessions/<int:session_id>/statements", methods=["POST"])
def add_statement(session_id: int):
    statement = _statement_text()
    return jsonify(_reply(owned_session(session_id), statement))
