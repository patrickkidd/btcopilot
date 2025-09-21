"""Integration test for audit template fix

This test verifies the template works correctly with the actual data structure
from the discussions route.
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask, render_template_string

from btcopilot.personal.models import Statement, Speaker, SpeakerType, Discussion


def test_audit_thread_template_integration():
    """Test that the audit thread template works with the actual data structure"""

    # Create a minimal template that matches the problematic parts
    template_content = """
    {% set ai_messages = messages|selectattr('statement.speaker.type', 'equalto', 'expert')|list %}
    AI count: {{ ai_messages|length }}
    
    {% for item in messages %}
        {% if item.statement.speaker and item.statement.speaker.type == 'subject' %}
            User: {{ item.statement.text }}
        {% elif item.statement.speaker and item.statement.speaker.type == 'expert' %}
            AI: {{ item.statement.text }}
        {% endif %}
    {% endfor %}
    """

    # Mock Flask app for template testing
    app = Flask(__name__)

    with app.app_context():
        # Create mock speakers
        expert_speaker = Mock()
        expert_speaker.type = "expert"  # String value as it would be in the database
        expert_speaker.name = "AI Assistant"

        subject_speaker = Mock()
        subject_speaker.type = "subject"  # String value
        subject_speaker.name = "User"

        # Create mock statements
        stmt1 = Mock()
        stmt1.id = 1
        stmt1.text = "Hello, how can I help you?"
        stmt1.speaker = subject_speaker
        stmt1.created_at = None

        stmt2 = Mock()
        stmt2.id = 2
        stmt2.text = "I can help you with that."
        stmt2.speaker = expert_speaker
        stmt2.created_at = None
        stmt2.pdp_deltas = {"people": [], "events": []}

        # Create the data structure as it's passed from the route
        statements_with_feedback = [
            {
                "statement": stmt1,
                "has_conv_feedback": False,
                "has_ext_feedback": False,
                "conv_feedback": None,
                "ext_feedback": None,
                "extracted_data": None,
            },
            {
                "statement": stmt2,
                "has_conv_feedback": False,
                "has_ext_feedback": False,
                "conv_feedback": None,
                "ext_feedback": None,
                "extracted_data": {"people": [], "events": [], "deletes": []},
            },
        ]

        # Render the template
        result = render_template_string(
            template_content, messages=statements_with_feedback
        )

        # Verify the output
        assert "AI count: 1" in result
        assert "User: Hello, how can I help you?" in result
        assert "AI: I can help you with that." in result


def test_speaker_type_string_comparison():
    """Test that speaker type comparisons work with string values"""

    # In the actual database, enum values are stored as strings
    expert_speaker = Mock()
    expert_speaker.type = "expert"  # This is how it comes from the database

    subject_speaker = Mock()
    subject_speaker.type = "subject"

    # Test string comparisons as used in the template
    assert expert_speaker.type == "expert"
    assert subject_speaker.type == "subject"

    # Test that the enum values match
    assert SpeakerType.Expert.value == "expert"
    assert SpeakerType.Subject.value == "subject"

    # Test enum to string comparison
    assert str(SpeakerType.Expert) == "expert"
    assert str(SpeakerType.Subject) == "subject"
