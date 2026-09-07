import logging

from flask import Blueprint, jsonify, request, abort

from btcopilot import auth
from btcopilot.extensions import db
from btcopilot.personal.models import Interaction, InteractionKind
from btcopilot.pro.models import Diagram
from btcopilot.schema import ItemKind

_log = logging.getLogger(__name__)

bp = Blueprint("interactions", __name__, url_prefix="/interactions")


def recent(diagram_id: int, n: int = 50) -> list[Interaction]:
    return (
        Interaction.query.filter_by(diagram_id=diagram_id)
        .order_by(Interaction.id.desc())
        .limit(n)
        .all()
    )


def record_interaction(user, data: dict) -> Interaction:
    """Write one tap against the diagram it touched. The browser surface
    authenticates its own way and calls this directly: /personal/ is signed by
    the native apps and a session cookie cannot reach it."""
    diagram = Diagram.query.get(data["diagram_id"])
    if not diagram:
        abort(404)
    if not diagram.check_read_access(user):
        abort(403)

    interaction = Interaction(
        diagram_id=diagram.id,
        user_id=user.id,
        session_id=data.get("session_id"),
        statement_id=data.get("statement_id"),
        kind=InteractionKind(data["kind"]),
        item_kind=ItemKind(data["item_kind"]),
        item_id=str(data["item_id"]) if data.get("item_id") is not None else None,
    )
    db.session.add(interaction)
    db.session.commit()
    return interaction


@bp.route("/", methods=["POST"], strict_slashes=False)
def record():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body is required"), 400
    interaction = record_interaction(auth.current_user(), data)
    return jsonify(success=True, interaction=interaction.as_dict())


@bp.route("/", strict_slashes=False)
def index():
    user = auth.current_user()
    diagram = Diagram.query.get(request.args["diagram_id"])
    if not diagram:
        abort(404)
    if not diagram.check_read_access(user):
        abort(403)

    n = int(request.args.get("n", 50))
    return jsonify(interactions=[x.as_dict() for x in recent(diagram.id, n)])
