import logging
import pytest
from unittest.mock import patch

import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback


# @pytest.mark.parametrize(
#     "endpoint,method",
#     [
#         ("/training/admin/", "GET"),
#         ("/training/feedback", "GET"),
#         ("/training/feedback/download", "GET"),
#         ("/training/admin/users/1", "PUT"),
#     ],
# )
# def tests_requires_admin(logged_in, endpoint, method, caplog):
#     """Test that all admin endpoints properly reject non-admin users"""
#     with patch("btcopilot.training.utils.check_admin_access", return_value=False):
#         with caplog.at_level(logging.ERROR):
#             try:
#                 response = logged_in.get(endpoint)
#                 # GET requests are web requests, expect redirect to login
#                 # assert response.status_code == 302
#                 # assert "/auth/login" in response.headers.get("Location", "")
#             except Exception:
#                 # Authorization failure is expected - check that 403 Forbidden error was logged
#                 assert any(
#                     "403" in record.message or "Forbidden" in record.message
#                     for record in caplog.records
#                 ), f"{[x for x in caplog.records]} did not contain '403' or 'Forbidden'"


def test_admin_dashboard(admin):
    response = admin.get("/training/admin/")
    assert response.status_code == 200
    assert response.data is not None


def test_user_update(admin, test_user):
    response = admin.put(
        f"/training/admin/users/{test_user.id}",
        json={"roles": [btcopilot.ROLE_SUBSCRIBER, btcopilot.ROLE_ADMIN]},
    )
    assert response.status_code == 200
    assert response.json["success"] is True


def test_approve_discussion(admin, test_user):
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.commit()

    stmt1 = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Statement 1",
        order=0,
    )
    stmt2 = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Statement 2",
        order=1,
    )
    db.session.add_all([stmt1, stmt2])
    db.session.commit()

    feedback1 = Feedback(
        statement_id=stmt1.id,
        auditor_id="auditor1",
        feedback_type="extraction",
        edited_extraction={"people": [{"id": -1, "name": "Person 1"}]},
    )
    feedback2 = Feedback(
        statement_id=stmt2.id,
        auditor_id="auditor1",
        feedback_type="extraction",
        edited_extraction={"people": [{"id": -2, "name": "Person 2"}]},
    )
    feedback3 = Feedback(
        statement_id=stmt1.id,
        auditor_id="auditor2",
        feedback_type="extraction",
        edited_extraction={"people": [{"id": -3, "name": "Person 3"}]},
    )
    db.session.add_all([feedback1, feedback2, feedback3])
    db.session.commit()

    response = admin.post(
        f"/training/admin/approve-discussion/{discussion.id}/auditor1"
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["approved_count"] == 2
    assert response.json["unapproved_count"] == 0

    feedback1 = Feedback.query.filter_by(
        statement_id=stmt1.id, auditor_id="auditor1", feedback_type="extraction"
    ).first()
    feedback2 = Feedback.query.filter_by(
        statement_id=stmt2.id, auditor_id="auditor1", feedback_type="extraction"
    ).first()
    feedback3 = Feedback.query.filter_by(
        statement_id=stmt1.id, auditor_id="auditor2", feedback_type="extraction"
    ).first()

    assert feedback1.approved is True
    assert feedback2.approved is True
    assert feedback3.approved is False


def test_approve_discussion_mutual_exclusivity(admin, test_user):
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.commit()

    stmt = Statement(
        discussion_id=discussion.id, speaker_id=speaker.id, text="Test", order=0
    )
    db.session.add(stmt)
    db.session.commit()

    feedback1 = Feedback(
        statement_id=stmt.id,
        auditor_id="auditor1",
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": []},
    )
    feedback2 = Feedback(
        statement_id=stmt.id,
        auditor_id="auditor2",
        feedback_type="extraction",
        approved=False,
        edited_extraction={"people": []},
    )
    db.session.add_all([feedback1, feedback2])
    db.session.commit()

    response = admin.post(
        f"/training/admin/approve-discussion/{discussion.id}/auditor2"
    )

    assert response.status_code == 200
    assert response.json["success"] is True

    feedback1 = Feedback.query.filter_by(
        statement_id=stmt.id, auditor_id="auditor1", feedback_type="extraction"
    ).first()
    feedback2 = Feedback.query.filter_by(
        statement_id=stmt.id, auditor_id="auditor2", feedback_type="extraction"
    ).first()

    assert feedback1.approved is False
    assert feedback2.approved is True


def test_export_ground_truth_all(admin, test_user):
    discussion = Discussion(user_id=test_user.id, summary="Test discussion")
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.commit()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Test statement",
        order=0,
        pdp_deltas={"people": [{"id": -1, "name": "AI Person"}]},
    )
    db.session.add(stmt)
    db.session.commit()

    feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": [{"id": -2, "name": "Human Person"}]},
    )
    db.session.add(feedback)
    db.session.commit()

    response = admin.get("/training/admin/export-ground-truth?all=true")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert "Content-Disposition" in response.headers

    data = response.json
    assert "discussions" in data
    assert len(data["discussions"]) == 1
    assert data["discussions"][0]["id"] == discussion.id
    assert "statements" in data["discussions"][0]
    assert len(data["discussions"][0]["statements"]) == 1

    exported_stmt = data["discussions"][0]["statements"][0]
    assert exported_stmt["id"] == stmt.id
    assert exported_stmt["text"] == "Test statement"
    assert "pdp_deltas" in exported_stmt
    assert "ground_truth" in exported_stmt
    assert exported_stmt["ground_truth"]["people"][0]["name"] == "Human Person"


def test_export_ground_truth_specific_discussions(admin, test_user):
    disc1 = Discussion(user_id=test_user.id, summary="Discussion 1")
    disc2 = Discussion(user_id=test_user.id, summary="Discussion 2")
    disc3 = Discussion(user_id=test_user.id, summary="Discussion 3")
    db.session.add_all([disc1, disc2, disc3])
    db.session.commit()

    speaker = Speaker(discussion_id=disc1.id, name="User", type=SpeakerType.Subject)
    db.session.add(speaker)
    db.session.commit()

    stmt = Statement(
        discussion_id=disc1.id,
        speaker_id=speaker.id,
        text="Test",
        order=0,
        pdp_deltas={"people": []},
    )
    db.session.add(stmt)
    db.session.commit()

    feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": []},
    )
    db.session.add(feedback)
    db.session.commit()

    response = admin.get(
        f"/training/admin/export-ground-truth?discussion_ids={disc1.id},{disc2.id}"
    )

    assert response.status_code == 200
    data = response.json

    assert len(data["discussions"]) == 1
    assert data["discussions"][0]["id"] == disc1.id


def test_unapprove_discussion(admin, test_user):
    """Test bulk unapprove only affects specified discussion and auditor."""
    disc1 = Discussion(user_id=test_user.id, summary="Discussion 1")
    disc2 = Discussion(user_id=test_user.id, summary="Discussion 2")
    db.session.add_all([disc1, disc2])
    db.session.commit()

    speaker1 = Speaker(discussion_id=disc1.id, name="User", type=SpeakerType.Subject)
    speaker2 = Speaker(discussion_id=disc2.id, name="User", type=SpeakerType.Subject)
    db.session.add_all([speaker1, speaker2])
    db.session.commit()

    stmt1 = Statement(
        discussion_id=disc1.id,
        speaker_id=speaker1.id,
        text="Statement in disc1",
        order=0,
    )
    stmt2 = Statement(
        discussion_id=disc2.id,
        speaker_id=speaker2.id,
        text="Statement in disc2",
        order=0,
    )
    db.session.add_all([stmt1, stmt2])
    db.session.commit()

    # Feedback for auditor1 in disc1 - should be unapproved
    fb1_d1_a1 = Feedback(
        statement_id=stmt1.id,
        auditor_id="auditor1",
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": []},
    )
    # Feedback for auditor2 in disc1 - should NOT be unapproved
    fb1_d1_a2 = Feedback(
        statement_id=stmt1.id,
        auditor_id="auditor2",
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": []},
    )
    # Feedback for auditor1 in disc2 - should NOT be unapproved (different discussion)
    fb2_d2_a1 = Feedback(
        statement_id=stmt2.id,
        auditor_id="auditor1",
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": []},
    )
    db.session.add_all([fb1_d1_a1, fb1_d1_a2, fb2_d2_a1])
    db.session.commit()

    response = admin.post(f"/training/admin/unapprove-discussion/{disc1.id}/auditor1")
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["unapproved_count"] == 1

    db.session.refresh(fb1_d1_a1)
    db.session.refresh(fb1_d1_a2)
    db.session.refresh(fb2_d2_a1)

    assert fb1_d1_a1.approved is False
    assert fb1_d1_a2.approved is True
    assert fb2_d2_a1.approved is True


def test_admin_index_with_f1_metrics(admin, test_user):
    discussion = Discussion(user_id=test_user.id, summary="Test")
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(
        discussion_id=discussion.id, name="User", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.commit()

    stmt = Statement(
        discussion_id=discussion.id,
        speaker_id=speaker.id,
        text="Test",
        order=0,
        pdp_deltas={"people": [{"id": -1, "name": "John"}]},
    )
    db.session.add(stmt)
    db.session.commit()

    feedback = Feedback(
        statement_id=stmt.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        approved=True,
        edited_extraction={"people": [{"id": -10, "name": "John"}]},
    )
    db.session.add(feedback)
    db.session.commit()

    response = admin.get("/training/admin/")

    assert response.status_code == 200
    assert b"F1 Ground Truth" in response.data or b"F1" in response.data
