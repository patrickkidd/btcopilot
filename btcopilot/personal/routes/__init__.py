from flask import Blueprint

from .discussions import bp as discussions_bp
from .diagrams import diagrams_bp

bp = Blueprint("personal", __name__, url_prefix="/personal")
bp.register_blueprint(discussions_bp)
bp.register_blueprint(diagrams_bp)


def init_app(app):
    app.register_blueprint(bp)
