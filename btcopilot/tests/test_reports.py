import pytest

import btcopilot
from btcopilot import reports, toolbox
from btcopilot.models import Report, ReportKind, ReportStatus
from btcopilot.toolbox import ToolName

BUG = {
    "kind": "bug",
    "status": "sent",
    "release": "3.2026.9.29.1",
    "address": "/app/",
    "turn_id": "t1",
    "statement_id": 9100,
    "words": "The picture did not update after I told you about my sister.",
}


def post(client, body, **headers):
    return client.post("/app/reports", json=body, headers=headers or {"Sec-Fetch-Site": "same-origin"})


def test_a_bug_the_coach_offered_is_one_row_for_the_person_and_the_diagram_the_app_is_on(web, test_user):
    # R-0056
    response = post(web, BUG)
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.kind, row.status, row.user_id, row.diagram_id) == (
        ReportKind.Bug,
        ReportStatus.Sent,
        test_user.id,
        test_user.free_diagram_id,
    )
    assert (row.release, row.address, row.turn_id, row.statement_id, row.words) == (
        "3.2026.9.29.1",
        "/app/",
        "t1",
        9100,
        BUG["words"],
    )


def test_a_signed_out_page_reports_without_a_person_or_a_csrf_token(flask_app):
    # R-0056
    response = post(flask_app.test_client(), BUG)
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.user_id, row.diagram_id) == (None, None)


def test_only_a_report_posted_from_this_site_is_taken(flask_app):
    # R-0056
    client = flask_app.test_client()
    assert post(client, BUG, **{"Sec-Fetch-Site": "cross-site", "Origin": "https://example.com"}).status_code == 403
    assert post(client, BUG, Origin="https://example.com").status_code == 403
    assert post(client, BUG, Origin="http://127.0.0.1").status_code == 201
    assert Report.query.count() == 1


def test_sent_feedback_keeps_the_words(web):
    # R-0056
    response = post(
        web,
        {"kind": "feedback", "status": "sent", "release": "r", "turn_id": "t2", "words": "Bigger dots."},
    )
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.kind, row.words, row.turn_id) == (ReportKind.Feedback, "Bigger dots.", "t2")


def test_feedback_the_person_turned_down_keeps_where_it_was_and_no_words(web):
    # R-0056
    declined = {"kind": "feedback", "status": "declined", "release": "r", "turn_id": "t2", "statement_id": 9202}
    response = post(web, declined)
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.status, row.turn_id, row.statement_id, row.words) == (ReportStatus.Declined, "t2", 9202, None)
    assert post(web, dict(declined, words="Bigger dots.")).status_code == 400


def test_a_bug_is_never_turned_down_during_the_beta(web, monkeypatch):
    # R-0613
    declined = {"kind": "bug", "status": "declined", "release": "r", "turn_id": "t1", "statement_id": 9100}
    assert post(web, declined).status_code == 400
    assert Report.query.count() == 0
    monkeypatch.setattr(btcopilot, "BETA", False)
    assert post(web, declined).status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        dict(BUG, kind="turn_failed"),
        dict(BUG, source="page"),
        dict(BUG, error="TypeError: x is undefined"),
        {k: v for k, v in BUG.items() if k != "words"},
    ],
)
def test_only_a_report_of_its_own_fields_is_taken(web, body):
    # R-0056
    response = post(web, body)
    assert response.status_code == 400
    assert Report.query.count() == 0


def test_one_sender_is_held_to_a_few_reports_an_hour(flask_app, web):
    # R-0056
    for _ in range(reports.LIMIT):
        assert post(web, BUG).status_code == 201
    assert post(web, BUG).status_code == 429
    # a signed-out page elsewhere is its own sender
    assert post(flask_app.test_client(), BUG).status_code == 201


def test_the_server_breaking_writes_no_report(flask_app, web):
    # R-0056
    def boom():
        raise KeyError("Sarah")

    flask_app.add_url_rule("/app/boom", "boom", boom)
    assert web.get("/app/boom").status_code == 500
    assert Report.query.count() == 0


def test_the_report_tool_names_the_four_bug_triggers():
    # R-0056
    tool = next(one for one in toolbox.schemas() if one["name"] == ToolName.Report.value)
    for trigger in ("did not work", "did not update", "repeating", "misunderstood", "a second time", "frustration"):
        assert trigger in tool["description"]
