"""Every tap is learning data (R-0077): the looks that send nothing, the chips
that speak, the plays.

The rows and the writing belong to the personal app's Interaction store; this is
only the browser's door to it. /personal/ is signed by the native apps, so a page
running on a session cookie cannot post there directly."""

from flask import jsonify, request

from btcopilot import auth
from btcopilot.companion.blueprint import bp
from btcopilot.personal.routes.interactions import record_interaction


@bp.route("/interactions", methods=["POST"])
def create_interaction():
    interaction = record_interaction(auth.current_user(), request.get_json())
    return jsonify(interaction.as_dict()), 201
