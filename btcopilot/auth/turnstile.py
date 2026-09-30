"""Cloudflare Turnstile, the check that a form on the landing page was sent by
a person. Both of the page's forms send email, so neither is taken without it."""

import logging

import requests
from flask import current_app

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Cloudflare's documented keys that always pass, so a development server with
# no widget of its own can still be driven end to end.
TEST_SITE_KEY = "1x00000000000000000000AA"
TEST_SECRET_KEY = "1x0000000000000000000000000000000AA"
FIELD = "cf-turnstile-response"

_log = logging.getLogger(__name__)


def keys() -> tuple[str, str] | None:
    """The site key and the secret, or None where the forms must stay shut."""
    config = current_app.config
    site = config.get("TURNSTILE_SITE_KEY")
    secret = config.get("TURNSTILE_SECRET_KEY")
    if site and secret:
        return site, secret
    if config["CONFIG"] == "development" and not site and not secret:
        return TEST_SITE_KEY, TEST_SECRET_KEY
    return None


def verify(token: str, remote_ip: str | None) -> bool:
    found = keys()
    if not found or not token:
        return False
    try:
        answer = requests.post(
            VERIFY_URL,
            data={"secret": found[1], "response": token, "remoteip": remote_ip},
            timeout=5,
        )
        answer.raise_for_status()
        result = answer.json()
    except Exception as e:
        _log.error(f"Turnstile check could not be made: {e}")
        return False
    if not result.get("success"):
        _log.warning(
            f"Turnstile check failed from {remote_ip}: {result.get('error-codes')}"
        )
        return False
    return True
