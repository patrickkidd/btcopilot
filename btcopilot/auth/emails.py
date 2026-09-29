import logging

from flask import current_app
from flask_mail import Message

import btcopilot
from btcopilot import extensions
from btcopilot.config import Config
from btcopilot.models import User

_log = logging.getLogger(__name__)

# Someone asked to code for the group is told nothing else before their first
# task, so the invitation and every sign-in code say what the work is.
AUDITOR = (
    "You have been asked to code conversations for the group's meetings: before "
    "each meeting you read one conversation and say what each line of it tells "
    "you happened. The app shows you each task when one is waiting and walks you "
    "through it step by step, so there is nothing to learn first.\n"
)


def _deliver(recipient: str, subject: str, body: str):
    """A development server with no mail server configured writes the link or
    the code to the log instead, so a sandbox can be driven without one."""
    config = current_app.config
    if config["CONFIG"] == Config.Development and "MAIL_SERVER" not in config:
        _log.warning(f"[dev mail] {recipient} — {subject}\n{body}")
        return
    message = Message(
        subject,
        recipients=[recipient],
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    message.body = body
    extensions.mail.send(message)


def _auditor(email: str) -> bool:
    """Patrick holds every role, and the words are not for him."""
    user = User.query.filter_by(username=email).first()
    return (
        user is not None
        and user.has_role(btcopilot.ROLE_AUDITOR)
        and not user.has_role(btcopilot.ROLE_ADMIN)
    )


def _explained(email: str, body: str) -> str:
    return f"{body}\n{AUDITOR}" if _auditor(email) else body


def send_invitation(email: str, url: str):
    _deliver(
        email,
        "Your Family Diagram invitation",
        _explained(
            email,
            f"Open this link to start. It works once and needs no password.\n\n{url}\n",
        ),
    )


def send_nudge(email: str, sessions: list[str], meeting: str):
    what = "\n".join(f"- {one}" for one in sessions)
    _deliver(
        email,
        "Coding still open before the next meeting",
        f"The meeting on {meeting} is waiting on your coding of:\n\n{what}\n\n"
        "Open the app and your task is the first thing on the screen.\n",
    )


def send_login_code(email: str, code: str, minutes: int):
    _deliver(
        email,
        "Your Family Diagram sign-in code",
        _explained(
            email, f"Your sign-in code is {code}. It expires in {minutes} minutes.\n"
        ),
    )


def send_notification(email: str, subject: str, words: str, url: str):
    _deliver(email, subject, f"{words}\n\n{url}\n")
