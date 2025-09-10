"""
BT Copilot Training Web Application

Open-source AI auditing web framework for training data collection and review.
Provides web-based interfaces for:
- Statement auditing and feedback collection
- AI extraction review and correction
- Prompt lab for testing and refinement
- Test case generation for model training

This module is designed to be imported and integrated into Flask applications
that provide the database session and user authentication.
"""


def init_app(app):
    """
    Initialize the training web application with a Flask app.

    Args:
        app: Flask application instance with configured database and auth

    The calling application should provide:
    - Database session via app extensions
    - User authentication system
    - Security configuration (CSRF, headers)
    """
    from .routes import training_bp

    app.register_blueprint(training_bp, url_prefix="/training")

    # Configure security headers for web routes
    from . import security

    security.init_app(app)
