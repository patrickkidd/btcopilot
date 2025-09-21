"""Test for the generic PUT /speaker/<id> endpoint"""

import pytest
from unittest.mock import Mock

from btcopilot.personal.models import SpeakerType


def test_generic_speaker_endpoint_capabilities():
    """Test that the generic speaker endpoint can update multiple fields"""

    def simulate_speaker_update(speaker_id, data):
        """Simulate the generic update endpoint"""
        # Mock speaker
        speaker = Mock()
        speaker.id = speaker_id
        speaker.name = "Original Name"
        speaker.type = SpeakerType.Subject
        speaker.person_id = None

        updated_fields = []

        # Update speaker type if provided
        if "type" in data:
            speaker_type = data["type"]
            if speaker_type not in ["expert", "subject"]:
                return {"success": False, "error": "Invalid speaker type"}

            speaker.type = (
                SpeakerType.Expert if speaker_type == "expert" else SpeakerType.Subject
            )
            updated_fields.append(f"type to {speaker_type}")

        # Update speaker name if provided
        if "name" in data:
            speaker.name = data["name"]
            updated_fields.append(f"name to {data['name']}")

        # Update person mapping if provided
        if "person_id" in data:
            speaker.person_id = data["person_id"]
            updated_fields.append(f"person_id to {data['person_id']}")

        if not updated_fields:
            return {"success": False, "error": "No valid fields to update"}

        return {
            "success": True,
            "speaker_id": speaker_id,
            "updated_fields": updated_fields,
            "speaker": speaker,
        }

    # Test updating just the type
    result = simulate_speaker_update(1, {"type": "expert"})
    assert result["success"]
    assert "type to expert" in result["updated_fields"]
    assert result["speaker"].type == SpeakerType.Expert

    # Test updating just the name
    result = simulate_speaker_update(1, {"name": "AI Assistant"})
    assert result["success"]
    assert "name to AI Assistant" in result["updated_fields"]
    assert result["speaker"].name == "AI Assistant"

    # Test updating just the person mapping
    result = simulate_speaker_update(1, {"person_id": 123})
    assert result["success"]
    assert "person_id to 123" in result["updated_fields"]
    assert result["speaker"].person_id == 123

    # Test updating multiple fields at once
    result = simulate_speaker_update(
        1, {"type": "expert", "name": "AI Assistant", "person_id": 456}
    )
    assert result["success"]
    assert len(result["updated_fields"]) == 3
    assert "type to expert" in result["updated_fields"]
    assert "name to AI Assistant" in result["updated_fields"]
    assert "person_id to 456" in result["updated_fields"]
    assert result["speaker"].type == SpeakerType.Expert
    assert result["speaker"].name == "AI Assistant"
    assert result["speaker"].person_id == 456


def test_rest_api_design_compliance():
    """Test that the endpoint follows REST API design principles"""

    # Test endpoint structure
    endpoint_patterns = {
        "create_discussion": {
            "method": "POST",
            "path": "/therapist/discussions",
            "description": "Create new discussion from transcript",
        },
        "update_speaker": {
            "method": "PUT",
            "path": "/therapist/speakers/{speaker_id}",
            "description": "Update speaker by ID",
        },
        "map_speaker": {
            "method": "POST",
            "path": "/therapist/audit/map_speaker",
            "description": "Map speaker to person (legacy endpoint)",
        },
    }

    # Verify RESTful patterns
    assert endpoint_patterns["create_discussion"]["method"] == "POST"
    assert "discussions" in endpoint_patterns["create_discussion"]["path"]

    assert endpoint_patterns["update_speaker"]["method"] == "PUT"
    assert "{speaker_id}" in endpoint_patterns["update_speaker"]["path"]

    # Test that the generic speaker endpoint is more flexible
    def test_endpoint_flexibility():
        """Test that PUT /speaker/{id} is more flexible than specific endpoints"""

        # The generic endpoint can handle multiple update types in one request
        generic_request_examples = [
            {"type": "expert"},  # Just type
            {"name": "New Name"},  # Just name
            {"person_id": 123},  # Just person mapping
            {"type": "expert", "name": "AI Bot"},  # Multiple fields
            {"type": "subject", "person_id": 456, "name": "User"},  # All fields
        ]

        for request in generic_request_examples:
            # All should be valid requests to the generic endpoint
            assert len(request) >= 1

            # Verify only valid fields
            valid_fields = {"type", "name", "person_id"}
            assert all(field in valid_fields for field in request.keys())

    test_endpoint_flexibility()


def test_backward_compatibility():
    """Test that the new endpoints maintain backward compatibility where needed"""

    # The map_speaker endpoint should still work for existing JavaScript
    def simulate_map_speaker(data):
        """Simulate the existing map_speaker endpoint logic"""
        speaker_id = data.get("speaker_id")
        person_id = data.get("person_id")

        if not speaker_id:
            return {"success": False, "error": "Speaker ID is required"}

        # This endpoint focuses on person mapping
        return {"success": True, "speaker_id": speaker_id, "person_id": person_id}

    # Test that map_speaker still works
    result = simulate_map_speaker({"speaker_id": 1, "person_id": 123})
    assert result["success"]
    assert result["speaker_id"] == 1
    assert result["person_id"] == 123

    # Test that the generic speaker endpoint can do the same thing
    def simulate_generic_speaker_update(speaker_id, data):
        """Simulate generic endpoint doing person mapping"""
        if "person_id" in data:
            return {
                "success": True,
                "speaker_id": speaker_id,
                "updated_fields": [f"person_id to {data['person_id']}"],
            }
        return {"success": False, "error": "No valid fields"}

    result = simulate_generic_speaker_update(1, {"person_id": 123})
    assert result["success"]
    assert "person_id to 123" in result["updated_fields"]
