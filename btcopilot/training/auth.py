"""
Authentication utilities for training web application.

Provides decorators and utilities for web-based authentication.
When integrated with fdserver, uses fdserver's authentication system.
"""

import enum
from functools import wraps
from flask import g, redirect, url_for, request, session

# Global storage for role checking functions
_role_checkers = {}


class UserRole(enum.StrEnum):
    """User roles for training web application authorization."""
    Auditor = "auditor"
    Admin = "admin"


def role_checker(role: UserRole):
    """Decorator to register a role checking function.

    Usage in parent application:
        from btcopilot.training.auth import role_checker, UserRole

        @role_checker(UserRole.Auditor)
        def is_auditor(user):
            return user and user.has_role(ROLE_AUDITOR)

        @role_checker(UserRole.Admin)
        def is_admin(user):
            return user and user.has_role(ROLE_ADMIN)
    """

    def decorator(func):
        _role_checkers[role] = func
        return func

    return decorator


def _check_role(user, role):
    """Internal function to check roles using registered checkers."""
    if role in _role_checkers:
        return _role_checkers[role](user)
    # Fallback to has_role method for backward compatibility
    if hasattr(user, "has_role"):
        return user.has_role(role)
    return False


def get_current_user():
    """Get the current authenticated user."""
    # Check if parent app (fdserver) provided user context
    if hasattr(g, "current_user"):
        return g.current_user

    # Fallback for standalone mode
    if "user_id" in session:
        # Stand-in user object for standalone mode
        class StandInUser:
            def __init__(self, user_id):
                self.id = user_id
                self.username = f"user_{user_id}"
                self.roles = ["auditor"]  # Default role for standalone

            def has_role(self, role):
                return role in self.roles

        return StandInUser(session["user_id"])

    return None


def require_auth(f):
    """Require authentication for a route."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("training.auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def require_auditor_or_admin(f):
    """Require auditor or admin role for a route."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("training.auth.login", next=request.url))

        # Check if user has required role using registered checkers
        if not (_check_role(user, UserRole.Auditor) or _check_role(user, UserRole.Admin)):
            return redirect(url_for("training.auth.login", next=request.url))

        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """Require admin role for a route."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("training.auth.login", next=request.url))

        # Check if user has admin role using registered checker
        if not _check_role(user, UserRole.Admin):
            return redirect(url_for("training.auth.login", next=request.url))

        return f(*args, **kwargs)

    return decorated_function


def check_admin_access():
    """Check if current user has admin access."""
    user = get_current_user()
    if not user:
        return False

    return _check_role(user, UserRole.Admin)


def get_auditor_id():
    """Get the current auditor's ID for feedback tracking."""
    user = get_current_user()
    if user:
        return getattr(user, "username", getattr(user, "id", "unknown"))
    return "anonymous"
