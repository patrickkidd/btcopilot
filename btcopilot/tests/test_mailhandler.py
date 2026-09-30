import logging

import btcopilot
from btcopilot.extensions.handlers import ColorfulSMTPHandler


def test_exception_mail_names_the_site_and_the_release(flask_app):
    # R-0056
    handler = ColorfulSMTPHandler("localhost", "a@b.c", ["d@e.f"], None)
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("btcopilot", logging.ERROR, __file__, 1, "Unhandled exception: Boom", None, None)
    with flask_app.test_request_context(base_url="https://familydiagram.com"):
        subject = handler.getSubject(record)
        body = handler.format(record)
    assert subject == f"[familydiagram.com {btcopilot.__version__}] Unhandled exception: Boom"
    assert body.splitlines()[0] == f"Server: familydiagram.com {btcopilot.__version__}"
