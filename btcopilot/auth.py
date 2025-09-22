import sys
import logging
from functools import wraps
from typing import Union

from flask import g, request, abort, session, redirect, url_for

import vedana
from btcopilot.pro.models import User


_log = logging.getLogger(__name__)


def is_pro_app_request():
    return request.path.startswith("/v1/")


def is_personal_app_request():
    return request.path.startswith("/personal")


def is_training_app_request() -> bool:
    return request.path.startswith("/training")


def _set_tracing_tags(user):
    """Set tracing tags for the current user if available."""
    if "ddtrace" in sys.modules:
        from ddtrace import tracer

        span = tracer.current_span()
        if span and not getattr(user, "IS_ANONYMOUS", False):
            span.set_tag("user.id", user.id)
            span.set_tag("user.username", user.username)
            span.set_tag("user.name", f"{user.first_name} {user.last_name}")


class AnonUser:
    IS_ANONYMOUS = True

    def roles(self):
        return "anonymous"

    def hasRoles(self, *roles):
        return roles == ("anonymous",)

    def has_role(self, role: str) -> bool:
        """Check if anonymous user has a specific role - always returns False except for anonymous."""
        return role == "anonymous"


def current_user() -> Union[User, None]:
    """
    Get the current authenticated user (possibly cached).

    For pro/personal apps (/v1/*, /personal/*): Returns user if signature is valid
    For training app (/training/*): Returns user if session is valid
    """
    if "current_user" in g:
        return g.current_user

    if is_pro_app_request() or is_personal_app_request():
        return _authenticate_pro_personal_apps()

    elif is_training_app_request():
        return _authenticate_training_app()

    # Other requests (root, static, etc.) - no authentication required
    return None


def _handle_unauthorized(status_code):
    """Handle unauthorized access based on request type."""
    if is_personal_app_request():
        abort(status_code)
    else:
        # For web requests, redirect to login
        from werkzeug.exceptions import HTTPException

        redirect_response = redirect(url_for("training.auth.login", next=request.url))
        # Create a proper HTTP exception with the redirect response
        exception = HTTPException()
        exception.response = redirect_response
        raise exception


def require_role(minimum: str) -> User:
    """
    Ensure the current user has the minimum required role.

    Returns the authenticated user if they have the required role.
    Redirects to login or aborts with 403 if not authorized.
    """
    user = current_user()

    if not user:
        return _handle_unauthorized(401)

    if not user.has_role(minimum):
        return _handle_unauthorized(403)

    return user


def get_required_role() -> str:
    """
    Determine the minimum role required for the current request.

    Priority order:
    1. Function-level @minimum_role (highest)
    2. Blueprint-level @minimum_role (medium)
    3. Parent blueprint default (lowest - ROLE_SUBSCRIBER)
    """
    from flask import request, current_app

    # Get the current endpoint
    endpoint = request.endpoint
    if not endpoint:
        return vedana.ROLE_SUBSCRIBER

    # Get the view function
    view_func = current_app.view_functions.get(endpoint)
    if view_func and hasattr(view_func, "_minimum_role"):
        return view_func._minimum_role

    # Check blueprint-level role requirement
    # Extract blueprint name from endpoint (format: "blueprint.function" or "parent.child.function")
    if "." in endpoint:
        parts = endpoint.split(".")
        # For nested blueprints, we need to check parent.child
        if len(parts) >= 2:
            # Try parent.child first (for nested blueprints)
            nested_blueprint_name = ".".join(parts[:-1])
            blueprint = current_app.blueprints.get(nested_blueprint_name)
            if blueprint and hasattr(blueprint, "_minimum_role"):
                return blueprint._minimum_role

            # Fall back to just the immediate parent
            blueprint_name = parts[0]
            blueprint = current_app.blueprints.get(blueprint_name)
            if blueprint and hasattr(blueprint, "_minimum_role"):
                return blueprint._minimum_role

    return vedana.ROLE_SUBSCRIBER


def minimum_role(role):
    """
    Decorator that can be applied to both Flask Blueprints and view functions.

    For Blueprints: Sets the default minimum role for all routes in the blueprint
    For Functions: Sets the minimum role for that specific endpoint

    Role hierarchy: function > blueprint > parent blueprint default
    """

    def decorator(target):
        from flask import Blueprint

        if isinstance(target, Blueprint):
            # Store role requirement on blueprint
            target._minimum_role = role
            return target
        else:
            # Store role requirement on function and return wrapper
            @wraps(target)
            def decorated_view(*args, **kwargs):
                require_role(role)
                return target(*args, **kwargs)

            decorated_view._minimum_role = role
            return decorated_view

    return decorator


def _authenticate_pro_personal_apps() -> User | None:
    """Handle desktop app authentication using FD-Authentication header.

    Desktop app authentication is completely controlled by signed headers.
    No role checking is performed here - that's handled by the app's business logic.
    """
    headers = request.headers
    auth_header = headers.get("FD-Authentication")
    if auth_header is None:
        return abort(401)

    authParts = auth_header.split(":")
    if authParts[1] == vedana.ANON_USER:
        user = AnonUser()
        secret = vedana.ANON_SECRET
    else:
        username = authParts[1]
        user = User.query.filter_by(username=username).first()
        if not user:
            return abort(401)
        secret = user.secret.encode("utf-8")

        # Verify signature
        theirSignature = authParts[2]
        content_md5 = headers.get("Content-MD5")
        content_type = headers.get("Content-Type")
        date = headers.get("Date")

        if request.query_string:
            resource = request.path + "?" + request.query_string.decode("utf-8")
        else:
            resource = request.path
        ourSignature = vedana.sign(
            secret, request.method, content_md5, content_type, date, resource
        )
        if ourSignature != theirSignature:
            _log.debug("Auth signature %s != %s" % (theirSignature, ourSignature))
            return abort(401)

    g.current_user = user
    _set_tracing_tags(user)
    return user


def _authenticate_training_app() -> User | None:
    """Authenticate user for personal app (/training/*) - supports both session and signature auth."""
    # First, try session-based authentication (for web users)
    user_id = session.get("user_id")
    if user_id:
        user = User.query.get(user_id)
        if user:
            g.current_user = user
            _set_tracing_tags(user)
            return user
        else:
            # Invalid session - clear it
            session.clear()

    # If both methods fail, return unauthorized

    from werkzeug.exceptions import HTTPException

    redirect_response = redirect(url_for("training.auth.login", next=request.url))
    # Create a proper HTTP exception with the redirect response
    exception = HTTPException()
    exception.response = redirect_response
    raise exception
