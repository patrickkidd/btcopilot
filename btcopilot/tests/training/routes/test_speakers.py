import logging
import pickle

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.personal.models import Discussion, Speaker, SpeakerType


@pytest.fixture
def test_speaker(test_user):
    """Create a test speaker for testing"""
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(
        discussion_id=discussion.id,
        name="Test Speaker",
        type=SpeakerType.Subject,
        person_id=1,
    )
    db.session.add(speaker)
    db.session.commit()
    return speaker


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/training/speakers/1", "PUT"),
    ],
)
def test_requires_auditor_or_admin(subscriber, endpoint, method, caplog):
    """Test that speaker endpoints require auditor or admin roles"""
    with patch("btcopilot.training.utils.get_auditor_id", return_value="test_auditor"):
        with caplog.at_level(logging.ERROR):
            try:
                if method == "GET":
                    response = subscriber.get(endpoint)
                elif method == "POST":
                    response = subscriber.post(endpoint, json={})
                elif method == "PUT":
                    response = subscriber.put(endpoint, json={})
                elif method == "DELETE":
                    response = subscriber.delete(endpoint)

                # If we get here, the request didn't fail as expected
                # The test should fail because access should be denied
                assert response.status_code == 302
            except Exception:
                # Authorization failure is expected - check that 403 Forbidden error was logged
                assert any(
                    "403" in record.message or "Forbidden" in record.message
                    for record in caplog.records
                )


def test_update_success(auditor, test_speaker):
    """Test successful speaker update"""
    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={
            "type": "expert",
            "name": "Updated Speaker",
            "person_id": 2,
        },
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["speaker_id"] == test_speaker.id
    assert "type to expert" in response.json["updated_fields"]
    assert "name to Updated Speaker" in response.json["updated_fields"]
    assert "person_id to 2" in response.json["updated_fields"]


def test_update_invalid_type(auditor, test_speaker):
    """Test speaker update with invalid type"""
    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={"type": "invalid"},
    )
    assert response.status_code == 400
    assert "Invalid speaker type" in response.json["error"]


def test_update_not_found(auditor):
    """Test speaker update with non-existent speaker"""
    response = auditor.put(
        "/training/speakers/99999",
        json={"name": "Test"},
    )
    assert response.status_code == 404
    assert "Speaker not found" in response.json["error"]


def test_update_no_body(auditor, test_speaker):
    """Test speaker update with no request body"""
    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={},
    )
    assert response.status_code == 400
    assert "Request body is required" in response.json["error"]


def test_update_no_valid_fields(auditor, test_speaker):
    """Test speaker update with no valid fields"""
    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={"invalid_field": "value"},
    )
    assert response.status_code == 400
    assert "No valid fields to update" in response.json["error"]


def test_map_speaker_existing_person(auditor, test_speaker):
    """Test mapping speaker to existing person"""
    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={
            "person_id": 5,
        },
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert "person_id to 5" in response.json["updated_fields"]


def test_map_speaker_create_new_person(auditor, test_speaker, test_user):
    """Test mapping speaker and creating new person (with Diagram-based DiagramData)"""

    # Create a diagram for the test user
    diagram = Diagram(
        user_id=test_user.id, name="Test Diagram", data=pickle.dumps({"database": {}})
    )
    db.session.add(diagram)
    db.session.flush()

    # Create a discussion linked to the diagram
    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test Discussion"
    )
    db.session.add(discussion)
    db.session.flush()

    # Update the test speaker to belong to this discussion
    test_speaker.discussion_id = discussion.id
    db.session.commit()

    response = auditor.put(
        f"/training/speakers/{test_speaker.id}",
        json={
            "person_id": -1,  # Dummy ID to trigger person creation
            "name": "New Person",
            "birth_date": "1990-01-01",
        },
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert "New Person" in response.json["message"]
    assert response.json["person_id"] is not None

    # Verify the speaker was mapped
    db.session.refresh(test_speaker)
    assert test_speaker.person_id is not None

    # Verify the person was added to the diagram's database
    database = diagram.get_diagram_data()
    assert len(database.people) == 1
    assert database.people[0].name == "New Person"


def test_update_speaker_not_found_for_person_mapping(auditor):
    """Test mapping non-existent speaker"""
    response = auditor.put(
        "/training/speakers/99999",
        json={
            "person_id": 1,
        },
    )
    assert response.status_code == 404
    assert "Speaker not found" in response.json["error"]
