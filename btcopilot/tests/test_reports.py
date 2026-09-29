import pytest

from btcopilot import tuning
from btcopilot.extensions import db
from btcopilot.models import Observation, ObservationKind
from btcopilot.tests.conftest import csrf_token

BUG = {
    "kind": "bug",
    "turn_id": "t1",
    "text": "My dad moved out.",
    "error": "The server broke on that one",
    "version": "2.0.0",
}


def post(web, body):
    return web.post("/app/observations", json=body, headers={"X-CSRFToken": csrf_token(web)})


def test_a_sent_bug_is_one_observation_on_the_diagram_the_app_is_on(web, test_user):
    # R-0056
    response = post(web, BUG)
    assert response.status_code == 201
    row = Observation.query.one()
    assert (row.diagram_id, row.turn_id, row.kind) == (
        test_user.free_diagram_id,
        "t1",
        ObservationKind.Bug,
    )
    assert row.detail == {k: BUG[k] for k in ("text", "error", "version")}


def test_sent_feedback_keeps_only_the_words(web):
    # R-0056
    response = post(web, {"kind": "feedback", "turn_id": "t2", "text": "Bigger dots."})
    assert response.status_code == 201
    assert Observation.query.one().detail == {"text": "Bigger dots."}


@pytest.mark.parametrize(
    "body",
    [
        dict(BUG, kind="turn_failed"),
        dict(BUG, kind="nothing"),
        {"kind": "feedback", "turn_id": "t2", "text": "Bigger dots.", "error": "x"},
    ],
)
def test_only_a_report_of_its_own_fields_is_taken(web, body):
    # R-0056
    response = post(web, body)
    assert response.status_code == 400
    assert Observation.query.count() == 0


def test_reports_stay_out_of_the_queue_patrick_rules_on(test_user):
    # R-0517
    for kind, detail in (
        (ObservationKind.Bug, {"text": "a", "error": "b", "version": "c"}),
        (ObservationKind.Feedback, {"text": "a"}),
        (ObservationKind.ToolRefused, {"reason": "show: No people were named."}),
    ):
        db.session.add(
            Observation(
                diagram_id=test_user.free_diagram_id, turn_id="t1", kind=kind, detail=detail
            )
        )
    db.session.commit()
    assert [g["kind"] for g in tuning.queue()] == [ObservationKind.ToolRefused.value]
