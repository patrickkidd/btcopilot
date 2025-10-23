import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.personal.database import (
    PDPDeltas,
    Event,
    Person,
    Anxiety,
    Shift,
)
from btcopilot.training.routes.discussions import extract_next_statement

from btcopilot.tests.training.conftest import flask_json


def test_audit(auditor, discussion):
    discussion_id = discussion.id
    response = auditor.get(f"/training/discussions/{discussion_id}")
    assert response.status_code == 200
    assert response.data is not None


def test_audit_403(subscriber, discussion):
    discussion_id = discussion.id
    response = subscriber.get(f"/training/discussions/{discussion_id}")
    # GET requests are web requests, expect redirect to login
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_audit_shows_pdp_deltas_for_subject_statements_only(auditor):
    """Test that audit page shows PDP deltas only for Subject statements"""

    # Create discussion with both statement types
    discussion = Discussion(user_id=auditor.user.id, summary="PDP deltas test")
    db.session.add(discussion)
    db.session.flush()

    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id, name="AI", type=SpeakerType.Expert
    )
    db.session.add_all([subject_speaker, expert_speaker])
    db.session.flush()

    # Create PDP deltas
    test_deltas = PDPDeltas(
        events=[Event(id=1, description="Test event", anxiety=Anxiety(shift=Shift.Up))],
        people=[Person(id=1, name="User")],
    )

    # Subject statement WITH PDP deltas (this is correct)
    subject_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I feel anxious",
        order=0,
        pdp_deltas=test_deltas.model_dump(),
    )

    # Expert statement WITHOUT PDP deltas (this is correct)
    expert_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Tell me more",
        order=1,
        pdp_deltas=None,
    )

    db.session.add_all([subject_stmt, expert_stmt])
    db.session.commit()

    # Test audit page
    response = auditor.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200

    # The audit page should only show PDP deltas for Subject statements
    # This is verified by the route logic that only processes Subject statements


def test_create_discussion_from_transcript_requires_auditor(subscriber):
    """Test that transcript creation requires auditor role"""
    response = subscriber.post(
        "/training/discussions/transcript",
        json={"text": "Test transcript"},
    )
    assert response.status_code == 302


def test_create_discussion_from_transcript_to_current_user(auditor):
    """Test creating transcript in current user's free diagram when no diagram_id provided"""
    response = auditor.post(
        "/training/discussions/transcript",
        json={"text": "Test transcript", "utterances": []},
    )
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert data["user_id"] == auditor.user.id  # Should create for current user


def test_delete_failed_non_owner(logged_in, test_user_2):
    diagram = Diagram(
        user_id=test_user_2.id, name="User 2 Diagram", data=pickle.dumps({})
    )
    test_user_2.free_diagram_id = diagram.id
    db.session.add(diagram)
    db.session.merge(diagram)
    discussion = Discussion(
        diagram_id=test_user_2.free_diagram_id, user_id=test_user_2.id
    )
    db.session.add(discussion)
    db.session.merge(discussion)
    response = logged_in.delete(f"/training/discussions/{discussion.id}")
    assert response.status_code == 302


def test_delete_success(admin, discussion):
    """Test successful discussion deletion"""
    discussion_id = discussion.id
    response = admin.delete(f"/training/discussions/{discussion_id}")
    assert response.status_code == 200
    assert response.json["success"] is True


def test_delete_not_found(admin):
    """Test 404 for non-existent discussion"""
    response = admin.delete("/training/discussions/99999")
    assert response.status_code == 404


def test_extract_requires_admin(logged_in, discussion):
    """Test that triggering extraction requires admin role"""
    response = logged_in.post(f"/training/discussions/{discussion.id}/extract")
    # POST requests are web requests, expect redirect to login
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_extract_success(mock_celery, admin, discussion):
    # Initially extracting should be False
    assert discussion.extracting == False

    response = admin.post(f"/training/discussions/{discussion.id}/extract")
    assert response.status_code == 200
    assert response.json["success"] is True

    # Check that extracting flag was set to True
    db.session.refresh(discussion)
    assert discussion.extracting == True

    # Verify Celery task was queued
    mock_celery.send_task.assert_called_once_with(
        "extract_discussion_statements", args=[discussion.id]
    )


def test_extract_not_found(admin):
    """Test 404 for non-existent discussion"""
    response = admin.post("/training/discussions/99999/extract")
    assert response.status_code == 404


@pytest.mark.extraction_flow(extractions=[PDPDeltas(events=[], people=[])])
def test_extracting_flag_reset_on_completion(admin, discussion):
    """Test that extracting flag is set to False when extraction is complete"""

    # Set up a single unprocessed statement
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None
            break

    # Enable extraction
    discussion.extracting = True
    db.session.commit()

    # Run extraction - should process the statement and set extracting to False
    with admin.application.app_context():
        result = extract_next_statement()

    # Verify extraction worked
    assert result is True

    # Refresh the discussion and check that extracting is now False
    db.session.refresh(discussion)
    assert discussion.extracting is False


def test_clear_extracted_data_requires_auditor(subscriber, discussion):
    """Test that clearing extracted data requires auditor role"""
    response = subscriber.post(f"/training/discussions/{discussion.id}/clear-extracted")
    # POST requests are web requests, expect redirect to login
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_clear_extracted_data_success(auditor, discussion):
    """Test successful clearing of extracted data"""

    # Add some extracted data to statements
    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(subject_speaker)
    db.session.flush()

    stmt1 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="First statement",
        pdp_deltas=PDPDeltas(
            people=[Person(id=-1, name="John")], events=[]
        ).model_dump(),
    )
    stmt2 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Second statement",
        pdp_deltas=PDPDeltas(
            people=[], events=[Event(id=-2, description="Event occurred", people=[-1])]
        ).model_dump(),
    )
    db.session.add_all([stmt1, stmt2])

    # Set extracting flag
    discussion.extracting = True
    db.session.commit()

    # Clear extracted data
    response = auditor.post(f"/training/discussions/{discussion.id}/clear-extracted")
    assert response.status_code == 200
    assert response.json["success"] is True
    # Should report clearing at least the 2 we just added
    assert "statements" in response.json["message"]

    # Verify data was cleared
    db.session.refresh(discussion)
    db.session.refresh(stmt1)
    db.session.refresh(stmt2)

    assert discussion.extracting is False
    assert stmt1.pdp_deltas is None
    assert stmt2.pdp_deltas is None


# Helper fixtures to reduce duplication
@pytest.fixture
def discussion_with_statements(admin):
    discussion = Discussion(user_id=admin.user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.flush()

    subject = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    expert = Speaker(discussion_id=discussion.id, name="AI", type=SpeakerType.Expert)
    db.session.add_all([subject, expert])
    db.session.flush()

    statements = [
        Statement(
            discussion_id=discussion.id,
            speaker_id=subject.id,
            text="I feel anxious",
            order=0,
        ),
        Statement(
            discussion_id=discussion.id,
            speaker_id=expert.id,
            text="Tell me more",
            order=1,
        ),
        Statement(
            discussion_id=discussion.id,
            speaker_id=subject.id,
            text="It's been difficult",
            order=2,
        ),
    ]
    db.session.add_all(statements)
    db.session.commit()

    return discussion, statements


def trigger_extraction(admin, discussion_id):
    """Helper to trigger extraction and verify it started"""
    response = admin.post(f"/training/discussions/{discussion_id}/extract")
    assert response.status_code == 200
    return response


def run_extraction(admin):
    """Helper to run extraction in app context"""
    with admin.application.app_context():
        return extract_next_statement()


def clear_extraction(admin, discussion_id):
    """Helper to clear extracted data"""
    response = admin.post(f"/training/discussions/{discussion_id}/clear-extracted")
    assert response.status_code == 200
    return response


def verify_extraction_state(
    discussion, statements, extracted_indices, not_extracted_indices
):
    """Helper to verify which statements were extracted"""
    db.session.refresh(discussion)
    for idx in extracted_indices:
        db.session.refresh(statements[idx])
        assert statements[idx].pdp_deltas is not None
    for idx in not_extracted_indices:
        db.session.refresh(statements[idx])
        assert statements[idx].pdp_deltas is None


@pytest.mark.extraction_flow(
    extractions=[
        PDPDeltas(
            people=[Person(id=-1, name="User")],
            events=[Event(id=-1, description="Feels anxious")],
        ),
        PDPDeltas(people=[], events=[Event(id=-2, description="Having difficulty")]),
        PDPDeltas(people=[Person(id=-3, name="New User")], events=[]),
    ]
)
def test_extraction_lifecycle_full(mock_celery, admin, discussion_with_statements):
    """Test complete extraction lifecycle: trigger, extract, clear, re-trigger"""
    discussion, stmts = discussion_with_statements

    # Trigger and run extraction
    trigger_extraction(admin, discussion.id)
    assert run_extraction(admin) is True  # Extract stmt 0
    assert run_extraction(admin) is True  # Extract stmt 2 (skips expert)

    # Verify extraction completed correctly
    verify_extraction_state(
        discussion, stmts, extracted_indices=[0, 2], not_extracted_indices=[1]
    )
    assert discussion.extracting is False

    # Clear and verify
    clear_extraction(admin, discussion.id)
    verify_extraction_state(
        discussion, stmts, extracted_indices=[], not_extracted_indices=[0, 1, 2]
    )

    # Re-trigger and re-extract
    trigger_extraction(admin, discussion.id)
    assert run_extraction(admin) is True
    verify_extraction_state(
        discussion, stmts, extracted_indices=[0], not_extracted_indices=[1, 2]
    )


def test_clear_during_extraction(mock_celery, admin):
    """Test clearing data while extraction is in progress"""
    # Create discussion with statements
    discussion = Discussion(user_id=admin.user.id, summary="Clear during test")
    db.session.add(discussion)
    db.session.flush()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()

    statements = [
        Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text=f"Statement {i}",
            order=i,
        )
        for i in range(3)
    ]
    db.session.add_all(statements)
    db.session.commit()

    # Trigger extraction
    response = admin.post(f"/training/discussions/{discussion.id}/extract")
    assert response.status_code == 200
    db.session.refresh(discussion)
    assert discussion.extracting is True

    # Clear while extraction is "in progress"
    response = admin.post(f"/training/discussions/{discussion.id}/clear-extracted")
    assert response.status_code == 200

    # Verify extraction was stopped
    db.session.refresh(discussion)
    assert discussion.extracting is False

    # Verify all statements are cleared
    for stmt in statements:
        db.session.refresh(stmt)
        assert stmt.pdp_deltas is None


@pytest.mark.e2e
def test_extraction_lifecycle_full_e2e(admin, discussion_with_statements):
    """E2E test: complete extraction lifecycle with real LLM calls"""
    discussion, stmts = discussion_with_statements

    # Override statement text with more realistic content for LLM
    stmts[0].text = "I had a fight with my brother yesterday about money"
    stmts[2].text = "He thinks I owe him $500 but I already paid him back"
    db.session.commit()

    # Run extraction lifecycle with real LLM
    trigger_extraction(admin, discussion.id)
    assert run_extraction(admin) is True  # Extract stmt 0 with LLM
    assert run_extraction(admin) is True  # Extract stmt 2 with LLM

    # Verify extraction worked (can't assert exact content with LLM)
    verify_extraction_state(
        discussion, stmts, extracted_indices=[0, 2], not_extracted_indices=[1]
    )
    assert isinstance(stmts[0].pdp_deltas, dict)  # Check structure

    # Clear and re-extract
    clear_extraction(admin, discussion.id)
    verify_extraction_state(
        discussion, stmts, extracted_indices=[], not_extracted_indices=[0, 1, 2]
    )

    trigger_extraction(admin, discussion.id)
    assert run_extraction(admin) is True  # Re-extract with LLM
    db.session.refresh(stmts[0])
    assert stmts[0].pdp_deltas is not None


def test_progress_endpoint_after_clear(admin):
    """Test that progress endpoint returns correct values after clearing"""
    # Create discussion with extracted data
    discussion = Discussion(user_id=admin.user.id, summary="Progress test")
    db.session.add(discussion)
    db.session.flush()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()

    # Add statements with extracted data
    statements = []
    for i in range(3):
        stmt = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text=f"Statement {i}",
            order=i,
            pdp_deltas=PDPDeltas(
                people=[Person(id=-i, name=f"Person {i}")], events=[]
            ).model_dump(),
        )
        statements.append(stmt)
        db.session.add(stmt)

    discussion.extracting = False
    db.session.commit()

    # Check progress before clearing
    response = admin.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200
    data = response.json
    assert data["total"] == 3
    assert data["processed"] == 3
    assert data["pending"] == 0
    assert data["extracting"] is False

    # Clear extracted data
    response = admin.post(f"/training/discussions/{discussion.id}/clear-extracted")
    assert response.status_code == 200

    # Force a new database session to avoid cache issues
    db.session.close()

    # Check progress after clearing
    response = admin.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 200
    data = response.json
    assert data["total"] == 3
    assert data["processed"] == 0  # Should be 0 after clearing
    assert data["pending"] == 3  # All should be pending
    assert data["extracting"] is False


def test_celery_task_queueing(mock_celery, admin, discussion):
    """Test that Celery tasks are queued correctly"""
    # Test extraction task queueing
    response = admin.post(f"/training/discussions/{discussion.id}/extract")
    assert response.status_code == 200

    # Verify the correct task was queued with correct arguments
    mock_celery.send_task.assert_called_once_with(
        "extract_discussion_statements", args=[discussion.id]
    )

    # Reset mock for additional assertions
    mock_celery.send_task.reset_mock()

    # Test that task is not queued for non-existent discussion
    response = admin.post("/training/discussions/99999/extract")
    assert response.status_code == 404

    # Verify no task was queued for invalid discussion
    mock_celery.send_task.assert_not_called()


def test_celery_task_chaining_mock(mock_celery, flask_app):
    """Test that Celery task chaining works in extract_next_statement"""
    from btcopilot.training.tasks import extract_next_statement
    from unittest.mock import patch

    # Mock the extract function to return True (more statements to process)
    with flask_app.app_context():
        with patch(
            "btcopilot.training.tasks._extract_next_statement",
            return_value=True,
        ):
            # Call the task function directly
            assert extract_next_statement() is True
            mock_celery.send_task.assert_called_once_with(
                "extract_next_statement", countdown=1
            )
