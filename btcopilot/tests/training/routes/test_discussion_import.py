import json

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import (
    PDPDeltas,
    Event,
    Person,
    VariableShift,
    EventKind,
    RelationshipKind,
    asdict,
)


def create_sample_discussion_fixture():
    """Create a sample discussion using actual models for testing import"""
    # Create a temporary discussion with speakers and statements
    discussion = Discussion(
        id=999,  # Old ID that should be replaced
        summary="Imported test discussion",
        last_topic="Testing import",
        chat_user_speaker_id=1,
        chat_ai_speaker_id=2,
    )

    # Create speakers using actual models
    subject_speaker = Speaker(
        id=1, name="John", type=SpeakerType.Subject, person_id=None
    )

    expert_speaker = Speaker(
        id=2, name="AI Assistant", type=SpeakerType.Expert, person_id=None
    )

    # Create statements using actual models
    subject_statement = Statement(
        id=100,
        speaker_id=1,
        text="I'm feeling anxious about the test",
        order=0,
        pdp_deltas=None,
    )

    expert_statement = Statement(
        id=101,
        speaker_id=2,
        text="Can you tell me more about that?",
        order=1,
        pdp_deltas=asdict(PDPDeltas(events=[], people=[])),
    )

    # Build the complete fixture by exporting to dict format
    discussion_dict = discussion.as_dict()
    discussion_dict["speakers"] = [subject_speaker.as_dict(), expert_speaker.as_dict()]
    discussion_dict["statements"] = [
        subject_statement.as_dict(),
        expert_statement.as_dict(),
    ]

    return discussion_dict


def create_complex_pdp_discussion_fixture():
    """Create a discussion with complex PDP deltas for testing"""
    # Create PDP deltas using actual Pydantic models
    work_anxiety_deltas = PDPDeltas(
        events=[
            Event(
                id=1,
                kind=EventKind.Shift,
                description="Work anxiety discussion",
                anxiety=VariableShift.Up,
                functioning=VariableShift.Down,
            )
        ],
        people=[Person(id=1, name="User")],
    )

    relationship_deltas = PDPDeltas(
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Boss relationship strain",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[2],
            )
        ],
        people=[Person(id=1, name="User"), Person(id=2, name="Boss")],
    )

    # Create discussion
    discussion = Discussion(id=1, summary="PDP deltas preservation test")

    # Create speakers
    subject_speaker = Speaker(id=1, name="User", type=SpeakerType.Subject)

    expert_speaker = Speaker(id=2, name="AI", type=SpeakerType.Expert)

    # Create statements with PDP deltas - extracted data goes on Subject statements
    statements = [
        Statement(
            id=1,
            speaker_id=1,
            text="I'm feeling very anxious about my job",
            order=0,
            pdp_deltas=asdict(
                work_anxiety_deltas
            ),  # Subject statement with extracted data
        ),
        Statement(
            id=2,
            speaker_id=2,
            text="I understand your concern about work anxiety",
            order=1,
            pdp_deltas=None,  # Expert statements don't have extracted data
        ),
        Statement(
            id=3,
            speaker_id=1,
            text="Yes, my relationship with my boss is also strained",
            order=2,
            pdp_deltas=asdict(
                relationship_deltas
            ),  # Subject statement with extracted data
        ),
        Statement(
            id=4,
            speaker_id=2,
            text="Let's explore that relationship dynamic",
            order=3,
            pdp_deltas=None,  # Expert statements don't have extracted data
        ),
    ]

    # Build the complete fixture
    discussion_dict = discussion.as_dict()
    discussion_dict["speakers"] = [subject_speaker.as_dict(), expert_speaker.as_dict()]
    discussion_dict["statements"] = [stmt.as_dict() for stmt in statements]

    return discussion_dict


def create_person_mapping_fixture():
    """Create a discussion with person_id mapping"""
    discussion = Discussion(id=1, summary="Discussion with person mapping")

    speaker = Speaker(
        id=1,
        name="John Doe",
        type=SpeakerType.Subject,
        person_id=42,  # Should be preserved
    )

    statement = Statement(id=1, speaker_id=1, text="Test message", order=0)

    discussion_dict = discussion.as_dict()
    discussion_dict["speakers"] = [speaker.as_dict()]
    discussion_dict["statements"] = [statement.as_dict()]

    return discussion_dict


def create_complex_pdp_fixture():
    """Create a discussion with complex PDP deltas using Triangle relationship"""
    complex_deltas = PDPDeltas(
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Tell me more",
                relationship=RelationshipKind.Inside,
                relationshipTargets=[2],
                relationshipTriangles=[1, 3],
            )
        ],
        people=[
            Person(id=1, name="User"),
            Person(id=2, name="Mom"),
            Person(id=3, name="Dad"),
        ],
    )

    discussion = Discussion(id=1, summary="Complex PDP test")

    speakers = [
        Speaker(id=1, name="User", type=SpeakerType.Subject),
        Speaker(id=2, name="AI", type=SpeakerType.Expert),
    ]

    statements = [
        Statement(
            id=1,
            speaker_id=1,
            text="I had a fight with my mom",
            order=0,
            pdp_deltas=None,
        ),
        Statement(
            id=2,
            speaker_id=2,
            text="Tell me more",
            order=1,
            pdp_deltas=asdict(complex_deltas),
        ),
    ]

    discussion_dict = discussion.as_dict()
    discussion_dict["speakers"] = [s.as_dict() for s in speakers]
    discussion_dict["statements"] = [s.as_dict() for s in statements]

    return discussion_dict


def test_import_discussion_from_json_success(auditor):
    """Test successful import of discussion from JSON"""
    # Use fixture created from actual models
    export_data = create_sample_discussion_fixture()

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert "discussion_id" in data

    # Verify discussion was created with new ID
    discussion = Discussion.query.get(data["discussion_id"])
    assert discussion is not None
    assert discussion.id != 999  # Should have new ID
    assert discussion.summary == "Imported test discussion"
    assert discussion.last_topic == "Testing import"
    assert discussion.user_id == auditor.user.id

    # Verify speakers were created
    assert len(discussion.speakers) == 2
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )
    expert_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Expert
    )

    assert subject_speaker.name == "John"
    assert expert_speaker.name == "AI Assistant"

    # Verify chat speaker IDs were mapped
    assert discussion.chat_user_speaker_id == subject_speaker.id
    assert discussion.chat_ai_speaker_id == expert_speaker.id

    # Verify statements were created with proper speaker mapping
    assert len(discussion.statements) == 2
    stmt1 = next(s for s in discussion.statements if s.order == 0)
    stmt2 = next(s for s in discussion.statements if s.order == 1)

    assert stmt1.text == "I'm feeling anxious about the test"
    assert stmt1.speaker_id == subject_speaker.id
    assert stmt1.pdp_deltas is None

    assert stmt2.text == "Can you tell me more about that?"
    assert stmt2.speaker_id == expert_speaker.id
    assert stmt2.pdp_deltas is not None


def test_import_discussion_response_includes_statements_and_speakers(auditor):
    """Test that API response includes statements and speakers, not just discussion data"""
    export_data = create_sample_discussion_fixture()

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200
    data = response.json

    assert "statements" in data
    assert "speakers" in data
    assert len(data["statements"]) == 2
    assert len(data["speakers"]) == 2

    statement_texts = [s["text"] for s in data["statements"]]
    assert statement_texts == [
        "I'm feeling anxious about the test",
        "Can you tell me more about that?",
    ]

    speaker_names = [s["name"] for s in data["speakers"]]
    assert speaker_names == ["John", "AI Assistant"]


def test_import_discussion_with_feedback_and_approval_fields(auditor):
    """Test that feedback and approval fields are correctly imported"""
    export_data = {
        "id": 999,
        "summary": "Test discussion with feedback",
        "last_topic": "Testing",
        "chat_user_speaker_id": 1,
        "chat_ai_speaker_id": 2,
        "speakers": [
            {"id": 1, "name": "User", "type": "subject", "person_id": None},
            {"id": 2, "name": "AI", "type": "expert", "person_id": None},
        ],
        "statements": [
            {
                "id": 100,
                "speaker_id": 1,
                "text": "Test statement with feedback",
                "order": 0,
                "pdp_deltas": {"people": [], "events": [], "delete": []},
                "custom_prompts": None,
                "approved": True,
                "approved_by": "admin",
                "approved_at": "2025-10-29T19:10:38.687167",
                "exported_at": None,
                "feedbacks": [
                    {
                        "statement_id": 100,
                        "auditor_id": "1",
                        "feedback_type": "extraction",
                        "thumbs_down": False,
                        "comment": "Test comment",
                        "edited_extraction": {
                            "people": [
                                {"id": -1, "name": "Test Person", "confidence": 0.9}
                            ],
                            "events": [],
                            "deletes": [],
                        },
                        "approved": True,
                        "approved_by": "admin",
                        "approved_at": "2025-10-29T19:11:38.019394",
                        "exported_at": None,
                        "rejection_reason": None,
                    }
                ],
            }
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    statement = discussion.statements[0]

    expected_statement_fields = {
        "approved": True,
        "approved_by": "admin",
        "exported_at": None,
    }
    assert statement.approved == expected_statement_fields["approved"]
    assert statement.approved_by == expected_statement_fields["approved_by"]
    assert statement.approved_at is not None
    assert statement.exported_at == expected_statement_fields["exported_at"]

    assert len(statement.feedbacks) == 1
    feedback = statement.feedbacks[0]

    expected_feedback_fields = {
        "auditor_id": "1",
        "comment": "Test comment",
        "approved": True,
        "approved_by": "admin",
        "exported_at": None,
        "rejection_reason": None,
    }
    assert feedback.auditor_id == expected_feedback_fields["auditor_id"]
    assert feedback.comment == expected_feedback_fields["comment"]
    assert feedback.edited_extraction is not None
    assert feedback.approved == expected_feedback_fields["approved"]
    assert feedback.approved_by == expected_feedback_fields["approved_by"]
    assert feedback.approved_at is not None
    assert feedback.exported_at == expected_feedback_fields["exported_at"]
    assert feedback.rejection_reason == expected_feedback_fields["rejection_reason"]


def test_import_discussion_preserves_timestamps_and_extracting(auditor):
    """Test that created_at, updated_at, and extracting flag are preserved"""
    export_data = {
        "id": 999,
        "summary": "Test with timestamps",
        "last_topic": "Testing",
        "extracting": True,
        "chat_user_speaker_id": 1,
        "chat_ai_speaker_id": 2,
        "created_at": "2025-10-29T06:08:54.873706",
        "updated_at": "2025-10-29T07:00:00.000000",
        "speakers": [
            {
                "id": 1,
                "name": "User",
                "type": "subject",
                "person_id": None,
                "created_at": "2025-10-29T06:08:54.880759",
                "updated_at": None,
            },
        ],
        "statements": [
            {
                "id": 100,
                "speaker_id": 1,
                "text": "Test",
                "order": 0,
                "pdp_deltas": None,
                "created_at": "2025-10-29T06:08:54.891898",
                "updated_at": "2025-10-29T06:10:00.000000",
                "approved": False,
                "feedbacks": [
                    {
                        "auditor_id": "1",
                        "feedback_type": "extraction",
                        "created_at": "2025-10-29T19:10:38.687167",
                        "updated_at": "2025-10-29T19:11:38.019394",
                    }
                ],
            }
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])

    assert discussion.extracting is True
    assert discussion.created_at.isoformat().startswith("2025-10-29T06:08:54")
    assert discussion.updated_at.isoformat().startswith("2025-10-29T07:00:00")

    speaker = discussion.speakers[0]
    assert speaker.created_at.isoformat().startswith("2025-10-29T06:08:54")
    assert speaker.updated_at is None

    statement = discussion.statements[0]
    assert statement.created_at.isoformat().startswith("2025-10-29T06:08:54")
    assert statement.updated_at.isoformat().startswith("2025-10-29T06:10:00")

    feedback = statement.feedbacks[0]
    assert feedback.created_at.isoformat().startswith("2025-10-29T19:10:38")
    assert feedback.updated_at.isoformat().startswith("2025-10-29T19:11:38")


def test_import_discussion_preserves_person_mapping(auditor):
    """Test that person_id mapping is preserved during import"""
    export_data = create_person_mapping_fixture()

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    speaker = discussion.speakers[0]
    assert speaker.person_id == 42  # Person mapping preserved


def test_import_discussion_requires_auditor_role(logged_in):
    """Test that regular users cannot import discussions"""
    export_data = {"id": 1, "summary": "Test", "statements": []}

    response = logged_in.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": logged_in.user.free_diagram_id},
    )

    assert response.status_code == 403


def test_import_discussion_to_current_user_free_diagram(auditor):
    """Test importing to current user's free diagram when no diagram_id provided"""
    export_data = {"id": 1, "summary": "Test", "statements": []}

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data},
    )

    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert data["user_id"] == auditor.user.id  # Should import to current user


def test_import_discussion_validates_diagram_exists(auditor):
    """Test that import validates the target diagram exists when using diagram_id"""
    export_data = {"id": 1, "summary": "Test", "statements": []}

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": 99999},
    )

    assert response.status_code == 404
    assert response.json["error"] == "Diagram not found"


def test_import_discussion_handles_malformed_json(auditor):
    """Test that import handles malformed JSON gracefully"""
    # Missing required fields
    export_data = {"not_a_discussion": "invalid"}

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    # Should succeed but create a minimal discussion
    assert response.status_code == 200
    # The import succeeded even with minimal data


def test_import_discussion_without_speakers(auditor):
    """Test importing discussion without speakers array"""
    export_data = {
        "id": 1,
        "summary": "No speakers discussion",
        "statements": [
            {
                "id": 1,
                "speaker_id": None,
                "text": "Statement without speaker",
                "order": 0,
            }
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    assert len(discussion.speakers) == 0
    assert len(discussion.statements) == 1
    assert discussion.statements[0].speaker_id is None


def test_import_discussion_complex_pdp_deltas(auditor):
    """Test importing discussion with complex PDP deltas"""
    export_data = create_complex_pdp_fixture()

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    expert_stmt = next(s for s in discussion.statements if s.order == 1)

    assert expert_stmt.pdp_deltas is not None
    assert len(expert_stmt.pdp_deltas["events"]) == 1
    assert len(expert_stmt.pdp_deltas["people"]) == 3
    assert expert_stmt.pdp_deltas["events"][0]["description"] == "Tell me more"


def test_import_discussion_handles_duplicate_speaker_ids(auditor):
    """Test that import handles discussions with duplicate speaker IDs in statements"""
    export_data = {
        "id": 1,
        "summary": "Duplicate speaker test",
        "speakers": [{"id": 1, "name": "User", "type": "subject"}],
        "statements": [
            {"id": 1, "speaker_id": 1, "text": "First message", "order": 0},
            {
                "id": 2,
                "speaker_id": 1,
                "text": "Second message same speaker",
                "order": 1,
            },
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    assert len(discussion.speakers) == 1
    assert len(discussion.statements) == 2

    # Both statements should map to the same new speaker
    assert discussion.statements[0].speaker_id == discussion.statements[1].speaker_id


def test_import_discussion_order_fallback(auditor):
    """Test that import uses index as order if order field is missing"""
    export_data = {
        "id": 1,
        "summary": "Order test",
        "speakers": [{"id": 1, "name": "User", "type": "subject"}],
        "statements": [
            {
                "id": 1,
                "speaker_id": 1,
                "text": "First (no order field)",
                # No order field
            },
            {
                "id": 2,
                "speaker_id": 1,
                "text": "Second (no order field)",
                # No order field
            },
            {"id": 3, "speaker_id": 1, "text": "Third (has order)", "order": 10},
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    statements = sorted(discussion.statements, key=lambda s: s.order)

    assert statements[0].text == "First (no order field)"
    assert statements[0].order == 0  # Index-based
    assert statements[1].text == "Second (no order field)"
    assert statements[1].order == 1  # Index-based
    assert statements[2].text == "Third (has order)"
    assert statements[2].order == 10  # From export data


def test_import_discussion_preserves_pdp_deltas(auditor):
    """Test that importing restores PDP deltas properly"""
    # Use fixture created from actual Pydantic models
    export_data = create_complex_pdp_discussion_fixture()

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    discussion = Discussion.query.get(response.json["discussion_id"])
    statements = sorted(discussion.statements, key=lambda s: s.order)

    # Verify PDP deltas are preserved correctly
    assert len(statements) == 4

    # Subject statements should have preserved PDP deltas
    subject_statements = [
        s for s in statements if s.speaker.type == SpeakerType.Subject
    ]
    assert len(subject_statements) == 2

    # Expert statements should have no PDP deltas (extracted data is only on Subject statements)
    expert_statements = [s for s in statements if s.speaker.type == SpeakerType.Expert]
    assert len(expert_statements) == 2
    for stmt in expert_statements:
        assert stmt.pdp_deltas is None

    # First subject statement
    first_subject = next(s for s in subject_statements if s.order == 0)
    assert first_subject.pdp_deltas is not None
    assert "events" in first_subject.pdp_deltas
    assert "people" in first_subject.pdp_deltas
    assert len(first_subject.pdp_deltas["events"]) == 1
    assert len(first_subject.pdp_deltas["people"]) == 1

    # Check first event details
    event1 = first_subject.pdp_deltas["events"][0]
    assert event1["description"] == "Work anxiety discussion"
    assert "anxiety" in event1
    assert event1["anxiety"] == VariableShift.Up
    assert "functioning" in event1
    assert event1["functioning"] == VariableShift.Down

    # Second subject statement
    second_subject = next(s for s in subject_statements if s.order == 2)
    assert second_subject.pdp_deltas is not None
    assert "events" in second_subject.pdp_deltas
    assert "people" in second_subject.pdp_deltas
    assert len(second_subject.pdp_deltas["events"]) == 1
    assert len(second_subject.pdp_deltas["people"]) == 2

    # Check second event details
    event2 = second_subject.pdp_deltas["events"][0]
    assert event2["description"] == "Boss relationship strain"
    assert "relationship" in event2
    assert event2["relationship"] == RelationshipKind.Conflict.value


def test_import_discussion_handles_null_pdp_deltas(auditor):
    """Test that importing a discussion with null pdp_deltas creates proper database NULLs"""
    # Create test data with explicit null values
    json_data = {
        "id": 999,
        "summary": "Test discussion with null pdp_deltas",
        "speakers": [
            {"id": 1, "name": "Subject", "type": "subject"},
            {"id": 2, "name": "Expert", "type": "expert"},
        ],
        "statements": [
            {
                "id": 1,
                "text": "Statement with null pdp_deltas",
                "speaker_id": 1,
                "order": 0,
                "pdp_deltas": None,  # Explicit None
                "custom_prompts": None,  # Explicit None
            },
            {
                "id": 2,
                "text": "Statement without pdp_deltas field",
                "speaker_id": 2,
                "order": 1,
                # No pdp_deltas field at all
            },
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": json_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify the discussion was created

    discussion = Discussion.query.get(response.json["discussion_id"])
    assert discussion is not None
    assert len(discussion.statements) == 2

    # Check that null pdp_deltas became database NULL (Python None)
    first_statement = discussion.statements[0]
    assert first_statement.pdp_deltas is None  # Should be None, not JSON null
    assert first_statement.custom_prompts is None

    second_statement = discussion.statements[1]
    assert second_statement.pdp_deltas is None  # Should be None when field is missing


def test_import_discussion_no_extracting_when_no_processing_needed(auditor):
    """Test that importing a discussion without statements needing processing doesn't set extracting"""
    # Create test data where no statements need processing
    json_data = {
        "id": 999,
        "summary": "Test discussion not needing extraction",
        "speakers": [
            {"id": 1, "name": "Subject", "type": "subject"},
            {"id": 2, "name": "Expert", "type": "expert"},
        ],
        "statements": [
            {
                "id": 1,
                "text": "Already processed statement",
                "speaker_id": 1,
                "order": 0,
                "pdp_deltas": {"people": [], "events": []},  # Already has pdp_deltas
            },
            {
                "id": 2,
                "text": "",  # Empty text - won't be processed
                "speaker_id": 1,
                "order": 1,
            },
        ],
    }

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": json_data, "diagram_id": auditor.user.free_diagram_id},
    )

    assert response.status_code == 200

    # Verify the discussion was created with extracting=False
    discussion = Discussion.query.get(response.json["discussion_id"])
    assert discussion is not None
    assert discussion.extracting is False  # Should not be set when no processing needed


def _export_import_roundtrip(auditor, discussion_id, mode="full"):
    """Helper for export-import roundtrip testing"""
    export_response = auditor.get(
        f"/training/discussions/{discussion_id}/export?mode={mode}"
    )
    assert export_response.status_code == 200

    import_response = auditor.post(
        "/training/discussions/import",
        json={
            "discussion": export_response.json,
            "diagram_id": auditor.user.free_diagram_id,
        },
    )
    assert import_response.status_code == 200

    return Discussion.query.get(import_response.json["discussion_id"])


def test_export_import_roundtrip_statements_only(auditor):
    """Test export then import for discussion with statements only (no extractions)"""
    discussion = Discussion(
        user_id=auditor.user.id,
        diagram_id=auditor.user.free_diagram_id,
        summary="Test discussion for roundtrip",
        last_topic="Testing",
        extracting=False,
    )
    db.session.add(discussion)
    db.session.flush()

    speaker1 = Speaker(
        discussion_id=discussion.id, name="Person A", type=SpeakerType.Subject
    )
    speaker2 = Speaker(
        discussion_id=discussion.id, name="Person B", type=SpeakerType.Expert
    )
    db.session.add_all([speaker1, speaker2])
    db.session.flush()

    discussion.chat_user_speaker_id = speaker1.id
    discussion.chat_ai_speaker_id = speaker2.id

    stmt1 = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker1.id,
        text="Statement 1",
        order=0,
        pdp_deltas=None,
    )
    stmt2 = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker2.id,
        text="Statement 2",
        order=1,
        pdp_deltas=None,
    )
    db.session.add_all([stmt1, stmt2])
    db.session.commit()

    imported = _export_import_roundtrip(auditor, discussion.id, mode="statements")

    assert imported.summary == discussion.summary
    assert len(imported.statements) == 2
    assert imported.statements[0].text == "Statement 1"
    assert imported.statements[1].text == "Statement 2"
    assert imported.statements[0].pdp_deltas is None
    assert imported.statements[1].pdp_deltas is None


def test_export_import_roundtrip_with_extractions(auditor):
    """Test export then import for discussion with AI extractions"""
    discussion = Discussion(
        user_id=auditor.user.id,
        diagram_id=auditor.user.free_diagram_id,
        summary="Test with extractions",
        extracting=False,
    )
    db.session.add(discussion)
    db.session.flush()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Test statement",
        order=0,
        pdp_deltas={"people": [], "events": [], "delete": []},
    )
    db.session.add(stmt)
    db.session.commit()

    imported = _export_import_roundtrip(auditor, discussion.id, mode="full")

    assert len(imported.statements) == 1
    assert imported.statements[0].pdp_deltas is not None
    assert "people" in imported.statements[0].pdp_deltas


def test_export_import_roundtrip_with_feedback(admin):
    """Test export then import for discussion with domain expert feedback

    Uses admin user to test full export including all feedback (blind review enforcement)
    """
    from btcopilot.training.models import Feedback

    discussion = Discussion(
        user_id=admin.user.id,
        diagram_id=admin.user.free_diagram_id,
        summary="Test with feedback",
        extracting=False,
    )
    db.session.add(discussion)
    db.session.flush()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Test statement",
        order=0,
        pdp_deltas={"people": [], "events": [], "delete": []},
    )
    db.session.add(stmt)
    db.session.flush()

    feedback = Feedback(
        statement_id=stmt.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        thumbs_down=False,
        comment="Test feedback",
        edited_extraction={"people": [{"id": -1, "name": "Test"}], "events": []},
        approved=True,
        approved_by="admin",
    )
    db.session.add(feedback)
    db.session.commit()

    imported = _export_import_roundtrip(admin, discussion.id, mode="full")

    assert len(imported.statements) == 1
    assert len(imported.statements[0].feedbacks) == 1

    imported_feedback = imported.statements[0].feedbacks[0]
    assert imported_feedback.auditor_id == "test_auditor"
    assert imported_feedback.comment == "Test feedback"
    assert imported_feedback.edited_extraction is not None
    assert imported_feedback.approved is True
    assert imported_feedback.approved_by == "admin"


def test_export_blind_review_auditor_only_sees_own_feedback(auditor, test_user_2):
    """Test that auditors only see their own feedback when exporting (blind review)"""
    from btcopilot.training.models import Feedback

    discussion = Discussion(
        user_id=auditor.user.id,
        diagram_id=auditor.user.free_diagram_id,
        summary="Test blind review",
        extracting=False,
    )
    db.session.add(discussion)
    db.session.flush()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Test statement",
        order=0,
    )
    db.session.add(stmt)
    db.session.flush()

    feedback_own = Feedback(
        statement_id=stmt.id,
        auditor_id=str(auditor.user.id),
        feedback_type="extraction",
        comment="My feedback",
    )
    db.session.add(feedback_own)

    feedback_other = Feedback(
        statement_id=stmt.id,
        auditor_id=str(test_user_2.id),
        feedback_type="extraction",
        comment="Other auditor feedback",
    )
    db.session.add(feedback_other)
    db.session.commit()

    imported = _export_import_roundtrip(auditor, discussion.id, mode="full")

    assert len(imported.statements) == 1
    assert len(imported.statements[0].feedbacks) == 1
    imported_feedback = imported.statements[0].feedbacks[0]
    assert imported_feedback.auditor_id == str(auditor.user.id)
    assert imported_feedback.comment == "My feedback"
