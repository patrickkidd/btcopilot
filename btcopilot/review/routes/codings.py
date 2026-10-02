"""Codings: one coder's reading of one cut, on their own record of the case."""

from flask import abort, jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, scribe, snapshot
from btcopilot.review.models import Coding, Cut, Note
from btcopilot.review.routes import (
    bp,
    coder,
    cut_or_404,
    day,
    my_coding,
    sees_others,
    session_name,
)


def payload(coding: Coding) -> dict:
    return coding.as_dict()


def blind_payload(coding: Coding) -> dict:
    """Who coded it is not shown while people are voting (R-0272)."""
    data = coding.as_dict()
    data.pop("user_id", None)
    return data


@bp.route("/codings")
def coding_index():
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not sees_others(cut, user):
        mine = my_coding(cut, user)
        return jsonify([payload(mine)] if mine else [])
    ratified = cut.ratified_at is not None
    shape = payload if ratified else blind_payload
    return jsonify([shape(c) for c in sorted(cut.codings, key=lambda c: c.id)])


@bp.route("/codings", methods=["POST"])
def coding_create():
    user = coder()
    body = request.get_json() or {}
    cut = cut_or_404(body.get("cut_id") or 0)
    existing = my_coding(cut, user)
    if existing is not None:
        return jsonify(payload(existing)), 200

    coding = Coding(
        cut_id=cut.id,
        user_id=user.id,
        diagram_id=_diagram_for(user, cut).id,
    )
    db.session.add(coding)
    db.session.commit()
    return jsonify(payload(coding)), 201


@bp.route("/codings/<int:coding_id>", methods=["PATCH"])
def coding_patch(coding_id: int):
    user = coder()
    coding = db.session.get(Coding, coding_id)
    if coding is None or coding.user_id != user.id:
        return "no coding of yours by that id", 404
    body = request.get_json() or {}

    if body.get("done_at"):
        if coding.done_at is None:
            coding.done_at = adapter.utcnow()
        if coding.cut.vote_opened_at is not None:
            snapshot.recompute(coding.cut)

    db.session.commit()
    return jsonify(payload(coding))


def _diagram_for(user, cut: Cut):
    """The coder's own record of this case: the one they built coding it last
    time, carried forward, or a fresh empty one (R-0267)."""
    case = adapter.diagram_of(cut.diagram_id)
    previous = _previous_coding(user, case.id, cut.id)
    if previous is not None:
        return db.session.get(adapter.Diagram, previous.diagram_id)
    diagram = adapter.coding_diagram(user, f"coding of {case.name or case.id}")
    adapter.grant_write(diagram, user)
    db.session.flush()
    return diagram


def _previous_coding(user, case_diagram_id: int, cut_id: int) -> Coding | None:
    found = (
        Coding.query.join(Cut, Coding.cut_id == Cut.id)
        .filter(
            Coding.user_id == user.id,
            Coding.cut_id != cut_id,
            Cut.diagram_id == case_diagram_id,
        )
        .order_by(Coding.id.desc())
        .first()
    )
    return found


@bp.route("/codings/<int:coding_id>/thread")
def coding_thread(coding_id: int):
    """The conversation this coding is of: every turn from the thread's first
    up to the cut, what this coder has already written from each, and the two
    lines across the thread — the last ratified cut and this one (R-0267)."""
    coding = _mine_or_404(coding_id)
    cut = coding.cut
    orders = adapter.statement_order(cut.diagram_id)
    turns = adapter.statements_between(
        cut.diagram_id, adapter.first_statement(cut.diagram_id).id, cut.end_statement_id
    )
    agreed = _last_ratified(cut)
    agreed_order = orders[agreed.end_statement_id] if agreed else None
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    said = _said_by_turn(coding.id, coding.diagram_id, data)

    return jsonify(
        {
            "coding_id": coding.id,
            "cut_id": cut.id,
            "diagram_id": coding.diagram_id,
            "done_at": coding.done_at.isoformat() if coding.done_at else None,
            "meeting_date": (
                cut.meeting_date.isoformat() if cut.meeting_date else None
            ),
            "session": session_name(cut),
            "cut_day": day(cut.end_statement_id),
            "agreed": (
                {
                    "order": agreed_order,
                    "day": day(agreed.end_statement_id),
                    "ratified": agreed.ratified_at.strftime("%b %-d"),
                }
                if agreed
                else None
            ),
            "turns": [
                {
                    "id": turn.id,
                    "order": orders[turn.id],
                    "who": _who(turn),
                    "client": _client(turn),
                    "text": turn.text or "",
                    "said": said.get(turn.id, []),
                    "above": agreed_order is not None
                    and orders[turn.id] <= agreed_order,
                }
                for turn in turns
            ],
        }
    )


@bp.route("/codings/<int:coding_id>/scribe", methods=["POST"])
def coding_scribe(coding_id: int):
    """What the coder says one turn tells them happened, written into their own
    record by the scribe (R-0270)."""
    coding = _mine_or_404(coding_id)
    if coding.done_at is not None:
        raise ValueError("that coding is finished and cannot be added to")
    body = request.get_json() or {}
    said = (body.get("text") or "").strip()
    if not said:
        raise ValueError("say what the turn tells you happened")
    statement = adapter.statement(body.get("statement_id") or 0)
    if statement is None or statement.discussion.diagram_id != coding.cut.diagram_id:
        raise ValueError("that turn is not part of this conversation")
    if not _in_cut(coding.cut, statement):
        raise ValueError("coding happens between the last agreed line and the cut")

    written = scribe.write(coding, statement, said)
    # Save what the coder typed too, attached to the line they coded (R-0270).
    db.session.add(
        Note(
            coding_id=coding.id,
            statement_id=statement.id,
            text=said,
            turn_id=written["turn_id"],
        )
    )
    db.session.commit()
    return jsonify(written)


def _mine_or_404(coding_id: int) -> Coding:
    user = coder()
    coding = db.session.get(Coding, coding_id)
    if coding is None or coding.user_id != user.id:
        abort(404)
    return coding


def _in_cut(cut: Cut, statement) -> bool:
    orders = adapter.statement_order(cut.diagram_id)
    start = orders.get(cut.start_statement_id)
    end = orders.get(cut.end_statement_id)
    here = orders.get(statement.id)
    return None not in (start, end, here) and start <= here <= end


def _last_ratified(cut: Cut) -> Cut | None:
    return (
        Cut.query.filter(
            Cut.diagram_id == cut.diagram_id,
            Cut.id != cut.id,
            Cut.ratified_at.isnot(None),
        )
        .order_by(Cut.id.desc())
        .first()
    )


def _said_by_turn(
    coding_id: int, diagram_id: int, data: dict
) -> dict[int, list[dict]]:
    """What this coder typed about each turn, oldest first, each with the lines
    the scribe wrote from those words, in the record's own words so a later
    correction to an event still reads as the record has it (R-0270), and the
    events those lines are, whose codes' concept pages hang under them
    (R-0541)."""
    by_scribe_turn = _events_by_scribe_turn(diagram_id)
    by_turn: dict[int, list[dict]] = {}
    notes = Note.query.filter(Note.coding_id == coding_id).order_by(Note.id.asc())
    for note in notes:
        event_ids = by_scribe_turn.get(note.turn_id, [])
        by_turn.setdefault(note.statement_id, []).append(
            {
                "text": note.text,
                "lines": scribe.written(data, event_ids),
                "event_ids": event_ids,
            }
        )
    return by_turn


def _events_by_scribe_turn(diagram_id: int) -> dict[str, list[int]]:
    by_turn: dict[str, list[int]] = {}
    for event_id, where in adapter.coded_in(diagram_id).items():
        turn_id = where.get("turn_id")
        if turn_id is not None:
            by_turn.setdefault(turn_id, []).append(event_id)
    return by_turn


def _who(statement) -> str:
    speaker = statement.speaker
    return (speaker.name if speaker and speaker.name else None) or "Someone"


def _client(statement) -> bool:
    """The client's turns read as the user's bubbles, the clinician's as the
    coach's, so a coded thread looks like any chat."""
    speaker = statement.speaker
    return speaker is not None and speaker.type == adapter.SpeakerType.Subject

