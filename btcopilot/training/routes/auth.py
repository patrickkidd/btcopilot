"""
Auth route placeholders for Phase 2.
Will be implemented in Phase 4.
"""

from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login')
def login():
    return "Auth routes - to be implemented in Phase 4"