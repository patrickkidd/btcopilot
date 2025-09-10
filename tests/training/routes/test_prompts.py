import logging
import pytest
from mock import patch

from btcopilot.training.models import Discussion, Statement, Speaker, SpeakerType


@pytest.fixture
def discussion_with_statements(test_user, db_session):
    """Create a discussion with statements for testing"""
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db_session.add(discussion)
    db_session.commit()

    # Create speakers for the discussion
    family_speaker = Speaker(
        discussion_id=discussion.id,
        name="Family Member",
        type=SpeakerType.Subject,
        person_id=1,
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id, name="Expert", type=SpeakerType.Expert, person_id=2
    )
    db_session.add_all([family_speaker, expert_speaker])
    db_session.commit()

    statement1 = Statement(
        discussion_id=discussion.id, speaker_id=family_speaker.id, text="Hello"
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Hi there",
        pdp_deltas={"events": [{"symptom": {"shift": "better"}}]},
    )
    db_session.add_all([statement1, statement2])
    db_session.commit()

    return discussion


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/training/prompts/defaults", "GET"),
        ("/training/prompts/1", "GET"),
        ("/training/prompts/1", "POST"),
        ("/training/prompts/", "GET"),
        ("/training/prompts/test", "POST"),
    ],
)
def test_requires_admin_or_auditor(subscriber, endpoint, method, caplog):
    """Test that prompt endpoints require admin or auditor roles"""
    with caplog.at_level(logging.ERROR):
        if method == "GET":
            response = subscriber.get(endpoint)
            # GET requests are web requests, expect redirect to login
            assert response.status_code == 302
            assert "/auth/login" in response.headers.get("Location", "")
        elif method == "POST":
            response = subscriber.post(endpoint, json={})
            # POST with JSON is API request, expect 403
            assert response.status_code == 403


def test_default_prompts(auditor):
    """Test getting default system prompts"""
    response = auditor.get("/training/prompts/defaults")
    assert response.status_code == 200
    assert response.json is not None
    assert "ROLE_COACH_NOT_THERAPIST" in response.json


def test_get_message_prompts(auditor, discussion_with_statements):
    """Test getting custom prompts for a message"""
    statement = discussion_with_statements.statements[0]
    response = auditor.get(f"/training/prompts/{statement.id}")
    assert response.status_code == 200
    assert "custom_prompts" in response.json


def test_set_message_prompts(auditor, discussion_with_statements):
    """Test setting custom prompts for a message"""
    statement = discussion_with_statements.statements[0]
    custom_prompts = {"custom_prompt": "test prompt"}

    response = auditor.post(
        f"/training/prompts/{statement.id}",
        json={"custom_prompts": custom_prompts},
    )
    assert response.status_code == 200
    assert response.json["success"] is True


def test_message_prompts_not_found(auditor):
    """Test getting prompts for non-existent message"""
    response = auditor.get("/training/prompts/99999")
    assert response.status_code == 404


def test_index_page(admin, test_user):
    """Test access to prompt lab page (requires admin)"""
    # This tests the web page endpoint
    response = admin.get("/training/prompts/")
    assert response.status_code == 200


def test_test_prompts_endpoint(admin, discussion_with_statements):
    """Test the prompt testing endpoint"""
    with patch("btcopilot.training.routes.prompts.mock_ai_response") as mock_ask:
        # Mock the AI response
        mock_response = {
            "message": "Test response",
            "extraction": {"test": "data"}
        }
        mock_ask.return_value = mock_response

        response = admin.post(
            "/training/prompts/test",
            json={
                "discussion_id": discussion_with_statements.id,
                "message": "Test message",
                "prompts": {"test_prompt": "test value"},
            },
        )
        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["message"] == "Test response"