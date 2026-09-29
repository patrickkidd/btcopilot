"""The landing page at familydiagram.com and its two forms: an invited address
asks for its sign-in link, anyone else asks to join the early beta list
(R-0601). Both forms send email, so both sit behind Turnstile."""

import datetime
import logging
from pathlib import Path

from flask import current_app, render_template, request, send_from_directory
from flask_wtf.csrf import generate_csrf

from btcopilot.auth import emails, turnstile
from btcopilot.auth.blueprint import bp
from btcopilot.auth.invitation import Invitation
from btcopilot.models import User

STATIC = Path(__file__).parents[1] / "static"
WORDS_LIMIT = 2000
UNAVAILABLE = "This form is not available right now."
NOT_A_PERSON = "The check that you are a person did not pass. Try again."

_log = logging.getLogger(__name__)


def page(status: int = 200, **state):
    """The page as a visitor sees it, with one form's outcome in `state`."""
    found = turnstile.keys()
    return (
        render_template(
            "landing.html",
            csrf_token=generate_csrf,
            site_key=found[0] if found else None,
            unavailable=UNAVAILABLE if not found else None,
            year=datetime.date.today().year,
            **state,
        ),
        status,
    )


# The app's own static files sit behind sign-in, and a visitor has not signed
# in; only /app reaches the app through Caddy.
@bp.route("/afs-logo.png")
def logo():
    return send_from_directory(STATIC, "afs-logo.png", mimetype="image/png")


def _visitor_ip() -> str | None:
    """The visitor's address as Caddy passed it on; the app itself only ever
    sees the proxy's."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr


def _refused(where: str, **state):
    """None when the post may go on; otherwise the page that refuses it."""
    if not turnstile.keys():
        _log.error(
            "The Turnstile keys are not set, so the landing page's forms are shut"
        )
        return page(503, **state)
    if not turnstile.verify(request.form.get(turnstile.FIELD, ""), _visitor_ip()):
        return page(400, where=where, error=NOT_A_PERSON, **state)
    return None


def _invited(email: str) -> bool:
    return bool(
        Invitation.query.filter_by(email=email).first()
        or User.query.filter_by(username=email).first()
    )


@bp.route("/signin-link", methods=("POST",))
def signin_link():
    email = request.form.get("email", "").strip().lower()
    refused = _refused("link", link_email=email)
    if refused:
        return refused
    if not email:
        return page(400, where="link", error="Enter your email.")

    if not _invited(email):
        _log.warning(f"Sign-in link requested for an address never invited: {email}")
        return page(link_sent=True)

    window = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    issued = Invitation.query.filter(
        Invitation.email == email, Invitation.created_at >= window
    ).count()
    if issued >= current_app.config["LOGIN_CODES_PER_HOUR"]:
        # The same words as every other case, so the cap never shows which
        # addresses are invited.
        _log.warning(f"Sign-in link rate limit hit for {email}")
        return page(link_sent=True)

    invitation = Invitation.issue(email, current_app.config["LANDING_LINK_DAYS"])
    base = current_app.config["SITE_URL"].rstrip("/")
    emails.send_signin_link(email, f"{base}/app/invite/{invitation.token}")
    return page(link_sent=True)


@bp.route("/beta-request", methods=("POST",))
def beta_request():
    raw_name = request.form.get("name", "")
    raw_email = request.form.get("email", "")
    name = raw_name.strip()[:200]
    email = raw_email.strip().lower()[:255]
    words = request.form.get("words", "").strip()[:WORDS_LIMIT]
    kept = {"beta_name": name, "beta_email": email, "beta_words": words}
    refused = _refused("beta", **kept)
    if refused:
        return refused
    if not name or not email:
        return page(400, where="beta", error="Enter your name and your email.", **kept)
    # The name goes into the mail's subject and the address into its reply-to
    # header, where a line break is refused by the mailer.
    if any(c in raw_name + raw_email for c in "\r\n"):
        return page(
            400,
            where="beta",
            error="Put your name and your email on one line each.",
            **kept,
        )
    if not _looks_like_email(email):
        return page(
            400, where="beta", error="That email address does not look right.", **kept
        )

    emails.send_beta_request(name, email, words)
    return page(beta_sent=True)


def _looks_like_email(email: str) -> bool:
    local, at, domain = email.partition("@")
    return bool(
        at
        and local
        and domain
        and "@" not in domain
        and not any(c.isspace() for c in email)
    )
