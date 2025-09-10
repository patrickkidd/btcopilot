import pytest
from mock import patch

from btcopilot.training.models import Feedback, SpeakerType


@pytest.fixture
def feedback_fixture(discussion, db_session):
    """Create audit feedback for testing"""
    statement = discussion.statements[1]  # Expert statement
    feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db_session.add(feedback)
    db_session.commit()
    return feedback


def test_admin_feedback(admin):
    response = admin.get("/training/feedback")
    assert response.status_code == 200


def test_create(auditor, discussion):
    statement = discussion.statements[0]
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.post(
            "/training/feedback/",
            json={
                "message_id": statement.id,
                "feedback_type": "extraction",
                "thumbs_down": False,
                "comment": "Good extraction",
            },
        )
        assert response.status_code == 200
        assert response.json["success"] is True


def test_create_missing_fields(auditor):
    response = auditor.post(
        "/training/feedback/",
        json={"message_id": 1},  # Missing feedback_type
    )
    assert response.status_code == 400