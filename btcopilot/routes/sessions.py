"""Sessions are Discussions, and each is one sitting of the family's thread.
The page reads the thread across them from /statements and posts to /chat,
which puts the words in the sitting they belong to."""

from flask import abort, jsonify, request
from sqlalchemy import func, tuple_

import btcopilot
from btcopilot import auth
from btcopilot.routes import (
    bp,
    current_session,
    owned_session,
    require_write_access,
    writable_diagram,
)
from btcopilot.routes.diagrams import readable
from btcopilot.extensions import db
from btcopilot.licence import require_professional
from btcopilot.models import (
    Diagram,
    Discussion,
    DiscussionKind,
    Statement,
    StatementKind,
)
from btcopilot.discussions import (
    all_sessions,
    chats,
    create_discussion,
    listed,
    session_payload,
    sync_chat_speakers,
    utc_iso,
)
from btcopilot import chips, toolnames, turns, turnstore
from btcopilot.toolbox import excerpt, said_in, said_with
from btcopilot.turnlog import TurnEventKind

THREAD_PAGE = 50
# About two lines of a session's row, so the words a search found stay in sight.
MATCH_CUT = 90


def statements_payload(statements: list[Statement], user) -> list[dict]:
    """Each message with the tool calls of its turn: a coach reply carries the
    calls that led to it, and the words of a turn that never answered carry the
    calls it made before it failed, marked unfinished with why it stopped."""
    kept = turnstore.kept({s.turn_id for s in statements if s.turn_id})
    out = []
    for s in statements:
        coach = s.speaker_id == s.discussion.chat_ai_speaker_id
        events = kept.get(s.turn_id, []) if s.turn_id else []
        unfinished = not coach and turnstore.failed(events)
        out.append(
            {
                "id": s.id,
                "session_id": s.discussion_id,
                "role": "coach" if coach else "user",
                "text": s.text,
                "kind": (s.kind or StatementKind.Turn).value,
                "cluster_id": s.cluster_id,
                "case": s.told_case,
                "digest": s.digest,
                "turn_id": s.turn_id,
                "tools": (
                    [
                        {
                            "name": e["name"],
                            "args": e["args"],
                            "names": toolnames.drawn(e),
                            "refusal": e.get("refusal"),
                        }
                        for e in events
                        if e["type"] == TurnEventKind.ToolCall.value
                        and toolnames.shown(e, user)
                    ]
                    if coach or unfinished
                    else []
                ),
                "unfinished": unfinished,
                "failure": (
                    next(
                        e["message"]
                        for e in reversed(events)
                        if e["type"] == TurnEventKind.Failed.value
                    )
                    if unfinished
                    else None
                ),
            }
        )
    return out


def thread(user, before: int | None = None) -> list[dict]:
    """The words of every sitting on the family the app is on, as one thread:
    sittings in the order they started, THREAD_PAGE statements at a time back
    from the statement `before`. A sitting's first words carry the sitting —
    its id, when it started, and when the one before it started — which is
    where the page draws the line between one sitting and the next."""
    at = func.min(Statement.created_at)
    start = (
        db.session.query(
            Statement.discussion_id,
            at.label("at"),
            func.min(Statement.id).label("first"),
            func.lag(at, type_=Statement.created_at.type)
            .over(order_by=(at, Statement.discussion_id))
            .label("previous"),
        )
        .filter(
            Statement.discussion_id.in_(
                chats(user, user.diagram_in_use()).with_entities(Discussion.id)
            )
        )
        .group_by(Statement.discussion_id)
        .subquery()
    )
    key = (start.c.at, Statement.discussion_id, Statement.id)
    found = Statement.query.join(start, start.c.discussion_id == Statement.discussion_id)
    if before is not None:
        edge = found.filter(Statement.id == before).with_entities(*key).one_or_none()
        if edge is None:
            abort(404)
        found = found.filter(tuple_(*key) < tuple_(*edge))
    rows = (
        found.add_columns(start.c.at, start.c.first, start.c.previous)
        .order_by(*(k.desc() for k in key))
        .limit(THREAD_PAGE)
        .all()[::-1]
    )
    out = statements_payload([s for s, *_ in rows], user)
    for said, (s, at, first, previous) in zip(out, rows):
        said["sitting"] = (
            {
                "id": s.discussion_id,
                "started": utc_iso(at),
                "previous_started": utc_iso(previous) if previous else None,
            }
            if s.id == first
            else None
        )
    return out


def _start(discussion: Discussion, statement: str):
    """The words are stored and the turn is handed to the worker, which answers
    at its own pace. The page follows it on /turns/<id>/events; nothing waits
    here, because a turn takes longer than a request may."""
    require_write_access(discussion.diagram)
    sync_chat_speakers(discussion)
    db.session.commit()
    try:
        return jsonify(turns.start(discussion, statement)), 202
    except turns.Busy as busy:
        abort(409, description=str(busy))


def _statement_text() -> str:
    if request.headers.get("Content-Type") != "application/json":
        abort(415, description="Only 'Content-Type: application/json' is supported")
    return request.json["statement"]


@bp.route("/chat", methods=["POST"])
def chat():
    statement = _statement_text()
    return _start(current_session(auth.current_user(), create=True), statement)


@bp.route("/statements")
def statement_index():
    """The thread, a page at a time: `?before=<statement id>` reads the page
    of words just older than that one."""
    return jsonify(thread(auth.current_user(), request.args.get("before", type=int)))


@bp.route("/sessions")
def session_index():
    """`?diagram_id=` lists another readable diagram's sessions, which is what
    the sessions sheet needs to show a professional's families in one scroll.
    A diagram the user cannot read is a 404, never a 403. `?all=true` is
    Patrick's: every session on every family, whoever had it, each with its
    family's name, which is what the meeting page puts one on the agenda from.
    `?words=` keeps the sessions where something said carries every word, the
    coach's own search, each with the newest line that does as `match`, in the
    words a reader sees."""
    user = auth.current_user()
    every = request.args.get("all") == "true"
    asked = request.args.get("diagram_id", type=int)
    if every and not user.has_role(btcopilot.ROLE_ADMIN):
        abort(403)
    if asked is not None and asked not in {d.id for d in readable(user)}:
        abort(404)
    found = all_sessions() if every else chats(user, asked or user.diagram_in_use())
    terms = request.args.get("words", "").split()
    lines = {}
    if terms:
        ids = Discussion.id.in_(found.with_entities(Discussion.id))
        for s in said_with(said_in(ids), terms):
            lines.setdefault(
                s.discussion_id, excerpt(chips.plain(s.text), terms, MATCH_CUT)
            )
        found = found.filter(Discussion.id.in_(list(lines)))
    families = (
        dict(found.join(Diagram).with_entities(Discussion.id, Diagram.name))
        if every
        else {}
    )
    return jsonify(
        [
            one
            | ({"family": families[one["id"]]} if every else {})
            | ({"match": lines[one["id"]]} if terms else {})
            for one in listed(found)
        ]
    )


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
    payload["statements"] = statements_payload(
        discussion.statements, auth.current_user()
    )
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
    return _start(owned_session(session_id), statement)
