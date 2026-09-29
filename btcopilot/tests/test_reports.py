import datetime

import pytest

from btcopilot import reports
from btcopilot.extensions import db
from btcopilot.models import Report, ReportKind, ReportSource, ReportStatus

PAGE_BUG = {
    "kind": "bug",
    "status": "sent",
    "source": "page",
    "release": "3.2026.9.29.1",
    "address": "/app/people/4",
    "statement_id": 9100,
    "error": "TypeError: x is undefined",
    "frames": ["https://familydiagram.com/app/static/web/assets/index-B26jI9NK.js:1:52301"],
}


def post(client, body):
    return client.post("/app/reports", json=body)


def test_a_bug_from_the_page_is_one_row_for_the_person_and_the_diagram_the_app_is_on(web, test_user):
    # R-0056
    response = post(web, PAGE_BUG)
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.kind, row.status, row.source, row.user_id, row.diagram_id, row.count) == (
        ReportKind.Bug,
        ReportStatus.Sent,
        ReportSource.Page,
        test_user.id,
        test_user.free_diagram_id,
        1,
    )
    assert (row.release, row.address, row.statement_id, row.error, row.frames) == (
        "3.2026.9.29.1",
        "/app/people/4",
        9100,
        "TypeError: x is undefined",
        PAGE_BUG["frames"],
    )


def test_a_signed_out_page_reports_without_a_person_or_a_csrf_token(flask_app):
    # R-0056
    response = post(flask_app.test_client(), dict(PAGE_BUG, source="worker"))
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.user_id, row.diagram_id, row.source) == (None, None, ReportSource.Worker)


def test_sent_feedback_keeps_the_words(web):
    # R-0056
    response = post(
        web,
        {"kind": "feedback", "status": "sent", "release": "r", "turn_id": "t2", "words": "Bigger dots."},
    )
    assert response.status_code == 201
    row = Report.query.one()
    assert (row.kind, row.words, row.turn_id, row.source) == (ReportKind.Feedback, "Bigger dots.", "t2", None)


@pytest.mark.parametrize(
    "body",
    [
        dict(PAGE_BUG, kind="turn_failed"),
        dict(PAGE_BUG, source="server"),
        dict(PAGE_BUG, text="My dad moved out."),
        {k: v for k, v in PAGE_BUG.items() if k != "error"},
        {"kind": "feedback", "status": "sent", "release": "r", "words": "a", "error": "x"},
        {"kind": "feedback", "status": "sent", "release": "r"},
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
        assert post(web, PAGE_BUG).status_code == 201
    assert post(web, PAGE_BUG).status_code == 429
    # a signed-out page elsewhere is its own sender
    assert post(flask_app.test_client(), PAGE_BUG).status_code == 201


def test_the_same_fault_for_the_same_person_release_and_day_is_counted_on_one_row(flask_app, web):
    # R-0056
    post(web, PAGE_BUG)
    # the page's count of the repeats it held back adds to the same row
    post(web, dict(PAGE_BUG, count=3))
    rows = Report.query.all()
    assert [(row.count, row.signature) for row in rows] == [
        (4, f"TypeError: x is undefined at {PAGE_BUG['frames'][0]}")
    ]
    # the same fault on another record: its ids and quoted names are not the fault
    post(web, dict(PAGE_BUG, error="KeyError: 'Sarah' 12"))
    post(web, dict(PAGE_BUG, error="KeyError: 'Tom' 40"))
    assert Report.query.filter_by(signature=f"KeyError: '…' # at {PAGE_BUG['frames'][0]}").one().count == 2
    # another release, another person, another day: each its own row
    post(web, dict(PAGE_BUG, release="3.2026.9.30.1"))
    post(flask_app.test_client(), PAGE_BUG)
    rows[0].created_at -= datetime.timedelta(days=1)
    db.session.commit()
    post(web, PAGE_BUG)
    assert sorted(row.count for row in Report.query) == [1, 1, 1, 2, 4]
