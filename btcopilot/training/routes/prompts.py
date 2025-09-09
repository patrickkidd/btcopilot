"""
Prompts route placeholders for Phase 2.
Will be implemented in Phase 4.
"""

from flask import Blueprint

prompts_bp = Blueprint('prompts', __name__, url_prefix='/prompts')

@prompts_bp.route('/')
def index():
    return "Prompts routes - to be implemented in Phase 4"