"""The diagrams a user can open: the ones they own and the ones they have been
granted. One resource per table, so the account page, the settings stack and the
family switcher all read the same list rather than each growing an endpoint of
its own."""

from flask import abort, jsonify, request

import btcopilot
from btcopilot import auth, diagramjson
from btcopilot.personal.licence import require_professional
from btcopilot.personal.routes import bp, last_activity
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.pro.models import Diagram
from btcopilot.pro.models.etc import AccessRight

GRANTED = (btcopilot.ACCESS_READ_ONLY, btcopilot.ACCESS_READ_WRITE)


def readable(user) -> list[Diagram]:
    """Owned first, then granted, each once."""
    found = list(user.diagrams)
    seen = {d.id for d in found}
    granted = (
        Diagram.query.join(AccessRight, AccessRight.diagram_id == Diagram.id)
        .filter(AccessRight.user_id == user.id, AccessRight.right.in_(GRANTED))
        .all()
    )
    found += [d for d in granted if d.id not in seen]
    return found


def writable(user) -> list[Diagram]:
    """The diagrams the user may put the app on: owned, or granted read-write.
    A diagram shared read-only is readable but never lands here — the switcher
    and the writing routes both key off this same check."""
    return [d for d in readable(user) if d.check_write_access(user)]


def diagram_payload(diagram: Diagram, user) -> dict:
    """A diagram as the switcher and the settings list need it: what it is
    called, how much has been said on it, and when that last happened."""
    discussions = Discussion.query.filter_by(
        diagram_id=diagram.id, user_id=user.id
    ).all()
    latest = max((last_activity(d) for d in discussions), default=None)
    saved = diagram.saved_at()
    when = max(filter(None, (latest, saved)), default=None)
    return {
        "id": diagram.id,
        "name": diagram.name,
        "session_count": len(discussions),
        "last_activity": when.isoformat() if when else None,
        "free": diagram.id == user.free_diagram_id,
        "current": diagram.id == user.diagram_in_use(),
        "owned": diagram.user_id == user.id,
    }


def diagrams_payload(user) -> list[dict]:
    """Most recently active first, so the switcher opens on what you were
    last in. Only the diagrams the user may write to — this is the switcher's
    list, and a diagram shared read-only is never a place the app can be put."""
    payload = [diagram_payload(d, user) for d in writable(user)]
    return sorted(
        payload,
        key=lambda d: (d["last_activity"] or "", d["id"]),
        reverse=True,
    )


@bp.route("/diagrams")
def diagram_index():
    return jsonify(diagrams_payload(auth.current_user()))


@bp.route("/diagrams", methods=["POST"])
def diagram_create():
    """A new case: an empty record the app is put on straight away, so the
    title row names it before anything is said into it. Only a professional
    keeps several records, so only a professional can make one (R-0285)."""
    require_professional()
    user = auth.current_user()
    name = (request.get_json().get("name") or "").strip()
    if not name:
        raise ValueError("A case needs a name")
    made = Diagram(user_id=user.id, name=name, data=diagramjson.dumps({}))
    db.session.add(made)
    db.session.flush()
    user.current_diagram_id = made.id
    db.session.commit()
    return jsonify(diagram_payload(made, user)), 201


@bp.route("/diagrams/<int:diagram_id>/select", methods=["POST"])
def diagram_select(diagram_id: int):
    """Put the app on one of the user's writable diagrams. This never writes
    free_diagram_id: which diagram is free of charge is a billing fact, not a
    record of where the reader is."""
    user = auth.current_user()
    if diagram_id not in {d.id for d in writable(user)}:
        abort(404)
    user.current_diagram_id = diagram_id
    db.session.commit()
    return jsonify(diagram_payload(next(d for d in writable(user) if d.id == diagram_id), user))
