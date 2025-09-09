"""
Admin route placeholders for Phase 2.
Will be implemented in Phase 4.
"""

from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
def index():
    return "Admin routes - to be implemented in Phase 4"