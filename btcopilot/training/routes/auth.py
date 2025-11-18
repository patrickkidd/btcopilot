"""Authentication routes for login/logout"""

import logging
import time
import random
from datetime import datetime, timedelta, timezone
from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)

import btcopilot
from btcopilot.pro.models import User
from btcopilot.extensions import db
from btcopilot.training.security import add_security_headers
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

_log = logging.getLogger(__name__)


def get_remote_address():
    """Get the remote IP address from request"""
    return request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)


# Track failed login attempts per IP
failed_attempts = {}
LOCKOUT_TIME = timedelta(minutes=15)  # Lockout duration
MAX_ATTEMPTS = 5  # Max failed attempts before lockout
CAPTCHA_THRESHOLD = 2  # Show CAPTCHA after this many failed attempts


def generate_math_captcha():
    """Generate a simple math problem and return question and answer"""
    operations = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("×", lambda a, b: a * b),
    ]

    # Choose operation
    op_symbol, op_func = random.choice(operations)

    if op_symbol == "+":
        # Addition: 1-20 + 1-20
        a, b = random.randint(1, 20), random.randint(1, 20)
    elif op_symbol == "-":
        # Subtraction: ensure positive result
        a, b = random.randint(10, 30), random.randint(1, 9)
    else:  # Multiplication
        # Multiplication: small numbers
        a, b = random.randint(2, 9), random.randint(2, 9)

    question = f"{a} {op_symbol} {b} = ?"
    answer = op_func(a, b)

    return question, answer


def needs_captcha(ip_address):
    """Check if this IP needs to solve a CAPTCHA"""
    if ip_address not in failed_attempts:
        return False
    return failed_attempts[ip_address]["count"] >= CAPTCHA_THRESHOLD


bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.after_request
def _(response):
    return add_security_headers(response)


def is_ip_locked_out(ip_address):
    """Check if IP is locked out due to too many failed attempts"""
    if ip_address not in failed_attempts:
        return False

    attempt_data = failed_attempts[ip_address]
    if attempt_data["count"] >= MAX_ATTEMPTS:
        # Check if lockout period has passed
        if datetime.now(timezone.utc) - attempt_data["last_attempt"] > LOCKOUT_TIME:
            # Reset failed attempts
            del failed_attempts[ip_address]
            return False
        return True
    return False


def record_failed_attempt(ip_address):
    """Record a failed login attempt for an IP"""
    now = datetime.now(timezone.utc)
    if ip_address not in failed_attempts:
        failed_attempts[ip_address] = {"count": 1, "last_attempt": now}
    else:
        # Reset count if last attempt was more than lockout time ago
        if now - failed_attempts[ip_address]["last_attempt"] > LOCKOUT_TIME:
            failed_attempts[ip_address] = {"count": 1, "last_attempt": now}
        else:
            failed_attempts[ip_address]["count"] += 1
            failed_attempts[ip_address]["last_attempt"] = now


def clear_failed_attempts(ip_address):
    """Clear failed attempts for successful login"""
    if ip_address in failed_attempts:
        del failed_attempts[ip_address]


@bp.route("/app", methods=["GET"])
def app_auth():
    """Authenticate using token from desktop app"""
    token = request.args.get("token")
    if not token:
        flash("Invalid authentication link", "error")
        return redirect(url_for("training.auth.login"))

    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

    try:
        token_data = serializer.loads(token, salt="web-auth", max_age=300)
    except SignatureExpired:
        _log.warning("Expired web auth token used")
        flash("Authentication link has expired. Please try again.", "error")
        return redirect(url_for("training.auth.login"))
    except BadSignature:
        _log.warning("Invalid web auth token signature")
        flash("Invalid authentication link", "error")
        return redirect(url_for("training.auth.login"))

    if token_data.get("purpose") != "web_auth":
        _log.warning("Invalid web auth token purpose")
        flash("Invalid authentication link", "error")
        return redirect(url_for("training.auth.login"))

    user_id = token_data.get("user_id")
    if not user_id:
        _log.warning("Web auth token missing user_id")
        flash("Invalid authentication link", "error")
        return redirect(url_for("training.auth.login"))

    user = User.query.get(user_id)
    if not user or not user.active:
        _log.warning(f"Web auth token for inactive/nonexistent user: {user_id}")
        flash("Account not found or inactive", "error")
        return redirect(url_for("training.auth.login"))

    session["user_id"] = user.id
    session["logged_in_at"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True

    ip_address = get_remote_address()
    _log.info(
        f"Successful app-based authentication for user: {user.username} from {ip_address}"
    )

    return redirect(btcopilot.auth.get_landing_page_for_user(user))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # If user is already logged in, redirect to their landing page
        user_id = session.get("user_id")
        if user_id:
            user = User.query.get(user_id)
            if user and user.active:
                return redirect(btcopilot.auth.get_landing_page_for_user(user))

        return render_template("app_auth_landing.html")

    # Old password login form - commented out for app-only auth
    # Keeping code for easy restoration if needed
    return ("Method not allowed", 405)
    """
    # Commented out password login POST handler
    ip_address = get_remote_address()

    # Check if IP is locked out
    if is_ip_locked_out(ip_address):
        _log.warning(f"Login attempt from locked out IP: {ip_address}")
        flash("Too many failed attempts. Please try again in 15 minutes.", "error")
        return render_template("auth/login.html"), 429

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    captcha_answer = request.form.get("captcha_answer", "").strip()

    # Input validation
    if not username or not password:
        flash("Username and password are required", "error")
        # Regenerate CAPTCHA if needed
        captcha_data = None
        if needs_captcha(ip_address):
            question, answer = generate_math_captcha()
            session["captcha_answer"] = answer
            captcha_data = {"question": question}
        return render_template("auth/login.html", captcha=captcha_data), 400

    # CAPTCHA validation if required
    if needs_captcha(ip_address):
        expected_answer = session.get("captcha_answer")
        if (
            not captcha_answer
            or not expected_answer
            or str(captcha_answer) != str(expected_answer)
        ):
            _log.warning(f"Failed CAPTCHA attempt from IP: {ip_address}")
            flash("Please solve the math problem correctly", "error")
            # Generate new CAPTCHA
            question, answer = generate_math_captcha()
            session["captcha_answer"] = answer
            captcha_data = {"question": question}
            return render_template("auth/login.html", captcha=captcha_data), 400

    # Additional security: limit username length to prevent DoS
    if len(username) > 100 or len(password) > 255:
        flash("Invalid credentials", "error")
        return render_template("auth/login.html"), 400

    # Add delay to prevent timing attacks
    start_time = time.time()

    # Look up user
    user = User.query.filter_by(username=username).first()

    # Always check password even if user doesn't exist (prevent timing attacks)
    if user:
        password_correct = user.check_password(password)
        user_active = user.active
    else:
        # Perform dummy password check to maintain consistent timing
        from flask_bcrypt import check_password_hash

        check_password_hash("$2b$12$dummy.hash.to.maintain.timing", password)
        password_correct = False
        user_active = False

    # Ensure minimum time for response (prevent timing attacks)
    elapsed = time.time() - start_time
    if elapsed < 0.5:  # Minimum 500ms response time
        time.sleep(0.5 - elapsed)

    if not user or not password_correct or not user_active:
        # Record failed attempt
        record_failed_attempt(ip_address)

        if not user:
            _log.warning(
                f"Login attempt for non-existent user: {username} from {ip_address}"
            )
        elif not user_active:
            _log.warning(
                f"Login attempt for inactive user: {username} from {ip_address}"
            )
        else:
            _log.warning(f"Failed login attempt for user: {username} from {ip_address}")

        flash("Invalid username or password", "error")
        # Regenerate CAPTCHA if needed for the error page
        captcha_data = None
        if needs_captcha(ip_address):
            question, answer = generate_math_captcha()
            session["captcha_answer"] = answer
            captcha_data = {"question": question}
        return render_template("auth/login.html", captcha=captcha_data), 401

    # Successful login
    clear_failed_attempts(ip_address)
    session["user_id"] = user.id
    session["logged_in_at"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True  # Make session persistent

    # Clear CAPTCHA data
    session.pop("captcha_answer", None)

    _log.info(f"Successful login for user: {username} from {ip_address}")

    # Redirect to next page or default
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    # Default redirect based on user role
    if user.has_role(btcopilot.ROLE_ADMIN):
        return redirect(url_for("training.admin.index"))
    elif user.has_role(btcopilot.ROLE_AUDITOR):
        return redirect(url_for("training.audit.index"))
    else:
        # Default to training root which handles role-based redirects
        return redirect(url_for("training.training_root"))
    """


@bp.route("/logout", methods=["POST"])
def logout():
    from flask_wtf.csrf import validate_csrf

    # CSRF validation for logout
    try:
        validate_csrf(request.form.get("csrf_token"))
    except Exception as e:
        _log.warning(f"CSRF validation failed for logout: {e}")
        flash("Invalid security token", "error")
        return redirect(url_for("training.auth.login"))

    if "user_id" in session:
        user_id = session["user_id"]
        _log.info(f"User {user_id} logged out from {get_remote_address()}")

    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("training.auth.login"))
