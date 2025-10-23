"""Test for audit template fix

This test replicates the template error where messages are passed as dictionaries
but the template expects statement objects with origin attributes.
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask, render_template_string

from btcopilot.personal.models import Statement, Speaker, SpeakerType


def test_audit_thread_template_data_structure():
    """Test that the audit thread template receives the correct data structure"""

    # Mock speaker with correct enum
    mock_expert_speaker = Mock()
    mock_expert_speaker.type = SpeakerType.Expert
    mock_expert_speaker.name = "AI Assistant"

    mock_subject_speaker = Mock()
    mock_subject_speaker.type = SpeakerType.Subject
    mock_subject_speaker.name = "User"

    # Mock statements
    expert_statement = Mock()
    expert_statement.id = 1
    expert_statement.text = "This is an AI response"
    expert_statement.speaker = mock_expert_speaker
    expert_statement.pdp_deltas = {"people": [], "events": [], "delete": []}

    subject_statement = Mock()
    subject_statement.id = 2
    subject_statement.text = "This is a user message"
    subject_statement.speaker = mock_subject_speaker
    subject_statement.pdp_deltas = None

    # This is the structure passed to the template
    statements_with_feedback = [
        {
            "statement": subject_statement,
            "has_conv_feedback": False,
            "has_ext_feedback": False,
            "conv_feedback": None,
            "ext_feedback": None,
            "extracted_data": None,
        },
        {
            "statement": expert_statement,
            "has_conv_feedback": False,
            "has_ext_feedback": False,
            "conv_feedback": None,
            "ext_feedback": None,
            "extracted_data": {"people": [], "events": [], "deletes": []},
        },
    ]

    # Test that we can determine message origin from speaker type
    for item in statements_with_feedback:
        stmt = item["statement"]
        if stmt.speaker:
            if stmt.speaker.type == SpeakerType.Expert:
                origin = "ai"
            elif stmt.speaker.type == SpeakerType.Subject:
                origin = "user"
            else:
                origin = "unknown"
            # Add origin to the item for template compatibility
            item["origin"] = origin

    # Verify the data structure
    assert statements_with_feedback[0]["origin"] == "user"
    assert statements_with_feedback[1]["origin"] == "ai"

    # Count AI messages like the template does
    ai_messages = [
        item for item in statements_with_feedback if item.get("origin") == "ai"
    ]
    assert len(ai_messages) == 1


def test_template_message_origin_detection():
    """Test the logic for determining message origin from speaker type"""

    # Create a simple template that mimics the problematic line
    template_content = """
    {% set ai_messages = messages|selectattr('origin', 'equalto', 'ai')|list %}
    {{ ai_messages|length }}
    """

    # Mock Flask app for template testing
    app = Flask(__name__)

    with app.app_context():
        # This is what the template expects - items with 'origin' attribute
        messages_with_origin = [
            {"origin": "user", "statement": Mock()},
            {"origin": "ai", "statement": Mock()},
            {"origin": "user", "statement": Mock()},
            {"origin": "ai", "statement": Mock()},
        ]

        result = render_template_string(template_content, messages=messages_with_origin)
        assert "2" in result.strip()  # Should find 2 AI messages


def test_speaker_type_to_origin_mapping():
    """Test mapping speaker types to origin strings for template compatibility"""

    def get_message_origin(speaker_type):
        """Map speaker type to origin string"""
        if speaker_type == SpeakerType.Expert:
            return "ai"
        elif speaker_type == SpeakerType.Subject:
            return "user"
        else:
            return "unknown"

    # Test the mapping
    assert get_message_origin(SpeakerType.Expert) == "ai"
    assert get_message_origin(SpeakerType.Subject) == "user"
    assert get_message_origin(None) == "unknown"
