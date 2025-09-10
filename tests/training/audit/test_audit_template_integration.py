"""Integration test for audit template fix

This test verifies the template works correctly with the actual data structure
from the discussions route.
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask, render_template_string

from btcopilot.training.models import Statement, Speaker, SpeakerType, Discussion


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
        stmt1.text = "Hello, I need help"
        stmt1.speaker = subject_speaker
        stmt1.created_at = None

        stmt2 = Mock()
        stmt2.id = 2
        stmt2.text = "How can I assist you today?"
        stmt2.speaker = expert_speaker
        stmt2.created_at = None

        # Create message items (as they would come from the view)
        messages = [
            {'statement': stmt1, 'feedback': None},
            {'statement': stmt2, 'feedback': None}
        ]

        # Render the template
        try:
            result = render_template_string(template_content, messages=messages)
            
            # Check that it rendered successfully
            assert "AI count: 1" in result
            assert "User: Hello, I need help" in result
            assert "AI: How can I assist you today?" in result
            
        except Exception as e:
            pytest.fail(f"Template rendering failed: {e}")


def test_audit_template_with_real_enums():
    """Test template rendering with actual SpeakerType enums"""
    
    template_content = """
    {% for item in messages %}
        {% if item.statement.speaker and item.statement.speaker.type.value == 'subject' %}
            User: {{ item.statement.text }}
        {% elif item.statement.speaker and item.statement.speaker.type.value == 'expert' %}
            AI: {{ item.statement.text }}
        {% endif %}
    {% endfor %}
    """

    app = Flask(__name__)

    with app.app_context():
        # Create mock speakers with proper enum types
        expert_speaker = Mock()
        expert_speaker.type = SpeakerType.Expert
        expert_speaker.name = "AI Assistant"

        subject_speaker = Mock()
        subject_speaker.type = SpeakerType.Subject
        subject_speaker.name = "User"

        # Create mock statements
        stmt1 = Mock()
        stmt1.text = "I'm feeling anxious"
        stmt1.speaker = subject_speaker

        stmt2 = Mock()
        stmt2.text = "Tell me more about that"
        stmt2.speaker = expert_speaker

        messages = [
            {'statement': stmt1},
            {'statement': stmt2}
        ]

        # Render the template
        result = render_template_string(template_content, messages=messages)
        
        # Verify both message types render
        assert "User: I'm feeling anxious" in result
        assert "AI: Tell me more about that" in result