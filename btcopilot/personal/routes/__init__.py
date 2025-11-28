from flask import Blueprint, g

from .discussions import bp as discussions_bp
from .diagrams import diagrams_bp

bp = Blueprint("personal", __name__, url_prefix="/personal")
bp.register_blueprint(discussions_bp)
bp.register_blueprint(diagrams_bp)


@bp.before_request
def include_all_fields():
    """Personal app is always up-to-date, include all versioned fields."""
    g.fd_include_all_fields = True


def init_app(app):
    app.register_blueprint(bp)
