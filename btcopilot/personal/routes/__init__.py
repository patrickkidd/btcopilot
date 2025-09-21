from flask import Blueprint, jsonify

from btcopilot import auth

bp = Blueprint("personal", __name__, url_prefix="/personal")


@bp.route("/pdp", methods=["GET"])
def pdp():
    """
    Returns the current PDP (Person Data Points) for the logged-in user.
    """
    user = auth.current_user()
    # database = Database(**user.database)
    # pdp_data = {
    #     "people": [person.model_dump() for person in database.pdp.people],
    #     "events": [event.model_dump() for event in database.pdp.events],
    # }
    if user.free_diagram:
        database = user.free_diagram.get_database()
        return jsonify(database.pdp.model_dump())
    else:
        return jsonify({})
