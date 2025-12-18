import logging
import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import asdict, PDP


@pytest.fixture
def discussion(test_user):
    """Create a discussion with statements for testing"""
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.commit()

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
    db.session.add_all([family_speaker, expert_speaker])
    db.session.commit()

    statement1 = Statement(
        discussion_id=discussion.id, speaker_id=family_speaker.id, text="Hello"
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Hi there",
        pdp_deltas={
            "events": [
                {
                    "id": 1,
                    "kind": "shift",
                    "person": 1,
                    "symptom": "up",
                    "description": "Feeling better",
                }
            ],
            "people": [],
            "pair_bonds": [],
        },
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    return discussion


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/training/prompts/defaults", "GET"),
        ("/training/prompts/1", "GET"),
        # ("/training/prompts/1", "POST"),
        ("/training/prompts/", "GET"),
        # ("/training/prompts/test", "POST"),
    ],
)
def test_requires_admin_or_auditor(subscriber, endpoint, method, caplog):
    """Test that prompt endpoints require admin or auditor roles"""
    with patch("btcopilot.training.utils.get_auditor_id", return_value="test_auditor"):
        with caplog.at_level(logging.ERROR):
            if method == "GET":
                response = subscriber.get(endpoint)
                assert response.status_code == 403
            elif method == "POST":
                response = subscriber.post(endpoint, json={})
                assert response.status_code == 403


def test_default_prompts(auditor):
    """Test getting default system prompts"""
    response = auditor.get("/training/prompts/defaults")
    assert response.status_code == 200
    assert response.json is not None
    assert "DATA_EXTRACTION_PROMPT" in response.json
    assert "DATA_EXTRACTION_EXAMPLES" in response.json
    assert "DATA_EXTRACTION_CONTEXT" in response.json
    assert "CONVERSATION_FLOW_PROMPT" in response.json


def test_get_message_prompts(auditor, discussion):
    """Test getting custom prompts for a message"""
    statement = discussion.statements[0]
    response = auditor.get(f"/training/prompts/{statement.id}")
    assert response.status_code == 200
    assert "custom_prompts" in response.json


def test_set_message_prompts(auditor, discussion):
    """Test setting custom prompts for a message"""
    statement = discussion.statements[0]
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


def test_test_prompts_endpoint(admin, discussion):
    """Test the prompt testing endpoint"""
    with patch("btcopilot.training.routes.prompts.ask") as ask:
        # Mock the therapist response

        mock_response = type(
            "Response", (), {"statement": "Test response", "pdp": PDP()}
        )()
        ask.return_value = mock_response

        response = admin.post(
            "/training/prompts/test",
            json={
                "discussion_id": discussion.id,
                "message": "Test message",
                "prompts": {"test_prompt": "test value"},
            },
        )
        assert response.status_code == 200
        assert response.json["success"] is True
        assert response.json["message"] == "Test response"
