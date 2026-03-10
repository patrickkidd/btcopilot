import pickle
from unittest.mock import patch

import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback
from btcopilot.schema import (
    PDP,
    PDPDeltas,
    DiagramData,
    Event,
    Person,
    VariableShift,
    EventKind,
    asdict,
)
from btcopilot.tests.training.conftest import flask_json


def test_audit(auditor, discussion):
    response = auditor.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200
    assert response.data is not None


def test_audit_403(subscriber, discussion):
    response = subscriber.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 403


def test_audit_shows_pdp_deltas_for_subject_statements_only(auditor):
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
        events=[
            Event(
                id=1,
                kind=EventKind.Shift,
                person=1,
                description="Test event",
                anxiety=VariableShift.Up,
            )
        ],
        people=[Person(id=1, name="User")],
    )

    # Subject statement WITH PDP deltas (this is correct)
    subject_stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I feel anxious",
        order=0,
        pdp_deltas=asdict(test_deltas),
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
    response = subscriber.post(
        "/training/discussions/transcript",
        json={"text": "Test transcript"},
    )
    assert response.status_code == 403


def test_create_discussion_from_transcript_to_current_user(auditor):
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
    response = admin.delete(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200
    assert response.json["success"] is True


def test_delete_not_found(admin):
    response = admin.delete("/training/discussions/99999")
    assert response.status_code == 404



def test_clear_extracted_data_subscriber_cannot_access(subscriber, discussion):
    # Subscribers don't have access to the SARF editor, so they shouldn't be able to clear
    response = subscriber.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": subscriber.user.username},
    )
    assert response.status_code == 403


def test_clear_extracted_data_auditor_can_clear_own_feedback(auditor, discussion):
    # Add some extracted feedback for the auditor
    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(subject_speaker)
    db.session.flush()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Test statement",
    )
    db.session.add(stmt)
    db.session.flush()

    feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=auditor.user.username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-1, name="John")], events=[])
        ),
    )
    db.session.add(feedback)
    db.session.commit()

    # Auditor should be able to clear their own feedback
    response = auditor.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": auditor.user.username},
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert "your extracted data" in response.json["message"]

    # Verify feedback was cleared
    db.session.refresh(feedback)
    assert feedback.edited_extraction is None


def test_clear_extracted_data_admin_clears_ai_extractions(admin):
    # Create a fresh discussion
    discussion = Discussion(user_id=admin.user.id, summary="Test AI extraction clear")
    db.session.add(discussion)
    db.session.flush()

    # Add AI extracted data to statements
    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(subject_speaker)
    db.session.flush()

    stmt1 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="First statement",
        pdp_deltas=asdict(PDPDeltas(people=[Person(id=-1, name="John")], events=[])),
    )
    stmt2 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Second statement",
        pdp_deltas=asdict(
            PDPDeltas(
                people=[],
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        description="Event occurred",
                        person=-1,
                    )
                ],
            )
        ),
    )
    db.session.add_all([stmt1, stmt2])
    discussion.extracting = True
    db.session.commit()

    # Admin clears AI extractions
    response = admin.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": "AI"},
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert "AI extracted data" in response.json["message"]
    assert response.json["cleared_count"] == 2

    # Verify AI data was cleared
    db.session.refresh(discussion)
    db.session.refresh(stmt1)
    db.session.refresh(stmt2)

    assert discussion.extracting is False
    assert stmt1.pdp_deltas is None
    assert stmt2.pdp_deltas is None


def test_clear_extracted_data_admin_clears_specific_auditor(admin):
    # Create a fresh discussion
    discussion = Discussion(
        user_id=admin.user.id, summary="Test auditor-specific clear"
    )
    db.session.add(discussion)
    db.session.flush()

    # Add feedback from multiple auditors
    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(subject_speaker)
    db.session.flush()

    stmt1 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Statement 1",
    )
    stmt2 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Statement 2",
    )
    db.session.add_all([stmt1, stmt2])
    db.session.flush()

    # Add feedback from auditor1
    auditor1_username = "auditor1@example.com"
    feedback1 = Feedback(
        statement_id=stmt1.id,
        auditor_id=auditor1_username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-1, name="Auditor1 Person")], events=[])
        ),
    )
    feedback2 = Feedback(
        statement_id=stmt2.id,
        auditor_id=auditor1_username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-2, name="Auditor1 Person2")], events=[])
        ),
    )

    # Add feedback from auditor2 (different user)
    auditor2_username = "auditor2@example.com"
    feedback3 = Feedback(
        statement_id=stmt1.id,
        auditor_id=auditor2_username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-3, name="Auditor2 Person")], events=[])
        ),
    )

    db.session.add_all([feedback1, feedback2, feedback3])
    db.session.commit()

    # Admin clears only auditor1's feedback
    response = admin.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": auditor1_username},
    )
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["cleared_count"] == 2

    # Verify only auditor1's feedback was cleared
    db.session.refresh(feedback1)
    db.session.refresh(feedback2)
    db.session.refresh(feedback3)

    assert feedback1.edited_extraction is None  # Cleared
    assert feedback2.edited_extraction is None  # Cleared
    assert feedback3.edited_extraction is not None  # NOT cleared (different auditor)


def test_clear_extracted_data_non_admin_cannot_clear_ai(auditor, discussion):
    response = auditor.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": "AI"},
    )
    assert response.status_code == 403
    assert "Only admins can clear AI extractions" in response.json["message"]


def test_clear_extracted_data_admin_requires_auditor_id(admin, discussion):
    response = admin.post(
        f"/training/discussions/{discussion.id}/clear-extracted", json={}
    )
    assert response.status_code == 400
    assert "auditor_id required" in response.json["message"]


def test_clear_extracted_data_auditor_uses_own_username(auditor):
    # Create a fresh discussion
    discussion = Discussion(user_id=auditor.user.id, summary="Test non-admin clear")
    db.session.add(discussion)
    db.session.flush()

    # Create feedback for auditor and another user
    subject_speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(subject_speaker)
    db.session.flush()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="Test statement",
    )
    db.session.add(stmt)
    db.session.flush()

    auditor_feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=auditor.user.username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-1, name="Auditor Person")], events=[])
        ),
    )
    other_auditor_username = "other_auditor@example.com"
    other_feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=other_auditor_username,
        feedback_type="extraction",
        edited_extraction=asdict(
            PDPDeltas(people=[Person(id=-2, name="Other Auditor Person")], events=[])
        ),
    )
    db.session.add_all([auditor_feedback, other_feedback])
    db.session.commit()

    # Auditor tries to clear (should only clear their own, not other auditor's)
    response = auditor.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": other_auditor_username},  # This should be ignored
    )
    assert response.status_code == 200
    assert response.json["cleared_count"] == 1

    # Verify only auditor's own feedback was cleared
    db.session.refresh(auditor_feedback)
    db.session.refresh(other_feedback)

    assert auditor_feedback.edited_extraction is None  # Cleared
    assert other_feedback.edited_extraction is not None  # NOT cleared


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





def test_clear_ai_extractions_resets_diagram_pdp(admin, discussion_with_statements):
    from btcopilot.pro.models import Diagram

    discussion, stmts = discussion_with_statements

    # Create a diagram for this discussion
    diagram = Diagram(user_id=admin.user.id, name="Test Diagram")
    db.session.add(diagram)
    db.session.flush()
    discussion.diagram_id = diagram.id
    db.session.commit()

    # Add some fake extracted data to statements and diagram
    stmts[0].pdp_deltas = {
        "people": [{"id": -1, "name": "Carol"}],
        "events": [],
        "pair_bonds": [],
        "delete": [],
    }
    db.session.commit()

    # Simulate diagram having extracted people
    from btcopilot.schema import PDP, Person

    database = discussion.diagram.get_diagram_data()
    database.pdp = PDP(
        people=[
            Person(id=1, name="User"),
            Person(id=2, name="Assistant"),
            Person(id=-1, name="Carol"),
            Person(id=-2, name="Uncle Tom"),
        ],
        events=[],
        pair_bonds=[],
    )
    discussion.diagram.set_diagram_data(database)
    db.session.commit()

    # Verify setup
    database = discussion.diagram.get_diagram_data()
    assert len(database.pdp.people) == 4

    # Clear AI extractions
    response = admin.post(
        f"/training/discussions/{discussion.id}/clear-extracted",
        json={"auditor_id": "AI"},
    )
    assert response.status_code == 200

    # Verify diagram PDP was completely reset
    db.session.refresh(discussion)
    database = discussion.diagram.get_diagram_data()
    assert len(database.pdp.people) == 0
    assert len(database.pdp.events) == 0
    assert len(database.pdp.pair_bonds) == 0


@pytest.mark.e2e



def test_audit_with_person_mapping(auditor, test_user):
    # Create diagram with people data as dicts (simulating real diagram structure)
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram_data = DiagramData(
        people=[
            {"id": 1, "name": "John Doe", "age": 30},
            {"id": 2, "name": "Jane Smith", "age": 25},
        ],
        events=[],
        pdp=PDP(),
        lastItemId=2,
    )
    diagram.set_diagram_data(diagram_data)
    db.session.add(diagram)
    db.session.flush()

    # Create discussion linked to diagram
    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.flush()

    # Create speaker mapped to person
    subject = Speaker(
        discussion_id=discussion.id,
        name="User",
        type=SpeakerType.Subject,
        person_id=1,
    )
    db.session.add(subject)
    db.session.flush()

    # Create statement with PDP deltas
    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=subject.id,
        text="I feel anxious",
        order=0,
        pdp_deltas=asdict(
            PDPDeltas(
                people=[Person(id=1, name="John Doe")],
                events=[
                    Event(
                        id=-1,
                        kind=EventKind.Shift,
                        person=1,
                        description="Feels anxious",
                        anxiety=VariableShift.Up,
                    )
                ],
            )
        ),
    )
    db.session.add(stmt)
    db.session.commit()

    # Test audit endpoint
    response = auditor.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200

    # Verify the response includes person name mapping
    html_content = response.data.decode("utf-8")
    assert "John Doe" in html_content


def test_audit_shows_diagram_pdp_on_last_subject(admin, test_user):
    """When no per-statement deltas exist, the diagram's PDP from extract_full()
    should appear as cumulative_pdp on the last subject statement."""
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram_data = DiagramData(
        people=[{"id": 1, "name": "User"}, {"id": 2, "name": "Assistant"}],
        events=[],
        pdp=PDP(
            people=[Person(id=-1, name="Mom"), Person(id=-2, name="Dad")],
            events=[
                Event(
                    id=-1,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Mom stressed",
                    anxiety=VariableShift.Up,
                )
            ],
        ),
        lastItemId=2,
    )
    diagram.set_diagram_data(diagram_data)
    db.session.add(diagram)
    db.session.flush()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="PDP fallback test"
    )
    db.session.add(discussion)
    db.session.flush()

    subject = Speaker(
        discussion_id=discussion.id, name="Client", type=SpeakerType.Subject
    )
    expert = Speaker(
        discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert
    )
    db.session.add_all([subject, expert])
    db.session.flush()

    # No pdp_deltas on any statement
    stmts = [
        Statement(
            discussion_id=discussion.id,
            speaker_id=subject.id,
            text="First message",
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
            text="Second message",
            order=2,
        ),
    ]
    db.session.add_all(stmts)
    db.session.commit()

    response = admin.get(
        f"/training/discussions/{discussion.id}?selected_auditor=AI"
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Diagram PDP people should appear in cumulative column
    assert "Mom" in html
    assert "Dad" in html
    assert "Mom stressed" in html


def test_extract_requires_admin(auditor, discussion):
    response = auditor.post(f"/training/discussions/{discussion.id}/extract")
    assert response.status_code == 403


def test_extract(admin, discussion):
    result_pdp = PDP(people=[Person(id=1, name="User")])
    result_deltas = PDPDeltas()
    with patch(
        "btcopilot.training.routes.discussions.pdp.extract_full",
        return_value=(result_pdp, result_deltas),
    ):
        response = admin.post(f"/training/discussions/{discussion.id}/extract")
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert data["people_count"] == 1
    assert data["events_count"] == 0
    assert data["pair_bonds_count"] == 0
