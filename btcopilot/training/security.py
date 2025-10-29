"""Security configuration and utilities for therapist blueprint"""

import logging
from flask import request, current_app
from flask_wtf.csrf import CSRFError

_log = logging.getLogger(__name__)


def add_security_headers(response):
    """Add security headers to response - for therapist and auth routes"""
    if not request.endpoint or not (
        request.endpoint.startswith("training.") or request.endpoint.startswith("auth.")
    ):
        return response

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Enable XSS filter (legacy but still useful for older browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Force HTTPS if in production and request is secure
    if current_app.config.get("CONFIG") != "development" and request.is_secure:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    # Content Security Policy - tailored to your current CDN usage
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.assemblyai.com; "
        "frame-src 'none'"
    )
    response.headers["Content-Security-Policy"] = csp_policy

    return response


def init_app(app):
    """Configure secure session settings"""
    # Only set secure cookies in production or when using HTTPS
    is_production = app.config.get("CONFIG") != "development"

    if is_production:
        app.config["SESSION_COOKIE_SECURE"] = True

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Ensure we have a secret key
    if not app.config.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY must be set for CSRF protection")
