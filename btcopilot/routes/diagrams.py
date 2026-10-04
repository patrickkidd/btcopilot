"""The diagrams a user can open: the ones they own and the ones they have been
granted. One resource per table, so the account page, the settings stack and the
family switcher all read the same list rather than each growing an endpoint of
its own."""

from flask import abort, jsonify, request

import btcopilot
from btcopilot import auth, diagramjson
from btcopilot.licence import require_professional
from btcopilot.routes import Access, access, bp, last_activity, utc_iso
from btcopilot.extensions import db
from btcopilot.models import Discussion
from btcopilot.models import Diagram, User
from btcopilot.models.etc import AccessRight
from btcopilot.routes.users import require_admin

GRANTED = (btcopilot.ACCESS_READ_ONLY, btcopilot.ACCESS_READ_WRITE)


def readable(user) -> list[Diagram]:
    """Owned first, then granted, each once."""
    found = [d for d in user.diagrams if not d.scratch]
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
        "last_activity": utc_iso(when) if when else None,
        "free": diagram.id == user.free_diagram_id,
        "current": diagram.id == user.diagram_in_use(),
        "owned": diagram.user_id == user.id,
        "access": access(diagram, user),
        "owner": diagram.user.full_name().strip() or diagram.user.username,
        # the owner's first name, for the case report's header, never an email
        "owner_name": diagram.user.first_name or None,
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
    """`?user_id=` lists another person's diagrams, which only an admin may
    read; `current` still says which one the caller is on."""
    user = auth.current_user()
    asked = request.args.get("user_id", type=int)
    if asked is None or asked == user.id:
        return jsonify(diagrams_payload(user))
    require_admin()
    here = user.diagram_in_use()
    return jsonify(
        [
            d | {"current": d["id"] == here}
            for d in diagrams_payload(db.get_or_404(User, asked))
        ]
    )


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
    """Put the app on one of the user's writable diagrams, or, for an admin,
    on anyone's to look at: no access right is written for that, and every
    write on it is refused. This never writes free_diagram_id: which diagram
    is free of charge is a billing fact, not a record of where the reader is."""
    user = auth.current_user()
    found = db.get_or_404(Diagram, diagram_id)
    if found not in writable(user) and access(found, user) is not Access.AdminView:
        abort(404)
    user.current_diagram_id = diagram_id
    db.session.commit()
    return jsonify(diagram_payload(found, user))
