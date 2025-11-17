import pytest
import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram


def test_import_discussion_requires_write_access_to_diagram(auditor, test_user_2):
    """Test that importing a discussion to a diagram requires write access"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Grant read-only access to auditor
    diagram.grant_access(auditor.user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    # Try to import discussion to the diagram with read-only access
    export_data = {"id": 1, "summary": "Test Discussion", "statements": []}

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": diagram.id},
    )

    assert response.status_code == 403
    assert response.json["error"] == "Write access denied"


def test_import_discussion_allows_write_access_to_diagram(auditor, test_user_2):
    """Test that importing a discussion to a diagram works with write access"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Grant read-write access to auditor
    diagram.grant_access(auditor.user, btcopilot.ACCESS_READ_WRITE, _commit=True)

    # Import discussion to the diagram with write access
    export_data = {"id": 1, "summary": "Test Discussion", "statements": []}

    response = auditor.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": diagram.id},
    )

    assert response.status_code == 200
    assert response.json["success"] is True


def test_import_discussion_allows_admin_override(admin, test_user_2):
    """Test that admins can import discussions to any diagram regardless of access rights"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Don't grant any access to admin - they should still be able to import
    export_data = {"id": 1, "summary": "Test Discussion", "statements": []}

    response = admin.post(
        "/training/discussions/import",
        json={"discussion": export_data, "diagram_id": diagram.id},
    )

    assert response.status_code == 200
    assert response.json["success"] is True


def test_transcript_requires_write_access_to_diagram(auditor, test_user_2):
    """Test that creating a discussion from transcript requires write access"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Grant read-only access to auditor
    diagram.grant_access(auditor.user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    # Try to create discussion from transcript with read-only access
    transcript_data = {
        "text": "This is a test transcript",
        "utterances": [
            {"speaker": "A", "text": "Hello"},
            {"speaker": "B", "text": "Hi there"},
        ],
    }

    response = auditor.post(
        f"/training/discussions/transcript?diagram_id={diagram.id}&title=Test",
        json=transcript_data,
    )

    assert response.status_code == 403
    assert response.json["error"] == "Write access denied"


def test_transcript_allows_write_access_to_diagram(auditor, test_user_2):
    """Test that creating a discussion from transcript works with write access"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Grant read-write access to auditor
    diagram.grant_access(auditor.user, btcopilot.ACCESS_READ_WRITE, _commit=True)

    # Create discussion from transcript with write access
    transcript_data = {
        "text": "This is a test transcript",
        "utterances": [
            {"speaker": "A", "text": "Hello"},
            {"speaker": "B", "text": "Hi there"},
        ],
    }

    response = auditor.post(
        f"/training/discussions/transcript?diagram_id={diagram.id}&title=Test",
        json=transcript_data,
    )

    assert response.status_code == 200
    assert response.json["success"] is True


def test_transcript_allows_admin_override(admin, test_user_2):
    """Test that admins can create discussions from transcript on any diagram"""
    # Create a diagram owned by test_user_2
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Don't grant any access to admin - they should still be able to create
    transcript_data = {
        "text": "This is a test transcript",
        "utterances": [
            {"speaker": "A", "text": "Hello"},
            {"speaker": "B", "text": "Hi there"},
        ],
    }

    response = admin.post(
        f"/training/discussions/transcript?diagram_id={diagram.id}&title=Test",
        json=transcript_data,
    )

    assert response.status_code == 200
    assert response.json["success"] is True
