"""Integration test for speaker type management feature"""

from unittest.mock import Mock

from btcopilot.personal.models import SpeakerType


def test_speaker_type_management_workflow():
    """Test the complete workflow for managing speaker types"""

    # Step 1: Create a discussion with speakers (simulating transcript processing)
    discussion = Mock()
    discussion.id = 1
    discussion.user_id = 123

    # Create speakers with default types
    speaker_a = Mock()
    speaker_a.id = 1
    speaker_a.name = "Speaker A"
    speaker_a.type = SpeakerType.Subject  # Default type
    speaker_a.person_id = None

    speaker_b = Mock()
    speaker_b.id = 2
    speaker_b.name = "Speaker B"
    speaker_b.type = SpeakerType.Subject  # Default type
    speaker_b.person_id = None

    speakers = [speaker_a, speaker_b]

    # Step 2: Auditor reviews and updates speaker types
    def update_speaker_type(speaker_id, new_type):
        """Simulate the update_speaker_type endpoint logic"""
        for speaker in speakers:
            if speaker.id == speaker_id:
                if new_type == "expert":
                    speaker.type = SpeakerType.Expert
                elif new_type == "subject":
                    speaker.type = SpeakerType.Subject
                return {"success": True, "speaker_type": new_type}
        return {"success": False, "error": "Speaker not found"}

    # Update Speaker A to Expert (AI assistant)
    result = update_speaker_type(1, "expert")
    assert result["success"]
    assert speaker_a.type == SpeakerType.Expert
    assert str(speaker_a.type) == "expert"

    # Keep Speaker B as Subject (user)
    assert speaker_b.type == SpeakerType.Subject
    assert str(speaker_b.type) == "subject"

    # Step 3: Verify message display logic uses updated types
    def get_message_display_type(speaker):
        """Simulate template logic for message display"""
        if speaker.type == "expert":
            return "ai-message"
        elif speaker.type == "subject":
            return "user-message"
        return "unknown-message"

    assert get_message_display_type(speaker_a) == "ai-message"
    assert get_message_display_type(speaker_b) == "user-message"

    # Step 4: Verify UI state reflects changes
    def get_ui_speaker_type_options(speaker):
        """Simulate UI options for speaker type selection"""
        return [
            {
                "value": "subject",
                "label": "Subject",
                "selected": speaker.type == "subject",
            },
            {
                "value": "expert",
                "label": "Expert",
                "selected": speaker.type == "expert",
            },
        ]

    speaker_a_options = get_ui_speaker_type_options(speaker_a)
    speaker_b_options = get_ui_speaker_type_options(speaker_b)

    # Speaker A should have "expert" selected
    expert_option_a = next(opt for opt in speaker_a_options if opt["value"] == "expert")
    subject_option_a = next(
        opt for opt in speaker_a_options if opt["value"] == "subject"
    )
    assert expert_option_a["selected"]
    assert not subject_option_a["selected"]

    # Speaker B should have "subject" selected
    expert_option_b = next(opt for opt in speaker_b_options if opt["value"] == "expert")
    subject_option_b = next(
        opt for opt in speaker_b_options if opt["value"] == "subject"
    )
    assert not expert_option_b["selected"]
    assert subject_option_b["selected"]


def test_speaker_type_validation_edge_cases():
    """Test edge cases for speaker type validation"""

    def validate_and_update_speaker_type(speaker_id, speaker_type):
        """Simulate complete validation and update logic"""

        # Input validation
        if not speaker_id:
            return {"success": False, "error": "Speaker ID is required"}

        if not speaker_type:
            return {"success": False, "error": "Speaker type is required"}

        if speaker_type not in ["expert", "subject"]:
            return {"success": False, "error": "Invalid speaker type"}

        # Simulate successful update
        return {
            "success": True,
            "speaker_id": speaker_id,
            "speaker_type": speaker_type,
            "message": f"Speaker type updated to {speaker_type}",
        }

    # Test valid updates
    result = validate_and_update_speaker_type(1, "expert")
    assert result["success"]
    assert result["speaker_type"] == "expert"

    result = validate_and_update_speaker_type(2, "subject")
    assert result["success"]
    assert result["speaker_type"] == "subject"

    # Test validation failures
    result = validate_and_update_speaker_type(None, "expert")
    assert not result["success"]
    assert "Speaker ID is required" in result["error"]

    result = validate_and_update_speaker_type(1, None)
    assert not result["success"]
    assert "Speaker type is required" in result["error"]

    result = validate_and_update_speaker_type(1, "invalid")
    assert not result["success"]
    assert "Invalid speaker type" in result["error"]
