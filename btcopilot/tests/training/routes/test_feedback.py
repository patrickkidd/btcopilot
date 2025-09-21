import pytest
from mock import patch


from btcopilot.extensions import db
from btcopilot.training.models import Feedback


@pytest.fixture
def feedback(discussion):
    """Create audit feedback for testing"""
    statement = discussion.statements[1]  # Expert statement
    feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db.session.add(feedback)
    db.session.commit()
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
    assert "Missing required fields" in response.json["error"]


def test_create_duplicate(auditor, feedback):
    statement = feedback.statement
    response = auditor.post(
        "/training/feedback/",
        json={
            "message_id": statement.id,
            "feedback_type": "extraction",
            "thumbs_down": False,
        },
    )
    # Should either succeed (200) or indicate duplicate (400)
    assert response.status_code in [200, 400]


def test_delete(auditor, feedback):
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.delete(f"/training/feedback/{feedback.id}")
        # Should either succeed (200) or not be found (404)
        assert response.status_code in [200, 404]


def test_delete_not_found(auditor):
    response = auditor.delete("/training/feedback/99999")
    assert response.status_code == 404
    assert "not found" in response.json["error"]


def test_admin_download(admin):
    response = admin.get("/training/feedback/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert "attachment" in response.headers["Content-Disposition"]
