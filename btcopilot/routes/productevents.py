from flask import jsonify, request

from btcopilot import auth
from btcopilot.productevents import record_events
from btcopilot.routes import bp


@bp.route("/product-events", methods=["POST"])
def create_product_events():
    data = request.get_json()
    stored = record_events(auth.current_user(), data["session_id"], data["events"])
    return jsonify({"stored": stored}), 201
