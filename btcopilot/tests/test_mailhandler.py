import logging
import sys

from celery import current_app

import btcopilot
from btcopilot.extensions.handlers import ColorfulSMTPHandler


def test_exception_mail_names_the_site_and_the_release(flask_app):
    # R-0056
    handler = ColorfulSMTPHandler("localhost", "a@b.c", ["d@e.f"], None)
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("btcopilot", logging.ERROR, __file__, 1, "Unhandled exception: Boom", None, None)
    with flask_app.test_request_context(base_url="https://familydiagram.com", path="/app/play"):
        subject = handler.getSubject(record)
        body = handler.format(record)
    assert subject == f"[familydiagram.com/app/play {btcopilot.__version__}] Unhandled exception: Boom"
    assert body.splitlines()[0] == f"Server: familydiagram.com/app/play {btcopilot.__version__}"


def handler():
    return ColorfulSMTPHandler("localhost", "a@b.c", ["d@e.f"], None)


def test_exception_mail_names_the_worker_task(flask_app, monkeypatch):
    # R-0056
    @current_app.task(name="btcopilot.tasks.sync")
    def sync():
        return handler().origin()

    assert sync.apply().get() == f"worker btcopilot.tasks.sync {btcopilot.__version__}"


def test_exception_mail_names_the_command_or_shell(flask_app, monkeypatch):
    # R-0056
    monkeypatch.setattr(sys, "argv", ["flask", "admin", "users", "--all"])
    assert handler().origin() == f"command admin users --all {btcopilot.__version__}"
    monkeypatch.setattr(sys, "argv", [""])
    assert handler().origin() == f"shell {btcopilot.__version__}"
