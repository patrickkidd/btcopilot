"""
Training web application routes.

Provides web-based interfaces for AI training data collection and review.
All routes use standard web authentication (sessions, CSRF) rather than
API authentication methods.
"""

from flask import Blueprint

# Main blueprint for the training web application
training_bp = Blueprint(
    'training', 
    __name__,
    template_folder='../templates',
    static_folder='../static',
    url_prefix='/training'
)

# Import and register sub-blueprints
from .audit import audit_bp
from .feedback import feedback_bp
from .prompts import prompts_bp
from .admin import admin_bp
from .auth import auth_bp

training_bp.register_blueprint(audit_bp)
training_bp.register_blueprint(feedback_bp) 
training_bp.register_blueprint(prompts_bp)
training_bp.register_blueprint(admin_bp)
training_bp.register_blueprint(auth_bp)

# Import route handlers to register them
from . import views