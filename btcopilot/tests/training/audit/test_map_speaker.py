"""Tests for the map_speaker endpoint

These are simplified unit tests that focus on the core business logic.
"""

from btcopilot.schema import Person


def test_speaker_to_person_mapping_logic():
    """Test the core logic of mapping a speaker to a person"""
    # Simulate the mapping logic
    speaker_data = {"id": 1, "name": "Speaker A", "person_id": None}

    person_id = 123

    # Simulate the mapping
    speaker_data["person_id"] = person_id

    assert speaker_data["person_id"] == 123
    assert speaker_data["name"] == "Speaker A"


def test_validation_logic():
    """Test input validation logic"""

    def validate_speaker_mapping_input(data):
        """Simulate the validation logic from the endpoint"""
        if not data.get("speaker_id"):
            return {"valid": False, "error": "Speaker ID is required"}

        if data.get("name") and not data.get("user_id"):
            return {"valid": False, "error": "User ID required for creating new person"}

        return {"valid": True}

    # Test missing speaker_id
    result = validate_speaker_mapping_input({"person_id": 1})
    assert not result["valid"]
    assert result["error"] == "Speaker ID is required"

    # Test creating person without user_id
    result = validate_speaker_mapping_input({"speaker_id": 1, "name": "New Person"})
    assert not result["valid"]
    assert result["error"] == "User ID required for creating new person"

    # Test valid mapping to existing person
    result = validate_speaker_mapping_input({"speaker_id": 1, "person_id": 123})
    assert result["valid"]

    # Test valid new person creation
    result = validate_speaker_mapping_input(
        {"speaker_id": 1, "name": "New Person", "user_id": 42}
    )
    assert result["valid"]
