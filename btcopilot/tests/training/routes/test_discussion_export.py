import json

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, SpeakerType


def test_export_success(auditor, discussion):
    """Test successful discussion export"""
    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    # Check headers
    assert response.headers["Content-Type"] == "application/json"
    assert "attachment" in response.headers["Content-Disposition"]
    assert f"discussion_{discussion.id}.json" in response.headers["Content-Disposition"]

    # Check content
    data = json.loads(response.data)
    assert data["id"] == discussion.id
    assert data["summary"] == discussion.summary
    assert "statements" in data
    assert len(data["statements"]) == len(discussion.statements)
    assert "speakers" in data
    assert len(data["speakers"]) == len(discussion.speakers)

    # Check that statements are included
    for stmt_data in data["statements"]:
        assert "id" in stmt_data
        assert "text" in stmt_data
        assert "speaker_id" in stmt_data
        assert "order" in stmt_data


def test_export_with_statements(auditor, discussion):
    """Test export includes all statement data"""
    # Add more statements to test comprehensive export
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )
    expert_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Expert
    )

    # Add Subject statement with PDP deltas
    subject_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I'm feeling anxious about my relationship",
        order=10,
        pdp_deltas={"events": [{"id": 1, "description": "anxiety"}], "people": []},
    )

    # Add Expert statement
    expert_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Can you tell me more about that?",
        order=11,
        pdp_deltas={"events": [], "people": []},
    )

    db.session.add_all([subject_stmt, expert_stmt])
    db.session.commit()

    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert len(data["statements"]) == 4  # 2 original + 2 new

    # Find our new statements in the export
    subject_exported = None
    expert_exported = None
    for stmt in data["statements"]:
        if stmt["text"] == "I'm feeling anxious about my relationship":
            subject_exported = stmt
        elif stmt["text"] == "Can you tell me more about that?":
            expert_exported = stmt

    assert subject_exported is not None
    assert expert_exported is not None

    # Check PDP deltas are included
    assert subject_exported["pdp_deltas"] is not None
    assert expert_exported["pdp_deltas"] is not None


def test_export_permission_denied(flask_app, discussion, test_user_2):
    """Test that users without auditor role cannot access export endpoint"""
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/therapist/discussions/{discussion.id}/export")
        # Users without ROLE_AUDITOR get redirected to login
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")


def test_export_auditor_access(auditor, discussion):
    """Test that auditors can export any discussion"""
    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["id"] == discussion.id


def test_export_not_found(auditor):
    """Test 404 for non-existent discussion"""
    response = auditor.get("/therapist/discussions/99999/export")
    assert response.status_code == 404


def test_export_json_format(auditor, discussion):
    """Test that exported JSON is properly formatted"""
    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    # Should be valid JSON
    data = json.loads(response.data)

    # Should have proper structure
    required_fields = ["id", "summary", "user_id", "created_at", "statements"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Statements should have proper structure
    if data["statements"]:
        stmt = data["statements"][0]
        stmt_required_fields = ["id", "text", "speaker_id", "order", "created_at"]
        for field in stmt_required_fields:
            assert field in stmt, f"Missing statement field: {field}"


def test_export_empty_statements(auditor, test_user):
    """Test export of discussion with no statements"""
    # Create discussion with no statements
    discussion = Discussion(user_id=test_user.id, summary="Empty discussion")
    db.session.add(discussion)
    db.session.commit()

    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["id"] == discussion.id
    assert data["statements"] == []


def test_export_filename_format(auditor, discussion):
    """Test that export filename follows expected format"""
    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    content_disposition = response.headers["Content-Disposition"]
    expected_filename = f"discussion_{discussion.id}.json"
    assert expected_filename in content_disposition
    assert "attachment" in content_disposition


def test_export_unicode_handling(auditor, discussion):
    """Test that export handles unicode characters properly"""
    # Add statement with unicode characters
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )
    unicode_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I'm feeling anxious about my café visit 😟",
        order=20,
    )
    db.session.add(unicode_stmt)
    db.session.commit()

    response = auditor.get(f"/therapist/discussions/{discussion.id}/export")
    assert response.status_code == 200

    # Should be valid JSON with unicode characters
    data = json.loads(response.data)

    # Find our unicode statement
    unicode_found = False
    for stmt in data["statements"]:
        if "café" in stmt["text"] and "😟" in stmt["text"]:
            unicode_found = True
            break

    assert unicode_found, "Unicode characters not properly preserved in export"
