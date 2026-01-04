import pytest
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.tests.training.conftest import set_test_session


def test_progress_endpoint(auditor, discussion):
    """Test the extraction progress endpoint returns correct counts"""
    # Get initial progress
    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    assert "total" in data
    assert "processed" in data
    assert "pending" in data
    assert "is_processing" in data
    assert "percent_complete" in data

    # Should have 1 Subject statement total, 1 processed (has pdp_deltas)
    assert data["total"] == 1
    assert data["processed"] == 0  # Base fixture has no pdp_deltas
    assert data["pending"] == 1
    assert data["percent_complete"] == 0.0


def test_progress_with_processed_statements(auditor, discussion):
    """Test progress calculation with partially processed statements"""
    # Add pdp_deltas to the Subject statement to mark it as processed
    subject_statement = next(
        s for s in discussion.statements if s.speaker.type == SpeakerType.Subject
    )
    subject_statement.pdp_deltas = {"events": [], "people": []}

    # Add more unprocessed Subject statements
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )
    for i in range(3):
        statement = Statement(
            discussion_id=discussion.id,
            speaker_id=subject_speaker.id,
            text=f"Statement {i}",
            order=i + 10,
        )
        db.session.add(statement)
    db.session.commit()

    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    assert data["total"] == 4  # 1 original + 3 new
    assert data["processed"] == 1  # Only the first one has pdp_deltas
    assert data["pending"] == 3
    assert data["percent_complete"] == 25.0  # 1/4 = 25%


def test_progress_all_processed(auditor, discussion):
    """Test progress when all statements are processed"""
    # Mark all Subject statements as processed
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = {"events": [], "people": []}
    db.session.commit()

    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    assert data["total"] == 1
    assert data["processed"] == 1
    assert data["pending"] == 0
    assert data["is_processing"] is False
    assert data["percent_complete"] == 100.0


def test_progress_no_subject_statements(auditor, test_user):
    """Test progress when discussion has no Subject statements"""
    # Create discussion with only Expert statements
    discussion = Discussion(user_id=test_user.id, summary="Expert only")
    db.session.add(discussion)
    db.session.flush()

    expert_speaker = Speaker(
        discussion_id=discussion.id, name="Expert", type=SpeakerType.Expert
    )
    db.session.add(expert_speaker)
    db.session.flush()

    statement = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Expert response",
        order=0,
    )
    db.session.add(statement)
    db.session.commit()

    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    assert data["total"] == 0
    assert data["processed"] == 0
    assert data["pending"] == 0
    assert data["percent_complete"] == 100  # No statements = 100% complete


def test_progress_permission_denied(flask_app, discussion, test_user_2):
    """Test that users can only see progress for their own discussions"""
    # Try to access another user's discussion progress
    with flask_app.test_client(use_cookies=True) as client:
        with client.session_transaction() as sess:
            set_test_session(sess, test_user_2.id)
        response = client.get(f"/training/discussions/{discussion.id}/progress")
        assert response.status_code == 403


def test_progress_auditor_access(auditor, discussion):
    """Test that auditors can see progress for any discussion"""
    # Auditor should be able to see any user's discussion progress
    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    assert "total" in data
    assert "processed" in data


def test_progress_nonexistent_discussion(auditor):
    """Test 404 for non-existent discussion"""
    response = auditor.get("/training/discussions/99999/progress")
    assert response.status_code == 404


def test_progress_empty_statements(auditor, discussion):
    """Test progress calculation with empty statement text"""
    # Add Subject statements with empty text (should be ignored)
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )

    empty_statement = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="",  # Empty text
        order=10,
    )
    none_statement = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text=None,  # None text
        order=11,
    )
    db.session.add_all([empty_statement, none_statement])
    db.session.commit()

    response = auditor.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200

    data = response.json
    # Should still only count the 1 Subject statement with actual text
    assert data["total"] == 1
    assert data["processed"] == 0
    assert data["pending"] == 1
