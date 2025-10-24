from flask import Blueprint, jsonify

from btcopilot import auth
from .discussions import bp as discussions_bp
from .diagrams import diagrams_bp

bp = Blueprint("personal", __name__, url_prefix="/personal")
bp.register_blueprint(discussions_bp)
bp.register_blueprint(diagrams_bp)


@bp.route("/pdp", methods=["GET"])
def pdp():
    """
    Returns the current PDP (Person Data Points) for the logged-in user.
    """
    user = auth.current_user()
    # diagram_data = DiagramData(**user.diagram_data)
    # pdp_data = {
    #     "people": [person.model_dump() for person in diagram_data.pdp.people],
    #     "events": [event.model_dump() for event in diagram_data.pdp.events],
    # }
    if user.free_diagram:
        diagram_data = user.free_diagram.get_diagram_data()
        return jsonify(diagram_data.pdp.model_dump())
    else:
        return jsonify({})


def init_app(app):
    app.register_blueprint(bp)
