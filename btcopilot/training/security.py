"""
Security configuration for training web application.

Handles CSRF protection, security headers, and other web security measures.
This is separate from API authentication used by the parent application.
"""

from flask import request

def configure_security(app):
    """
    Configure security settings for training web routes.
    
    Args:
        app: Flask application instance
    """
    
    # Security headers that should be applied to all training routes
    @app.after_request
    def add_security_headers(response):
        if request.endpoint and request.endpoint.startswith('training.'):
            # Add security headers for training web routes
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY' 
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Cache control for HTML responses
            if response.content_type and 'text/html' in response.content_type:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                
        return response


def require_web_auth():
    """
    Decorator to require web-based authentication for training routes.
    This should be implemented by the parent application.
    """
    # This will be overridden by the parent application's auth system
    pass