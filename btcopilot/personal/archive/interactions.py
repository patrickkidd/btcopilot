import logging

from flask import Blueprint, jsonify, request, abort

from btcopilot import auth
from btcopilot.personal.interactions import recent, record_interaction
from btcopilot.pro.models import Diagram

_log = logging.getLogger(__name__)

bp = Blueprint("interactions", __name__, url_prefix="/interactions")


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
