import logging

from flask import current_app
from flask_mail import Message

from btcopilot import extensions

_log = logging.getLogger(__name__)


def _deliver(recipient: str, subject: str, body: str, reply_to: str | None = None):
    """A development server with no mail server configured writes the link or
    the code to the log instead, so a sandbox can be driven without one."""
    config = current_app.config
    if config["CONFIG"] == "development" and "MAIL_SERVER" not in config:
        _log.warning(f"[dev mail] {recipient} — {subject}\n{body}")
        return
    message = Message(
        subject,
        recipients=[recipient],
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        reply_to=reply_to,
    )
    message.body = body
    extensions.mail.send(message)


def send_invitation(email: str, url: str):
    _deliver(
        email,
        "Your Family Diagram invitation",
        f"Open this link to start. It works once and needs no password.\n\n{url}\n",
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
        f"Your sign-in code is {code}. It expires in {minutes} minutes.\n",
    )


def send_signin_link(email: str, url: str):
    _deliver(
        email,
        "Your Family Diagram sign-in link",
        f"Open this link to sign in. It works once, lasts one day and needs no "
        f"password.\n\n{url}\n",
    )


def send_beta_request(name: str, email: str, words: str):
    _deliver(
        current_app.config["ADMIN_EMAIL"],
        f"Family Diagram beta request from {name}",
        f"Name: {name}\nEmail: {email}\n\nA few words about them and their "
        f"interest:\n{words or '(none given)'}\n",
        reply_to=email,
    )
