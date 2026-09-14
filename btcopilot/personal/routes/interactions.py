"""Every tap is learning data (R-0077): the looks that send nothing, the chips
that speak, the plays. The rows and the writing belong to the Interaction
store; this is only the browser's door to it."""

from flask import jsonify, request

from btcopilot import auth
from btcopilot.personal.interactions import record_interaction
from btcopilot.personal.routes import bp


@bp.route("/interactions", methods=["POST"])
def create_interaction():
    interaction = record_interaction(auth.current_user(), request.get_json())
    return jsonify(interaction.as_dict()), 201
