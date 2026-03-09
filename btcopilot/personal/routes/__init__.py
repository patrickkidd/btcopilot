import os

from flask import Blueprint, g, jsonify

from btcopilot import auth
from .discussions import bp as discussions_bp
from .diagrams import diagrams_bp

bp = Blueprint("personal", __name__, url_prefix="/personal")
bp.register_blueprint(discussions_bp)
bp.register_blueprint(diagrams_bp)


@bp.before_request
def include_all_fields():
    """Personal app is always up-to-date, include all versioned fields."""
    g.fd_include_all_fields = True


@bp.route("/assemblyai-key")
def assemblyai_key():
    auth.current_user()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        return (
            jsonify({"success": False, "error": "AssemblyAI API key not configured"}),
            500,
        )
    return jsonify({"success": True, "api_key": api_key})


def init_app(app):
    app.register_blueprint(bp)
