"""The diagrams a user can open: the ones they own and the ones they have been
granted. One resource per table, so the account page, the settings stack and the
family switcher all read the same list rather than each growing an endpoint of
its own."""

import datetime
import uuid

from flask import abort, jsonify, request

import btcopilot
from btcopilot import attachments, auth, diagramjson, fdafter, fdimport, profile, record
from btcopilot.routes import Access, access, bp, last_activity, utc_iso
from btcopilot.extensions import db
from btcopilot.models import Discussion
from btcopilot.models import Author, Diagram, User
from btcopilot.models.diagram import owner_row
from btcopilot.models.etc import AccessRight
from btcopilot.profile import FIRST_PERSON_ID
from btcopilot.routes.users import require_admin

GRANTED = (btcopilot.ACCESS_READ_ONLY, btcopilot.ACCESS_READ_WRITE)
PERSONAL = "Your personal diagram cannot be deleted."
NOT_IN = "That person is not in this diagram."
# A form carrying a desktop file at its size limit, with room for its name.
FORM_BYTES = attachments.MAX_BYTES + 1024 * 1024


def readable(user) -> list[Diagram]:
    """Owned first, then granted, each once; never a scratch copy or one its
    owner deleted."""
    found = [d for d in user.diagrams if not d.scratch and d.deleted_at is None]
    seen = {d.id for d in found}
    granted = (
        Diagram.query.join(AccessRight, AccessRight.diagram_id == Diagram.id)
        .filter(
            AccessRight.user_id == user.id,
            AccessRight.right.in_(GRANTED),
            Diagram.deleted_at.is_(None),
        )
        # a scratch copy carries its owner's row and is never listed to anyone
        .filter(Diagram.scratch.is_(False))
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
        "owner_username": diagram.user.username,
        "person_id": profile.person_of(user, diagram),
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


def _name(body: dict) -> str:
    name = (body.get("name") or "").strip()
    if not name:
        raise ValueError("A diagram needs a name")
    return name


@bp.route("/diagrams", methods=["POST"])
def diagram_create():
    """A new diagram, which anyone may make (FD-387): an empty one the app is
    put on straight away, so the title row names it before anything is said
    into it. `own_family` answers "Is this your own family?": yes, and the
    maker is the person the chat app makes first; no, and they are a human
    coach on it, the person it belongs to no one on it yet."""
    user = auth.current_user()
    if request.mimetype == "multipart/form-data":
        return _imported(user)
    body = request.get_json()
    name = _name(body)
    own = body.get("own_family")
    if not isinstance(own, bool):
        raise ValueError("Say whether this is your own family")
    made = Diagram(
        user_id=user.id,
        name=name,
        data=diagramjson.dumps({}),
        access_rights=[owner_row(user.id, FIRST_PERSON_ID if own else None)],
    )
    db.session.add(made)
    db.session.flush()
    user.current_diagram_id = made.id
    db.session.commit()
    return jsonify(diagram_payload(made, user)), 201


@bp.route("/diagrams/<int:diagram_id>", methods=["PATCH"])
def diagram_update(diagram_id: int):
    """The owner renames their diagram."""
    user = auth.current_user()
    found = db.get_or_404(Diagram, diagram_id)
    if found.user_id != user.id:
        abort(404)
    found.name = _name(request.get_json())
    db.session.commit()
    return jsonify(diagram_payload(found, user))


def _imported(user):
    """A new case from a Family Diagram desktop file, made here as the file
    stands and opened; the worker then mails its record and groups its
    clusters [Oracle: R-0899, R-0902]."""
    if request.content_length and request.content_length > FORM_BYTES:
        abort(413, description=attachments.TOO_BIG)
    name = _name(request.form)
    data = request.files["file"].read()
    if len(data) > attachments.MAX_BYTES:
        abort(413, description=attachments.TOO_BIG)
    pickled, fd = fdafter.scene(data)
    made, turn, out = fdafter.made(user, name, fd)
    fdafter.enqueue(made, user.id, turn, pickled)
    imported = {
        "people": out.brought["people"],
        "events": out.brought["events"],
        "left_out": out.brought[fdimport.LEFT_OUT],
        "primary": out.primaries,
    }
    return jsonify(diagram_payload(made, user) | {"imported": imported}), 201


@bp.route("/diagrams/<int:diagram_id>", methods=["DELETE"])
def diagram_delete(diagram_id: int):
    """The owner deletes a diagram: it is hidden and nothing is removed, and
    anyone the app was on it goes back to their personal diagram. The personal
    diagram stays [Oracle: R-0904, R-0908]."""
    user = auth.current_user()
    found = db.session.get(Diagram, diagram_id)
    if found is None or found.user_id != user.id or found.deleted_at is not None:
        abort(404)
    if found.id == user.free_diagram_id:
        raise ValueError(PERSONAL)
    found.deleted_at = datetime.datetime.utcnow()
    User.query.filter_by(current_diagram_id=found.id).update(
        {"current_diagram_id": None}
    )
    db.session.commit()
    return "", 204


@bp.route("/diagrams/<int:diagram_id>/access", methods=["PATCH"])
def diagram_access_update(diagram_id: int):
    """Who the signed-in user is on a diagram, on their own access row: a
    person in it, or no one. A person named is also marked the one the
    diagram is about. The owner's row is made when it has none; anyone else
    needs a row already."""
    user = auth.current_user()
    found = db.session.get(Diagram, diagram_id)
    if found is None or found.deleted_at is not None:
        abort(404)
    row = found.access_right(user)
    if row is None and found.user_id != user.id:
        abort(404)
    person_id = request.get_json()["person_id"]
    if person_id is not None and not any(
        p.get("id") == person_id for p in found.get_diagram_data().people
    ):
        raise ValueError(NOT_IN)
    if person_id is not None:
        # the person they are is the one the diagram is about
        record.apply(
            found.id,
            record.made_primary(found.get_diagram_data(), person_id),
            author=Author.User,
            turn_id=uuid.uuid4().hex,
            user_id=user.id,
        )
    if row is None:
        found.access_rights.append(owner_row(user.id, person_id))
    else:
        row.person_id = person_id
    db.session.commit()
    return jsonify(diagram_payload(found, user))


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
