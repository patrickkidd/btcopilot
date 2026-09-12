"""Which of the app's surfaces a reader gets: features turn on by licence, role
and view, never by a separate app (R-0237). A professional licence is the one
gate the chat app reads — it adds cases, recordings and notes to the surfaces
that already exist."""

from flask import abort

import btcopilot
from btcopilot import auth
from btcopilot.pro.models.license import LicenseStatus


def professional(user) -> bool:
    return any(
        licence.policy.product == btcopilot.LICENSE_PROFESSIONAL
        and licence.status() == LicenseStatus.Active
        for licence in user.licenses
    )


def require_professional() -> None:
    """A reader without the licence is told the surface is not there, never
    that it exists and is refused."""
    if not professional(auth.current_user()):
        abort(404)
