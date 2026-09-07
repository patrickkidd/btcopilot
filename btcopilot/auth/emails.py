import logging

from flask import current_app
from flask_mail import Message

from btcopilot import extensions

_log = logging.getLogger(__name__)


def _deliver(recipient: str, subject: str, body: str):
    """Development never sends: the link or the code goes to the log so a
    sandbox can be driven without a mail server."""
    if current_app.config["CONFIG"] == "development":
        _log.warning(f"[dev mail] {recipient} — {subject}\n{body}")
        return
    message = Message(
        subject,
        recipients=[recipient],
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    message.body = body
    extensions.mail.send(message)


def send_invitation(email: str, url: str):
    _deliver(
        email,
        "Your Family Diagram invitation",
        f"Open this link to start. It works once and needs no password.\n\n{url}\n",
    )


def send_login_code(email: str, code: str, minutes: int):
    _deliver(
        email,
        "Your Family Diagram sign-in code",
        f"Your sign-in code is {code}. It expires in {minutes} minutes.\n",
    )
