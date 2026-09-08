"""The diagrams a user can open: the ones they own and the ones they have been
granted. One resource per table, so the account page, the settings stack and the
family switcher all read the same list rather than each growing an endpoint of
its own."""

from flask import jsonify

import btcopilot
from btcopilot import auth
from btcopilot.companion.blueprint import bp, last_activity
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
        "owned": diagram.user_id == user.id,
    }


def diagrams_payload(user) -> list[dict]:
    """Most recently active first, so the switcher opens on what you were
    last in."""
    payload = [diagram_payload(d, user) for d in readable(user)]
    return sorted(
        payload,
        key=lambda d: (d["last_activity"] or "", d["id"]),
        reverse=True,
    )


@bp.route("/diagrams")
def diagram_index():
    return jsonify(diagrams_payload(auth.current_user()))
