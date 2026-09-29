import logging

from btcopilot.app import REQUEST_ID
from btcopilot.extensions import RequestIdFilter


def test_every_request_is_named_in_its_answer_and_every_line_logged_for_it(flask_app, web, caplog):
    # R-0056
    def boom():
        raise RuntimeError("broke")

    flask_app.add_url_rule("/app/boom", "boom", boom)
    lines = []
    handler = logging.Handler()
    handler.addFilter(RequestIdFilter())
    handler.emit = lines.append
    logger = logging.getLogger("btcopilot")
    logger.addHandler(handler)
    with caplog.at_level(logging.INFO, logger="btcopilot"):
        answers = [web.get("/app/version"), web.get("/app/boom")]
    logger.removeHandler(handler)
    assert [answer.status_code for answer in answers] == [200, 500]
    ids = [answer.headers[REQUEST_ID] for answer in answers]
    assert ids[0] != ids[1]
    assert {line.request_id for line in lines if line.getMessage().startswith("GET /app/")} == set(ids)
    assert [line.request_id for line in lines if line.exc_info] == [ids[1]]
