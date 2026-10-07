import json
import logging

ERROR = {
    "source": "error",
    "message": "TypeError: x is undefined",
    "stack": "at draw (chat.ts:12)",
    "address": "/app/",
    "release": "3.2026.10.6.1",
}


def post(client, body, **headers):
    return client.post(
        "/app/browser-errors", json=body, headers=headers or {"Sec-Fetch-Site": "same-origin"}
    )


def logged(caplog) -> list[dict]:
    records = [r for r in caplog.records if r.message.startswith("Browser error ")]
    assert {r.levelno for r in records} <= {logging.WARNING}
    return [json.loads(r.message.removeprefix("Browser error ")) for r in records]


def test_a_page_error_is_one_log_line_with_the_person(web, test_user, caplog):
    # R-0370
    with caplog.at_level(logging.WARNING, logger="btcopilot.routes.browsererrors"):
        assert post(web, ERROR).status_code == 204
    [line] = logged(caplog)
    agent = line.pop("agent")
    assert line == ERROR | {"user_id": test_user.id}
    assert agent.startswith("Werkzeug")


def test_a_signed_out_page_posts_without_a_csrf_token_but_only_from_this_site(flask_app, caplog):
    # R-0370
    client = flask_app.test_client()
    with caplog.at_level(logging.WARNING, logger="btcopilot.routes.browsererrors"):
        assert post(client, ERROR).status_code == 204
        assert post(client, ERROR, **{"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert post(client, ERROR | {"cookie": "x"}).status_code == 400
        assert post(client, ERROR | {"source": "console"}).status_code == 400
    assert [line["user_id"] for line in logged(caplog)] == [None]


def test_a_page_caught_in_a_loop_is_cut_off_without_using_up_its_reports(flask_app):
    # R-0370
    client = flask_app.test_client()
    for _ in range(20):
        post(client, ERROR)
    assert post(client, ERROR).status_code == 429
    report = {"kind": "feedback", "status": "declined", "release": "3.2026.10.6.1"}
    assert client.post("/app/reports", json=report, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 201


def test_an_error_too_large_to_be_a_real_one_is_refused(web, caplog):
    # R-0370
    with caplog.at_level(logging.WARNING, logger="btcopilot.routes.browsererrors"):
        assert post(web, ERROR | {"stack": "x" * 70_000}).status_code == 413
    assert logged(caplog) == []
