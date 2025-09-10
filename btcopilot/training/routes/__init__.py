"""
Training web application routes.

Provides web-based interfaces for AI training data collection and review.
All routes use standard web authentication (sessions, CSRF) rather than
API authentication methods.

When integrated with fdserver, authentication is handled by the parent application.
"""

from flask import Blueprint, g, request, render_template, redirect, url_for

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
from .discussions import discussions_bp

training_bp.register_blueprint(audit_bp)
training_bp.register_blueprint(feedback_bp) 
training_bp.register_blueprint(prompts_bp)
training_bp.register_blueprint(admin_bp)
training_bp.register_blueprint(auth_bp)
training_bp.register_blueprint(discussions_bp)


@training_bp.before_request
def setup_integration_context():
    """Set up context for integration with parent application."""
    # Check if we're running in integrated mode (fdserver provides these)
    if hasattr(g, 'db_session'):
        # Use fdserver's database session
        from ..models import set_session
        set_session(g.db_session)
    
    if hasattr(g, 'custom_prompts'):
        # Use fdserver's prompt overrides
        from .. import prompts
        prompts.update_prompts(g.custom_prompts)


# Error handlers for training web interface
@training_bp.errorhandler(404)
def handle_404(e):
    """Handle 404 errors for training web interface with template rendering."""
    from ..auth import get_current_user
    current_user = get_current_user()
    return render_template('errors/404.html', current_user=current_user), 404


@training_bp.errorhandler(403)
def handle_403(e):
    """Handle 403 errors for training web interface - redirect to login."""
    return redirect(url_for('training.auth.login', next=request.url))


# Import route handlers to register them
from . import views