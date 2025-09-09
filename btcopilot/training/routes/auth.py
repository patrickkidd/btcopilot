"""
Authentication routes for training web interface.

Provides simple login/logout functionality for the training web interface.
Uses stand-in implementations that should be overridden by the parent 
application with proper user management and security features.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, render_template, redirect, url_for, flash, session

_log = logging.getLogger(__name__)

# Create the auth blueprint
auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
    template_folder="../templates",
    static_folder="../static",
)

# Note: Authentication/authorization should be provided by parent application

# Stand-in user database - parent application should provide real user management
STAND_IN_USERS = {
    "admin": {
        "id": 1,
        "username": "admin",
        "password": "admin123",  # Stand-in password
        "roles": ["admin"],
        "active": True,
    },
    "auditor": {
        "id": 2,
        "username": "auditor",
        "password": "auditor123",  # Stand-in password
        "roles": ["auditor"],
        "active": True,
    }
}


def get_remote_address():
    """Get the remote IP address from request"""
    return request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)


# Simple failed login tracking for demonstration
failed_attempts = {}
LOCKOUT_TIME = timedelta(minutes=15)
MAX_ATTEMPTS = 5


def is_ip_locked_out(ip_address):
    """Check if IP is locked out - simplified implementation"""
    if ip_address not in failed_attempts:
        return False
    
    attempt_data = failed_attempts[ip_address]
    if attempt_data["count"] >= MAX_ATTEMPTS:
        if datetime.now(timezone.utc) - attempt_data["last_attempt"] > LOCKOUT_TIME:
            del failed_attempts[ip_address]
            return False
        return True
    return False


def record_failed_attempt(ip_address):
    """Record a failed login attempt"""
    now = datetime.now(timezone.utc)
    if ip_address not in failed_attempts:
        failed_attempts[ip_address] = {"count": 1, "last_attempt": now}
    else:
        if now - failed_attempts[ip_address]["last_attempt"] > LOCKOUT_TIME:
            failed_attempts[ip_address] = {"count": 1, "last_attempt": now}
        else:
            failed_attempts[ip_address]["count"] += 1
            failed_attempts[ip_address]["last_attempt"] = now


def clear_failed_attempts(ip_address):
    """Clear failed attempts for successful login"""
    if ip_address in failed_attempts:
        del failed_attempts[ip_address]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page - stand-in implementation"""
    ip_address = get_remote_address()

    if request.method == "GET":
        return render_template("auth/login.html")

    # Check if IP is locked out
    if is_ip_locked_out(ip_address):
        _log.warning(f"Login attempt from locked out IP: {ip_address}")
        flash("Too many failed attempts. Please try again in 15 minutes.", "error")
        return render_template("auth/login.html"), 429

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    # Input validation
    if not username or not password:
        flash("Username and password are required", "error")
        return render_template("auth/login.html"), 400

    # Additional security: limit input length
    if len(username) > 100 or len(password) > 255:
        flash("Invalid credentials", "error")
        return render_template("auth/login.html"), 400

    # Add delay to prevent timing attacks
    start_time = time.time()

    # Stand-in user lookup
    user_data = STAND_IN_USERS.get(username)
    
    if user_data and user_data["password"] == password and user_data["active"]:
        password_correct = True
        user_active = True
    else:
        password_correct = False
        user_active = False

    # Ensure minimum time for response (prevent timing attacks)
    elapsed = time.time() - start_time
    if elapsed < 0.5:
        time.sleep(0.5 - elapsed)

    if not user_data or not password_correct or not user_active:
        record_failed_attempt(ip_address)
        
        _log.warning(f"Failed login attempt for user: {username} from {ip_address}")
        flash("Invalid username or password", "error")
        return render_template("auth/login.html"), 401

    # Successful login
    clear_failed_attempts(ip_address)
    session["user_id"] = user_data["id"]
    session["username"] = user_data["username"]
    session["roles"] = user_data["roles"]
    session["logged_in_at"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True

    _log.info(f"Successful login for user: {username} from {ip_address}")

    # Redirect to next page or default
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    # Default redirect based on user role
    if "admin" in user_data["roles"]:
        return redirect(url_for("admin.index"))
    elif "auditor" in user_data["roles"]:
        return redirect(url_for("audit.index"))
    else:
        return redirect(url_for("audit.index"))  # Default to audit


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout - stand-in implementation"""
    if "user_id" in session:
        user_id = session["user_id"]
        _log.info(f"User {user_id} logged out from {get_remote_address()}")

    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout", methods=["GET"])
def logout_get():
    """GET logout for convenience - stand-in implementation"""
    if "user_id" in session:
        user_id = session["user_id"]
        _log.info(f"User {user_id} logged out from {get_remote_address()}")

    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("auth.login"))


def get_current_user():
    """Get current user from session - stand-in implementation"""
    if "user_id" not in session:
        return None
    
    user_id = session["user_id"]
    username = session.get("username")
    roles = session.get("roles", [])
    
    return {
        "id": user_id,
        "username": username,
        "roles": roles,
        "active": True,
        "note": "Stand-in user - parent app should provide real user management"
    }


def require_auth():
    """Decorator helper to require authentication - stand-in implementation"""
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return None


def require_role(required_role):
    """Check if current user has required role - stand-in implementation"""
    if "user_id" not in session:
        return False
    
    user_roles = session.get("roles", [])
    return required_role in user_roles