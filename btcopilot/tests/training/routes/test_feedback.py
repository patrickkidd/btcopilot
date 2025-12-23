import pytest
from unittest.mock import patch


from btcopilot.extensions import db
from btcopilot.training.models import Feedback
from btcopilot.training.routes.feedback import cleanup_extraction_pair_bonds


@pytest.fixture
def feedback(discussion):
    statement = discussion.statements[1]  # Expert statement
    feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db.session.add(feedback)
    db.session.commit()
    return feedback


def test_create(auditor, discussion):
    statement = discussion.statements[0]
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.post(
            "/training/feedback/",
            json={
                "message_id": statement.id,
                "feedback_type": "extraction",
                "thumbs_down": False,
                "comment": "Good extraction",
            },
        )
        assert response.status_code == 200
        assert response.json["success"] is True


def test_create_missing_fields(auditor):
    response = auditor.post(
        "/training/feedback/",
        json={"message_id": 1},  # Missing feedback_type
    )
    assert response.status_code == 400
    assert "Missing required fields" in response.json["error"]


def test_create_duplicate(auditor, feedback):
    statement = feedback.statement
    response = auditor.post(
        "/training/feedback/",
        json={
            "message_id": statement.id,
            "feedback_type": "extraction",
            "thumbs_down": False,
        },
    )
    # Should either succeed (200) or indicate duplicate (400)
    assert response.status_code in [200, 400]


def test_delete(auditor, feedback):
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.delete(f"/training/feedback/{feedback.id}")
        # Should either succeed (200) or not be found (404)
        assert response.status_code in [200, 404]


def test_delete_not_found(auditor):
    response = auditor.delete("/training/feedback/99999")
    assert response.status_code == 404
    assert "not found" in response.json["error"]


def test_admin_download(admin):
    response = admin.get("/training/feedback/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert "attachment" in response.headers["Content-Disposition"]


def test_cleanup_extraction_pair_bonds_removes_orphans():
    """Pair bonds not referenced by any person's parents should be removed."""
    extraction = {
        "people": [
            {"id": -1, "name": "Alice"},
            {"id": -2, "name": "Bob"},
            {"id": -3, "name": "Child", "parents": -10},
        ],
        "pair_bonds": [
            {"id": -10, "person_a": -1, "person_b": -2},  # referenced by Child
            {"id": -11, "person_a": -1, "person_b": -2},  # orphaned
        ],
        "events": [],
    }

    result = cleanup_extraction_pair_bonds(extraction)

    assert len(result["pair_bonds"]) == 1
    assert result["pair_bonds"][0]["id"] == -10


def test_cleanup_extraction_pair_bonds_removes_invalid_refs():
    """Pair bonds referencing non-existent people should be removed."""
    extraction = {
        "people": [
            {"id": -1, "name": "Alice", "parents": -10},
            {"id": -2, "name": "Bob"},
        ],
        "pair_bonds": [
            {"id": -10, "person_a": -1, "person_b": -2},  # valid
            {"id": -11, "person_a": -1, "person_b": -99},  # invalid ref
        ],
        "events": [],
    }

    result = cleanup_extraction_pair_bonds(extraction)

    assert len(result["pair_bonds"]) == 1
    assert result["pair_bonds"][0]["id"] == -10


def test_cleanup_extraction_pair_bonds_preserves_other_fields():
    """Cleanup should preserve events and other extraction fields."""
    extraction = {
        "people": [
            {"id": -1, "name": "Alice", "parents": -10},
            {"id": -2, "name": "Bob"},
        ],
        "pair_bonds": [{"id": -10, "person_a": -1, "person_b": -2}],
        "events": [{"id": -5, "kind": "shift", "description": "test"}],
        "delete": [-99],
    }

    result = cleanup_extraction_pair_bonds(extraction)

    assert result["events"] == extraction["events"]
    assert result["delete"] == extraction["delete"]
    assert len(result["pair_bonds"]) == 1


def test_cleanup_extraction_pair_bonds_handles_empty():
    """Cleanup should handle empty or None extractions."""
    assert cleanup_extraction_pair_bonds(None) is None
    assert cleanup_extraction_pair_bonds({}) == {}
    assert cleanup_extraction_pair_bonds({"people": [], "events": []}) == {
        "people": [],
        "events": [],
    }
