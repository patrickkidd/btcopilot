from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, AccessRight
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback


def test_delete_diagram_with_discussions_admin(admin, diagram_with_full_data):
    """Test that admin can delete diagram with discussions, statements, speakers, and feedbacks"""
    data = diagram_with_full_data
    diagram = data["diagram"]

    # Verify everything exists
    assert Diagram.query.count() == 2  # admin.user.free_diagram + our diagram
    assert Discussion.query.count() == 1
    assert Speaker.query.count() == 2
    assert Statement.query.count() == 2
    assert Feedback.query.count() == 1
    assert AccessRight.query.count() == 1

    # Delete the diagram
    response = admin.delete(f"/training/diagrams/{diagram.id}")
    assert response.status_code == 200
    assert response.json["success"] is True

    # Verify everything was deleted
    assert Diagram.query.count() == 1  # Only admin.user.free_diagram remains
    assert Discussion.query.count() == 0
    assert Speaker.query.count() == 0
    assert Statement.query.count() == 0
    assert Feedback.query.count() == 0
    assert AccessRight.query.count() == 0


def test_delete_diagram_owner_without_discussions(auditor, simple_diagram):
    """Test that diagram owner can delete their own diagram without discussions"""
    diagram = simple_diagram

    # Verify diagram exists
    assert (
        Diagram.query.filter_by(user_id=auditor.user.id).count() == 2
    )  # free_diagram + our diagram

    # Delete the diagram
    response = auditor.delete(f"/training/diagrams/{diagram.id}")
    assert response.status_code == 200
    assert response.json["success"] is True

    # Verify diagram was deleted
    assert (
        Diagram.query.filter_by(user_id=auditor.user.id).count() == 1
    )  # Only free_diagram remains


def test_delete_diagram_owner_with_discussions_denied(auditor, discussion):
    """Test that non-admin owner cannot delete diagram with discussions"""
    # Use the existing discussion fixture which uses the user's free_diagram
    diagram_id = discussion.diagram_id

    # Verify both exist (only 1 diagram - the free_diagram with discussion)
    assert Diagram.query.count() == 1  # free_diagram only
    assert Discussion.query.count() == 1

    # Try to delete the diagram
    response = auditor.delete(f"/training/diagrams/{diagram_id}")
    assert response.status_code == 400
    assert "Only admins can delete diagrams with discussions" in response.json["error"]

    # Verify nothing was deleted
    assert Diagram.query.count() == 1
    assert Discussion.query.count() == 1


def test_delete_diagram_unauthorized(auditor, test_user_2):
    """Test that user cannot delete another user's diagram"""
    from btcopilot.pro.models import Diagram
    from btcopilot.schema import DiagramData

    # Create a diagram for user 2
    diagram = Diagram(
        user_id=test_user_2.id,
        name="Other User's Diagram",
        data=b"",
    )

    # Initialize with empty database
    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    # Try to delete as auditor user
    response = auditor.delete(f"/training/diagrams/{diagram.id}")
    assert response.status_code == 403
    assert response.json["error"] == "Access denied"

    # Verify diagram still exists
    assert Diagram.query.get(diagram.id) is not None


def test_delete_diagram_not_found(admin):
    """Test 404 for non-existent diagram"""
    response = admin.delete("/training/diagrams/99999")
    assert response.status_code == 404
    assert response.json["error"] == "Diagram not found"


def test_delete_diagram_cascade_order(admin):
    """Test that deletion happens in correct cascade order to avoid foreign key issues"""
    from btcopilot.pro.models import Diagram
    from btcopilot.schema import DiagramData

    # Create complex diagram structure
    diagram = Diagram(
        user_id=admin.user.id,
        name="Complex Diagram",
        data=b"",
    )

    # Initialize with empty database
    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    # Create multiple discussions
    discussions = []
    for i in range(2):
        discussion = Discussion(
            user_id=admin.user.id,
            diagram_id=diagram.id,
            summary=f"Discussion {i}",
        )
        discussions.append(discussion)
        db.session.add(discussion)
    db.session.commit()

    # Create speakers and statements for each discussion
    for i, discussion in enumerate(discussions):
        speaker = Speaker(
            discussion_id=discussion.id,
            name=f"Speaker {i}",
            type=SpeakerType.Subject,
        )
        db.session.add(speaker)
        db.session.commit()

        statement = Statement(
            discussion_id=discussion.id,
            speaker_id=speaker.id,
            text=f"Statement {i}",
            order=0,
        )
        db.session.add(statement)
        db.session.commit()

        # Create feedback for each statement
        feedback = Feedback(
            statement_id=statement.id,
            auditor_id=admin.user.username,
            feedback_type="extraction",
            thumbs_down=False,
        )
        db.session.add(feedback)

    db.session.commit()

    # Verify all records exist
    assert Discussion.query.filter_by(diagram_id=diagram.id).count() == 2
    assert (
        Speaker.query.join(Discussion, Speaker.discussion_id == Discussion.id)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 2
    )
    assert (
        Statement.query.join(Discussion)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 2
    )
    assert (
        Feedback.query.join(Statement)
        .join(Discussion)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 2
    )

    # Delete diagram - this should cascade properly
    response = admin.delete(f"/training/diagrams/{diagram.id}")
    assert response.status_code == 200
    assert response.json["success"] is True

    # Verify all records were deleted
    assert Discussion.query.filter_by(diagram_id=diagram.id).count() == 0
    assert (
        Speaker.query.join(Discussion, Speaker.discussion_id == Discussion.id)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 0
    )
    assert (
        Statement.query.join(Discussion)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 0
    )
    assert (
        Feedback.query.join(Statement)
        .join(Discussion)
        .filter(Discussion.diagram_id == diagram.id)
        .count()
        == 0
    )
