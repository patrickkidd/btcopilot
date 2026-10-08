import logging
import sys

import pytest

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
    assert subject == f"[Server: familydiagram.com/app/play {btcopilot.__version__}] Unhandled exception: Boom"
    assert body.splitlines()[0] == f"Server: familydiagram.com/app/play {btcopilot.__version__}"


def handler():
    return ColorfulSMTPHandler("localhost", "a@b.c", ["d@e.f"], None)


def test_exception_mail_names_the_worker_task(flask_app, monkeypatch):
    # R-0056
    @current_app.task(name="btcopilot.tasks.sync")
    def sync():
        return handler().origin()

    assert sync.apply().get() == f"Server: worker btcopilot.tasks.sync {btcopilot.__version__}"


@pytest.mark.parametrize(
    "argv, origin",
    [
        (["/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:8888"], "Server: gunicorn"),
        (["/app/.venv/lib/python3.11/site-packages/celery/__main__.py", "-A", "btcopilot.celery:celery", "beat"], "Server: celery beat"),
        (["/app/.venv/bin/flask", "admin", "diagrams", "regroup", "--apply"], "Script: admin diagrams regroup"),
        (["/app/.venv/bin/flask", "shell"], "Script: shell"),
        (["/app/.venv/bin/alembic", "upgrade", "head"], "Script: alembic upgrade head"),
        (["/tmp/fix_rows.py", "--dry-run"], "Script: fix_rows.py"),
        (["-c"], "Script: python -c"),
        ([""], "Script: python"),
    ],
)
def test_exception_mail_says_server_or_script(flask_app, monkeypatch, argv, origin):
    # R-0056
    monkeypatch.setattr(sys, "argv", argv)
    assert handler().origin() == f"{origin} {btcopilot.__version__}"
