"""
Database utilities for training data collection.

Handles initialization and management of training-related database structures.
"""

import logging
from ..extensions import db
from .models import Discussion, Statement, Speaker, SpeakerType

_log = logging.getLogger(__name__)


def create_initial_database():
    """Create initial database with User and Assistant people for training discussions."""
    try:
        # Try to use fdserver's Database class if available
        from fdserver.therapist.database import Database, Person

        initial_database = Database()

        # Add User person (ID will be 1)
        user_person = Person(
            name="User", spouses=[], offspring=[], parents=[], confidence=1.0
        )
        initial_database.add_person(user_person)

        # Add Assistant person (ID will be 2)
        assistant_person = Person(
            name="Assistant", spouses=[], offspring=[], parents=[], confidence=1.0
        )
        initial_database.add_person(assistant_person)

        return initial_database

    except ImportError:
        # fdserver not available, return None
        _log.warning("fdserver database classes not available")
        return None


def create_discussion_with_speakers(user_id, diagram_id=None, summary="New Discussion"):
    """Create a new discussion with default User and Assistant speakers."""
    discussion = Discussion(
        user_id=user_id,
        diagram_id=diagram_id,
        summary=summary,
        speakers=[
            Speaker(name="User", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Assistant", type=SpeakerType.Expert, person_id=2),
        ],
    )
    db.session.add(discussion)
    db.session.flush()

    # Update discussion with speaker IDs for chat
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    discussion.chat_ai_speaker_id = discussion.speakers[1].id

    return discussion


def cascade_delete_training_data(diagram_id):
    """Delete all training data associated with a diagram."""
    from .models import Feedback

    # Delete feedbacks for statements in discussions of this diagram
    Feedback.query.filter(
        Feedback.statement_id.in_(
            db.session.query(Statement.id).filter(
                Statement.discussion_id.in_(
                    db.session.query(Discussion.id).filter(
                        Discussion.diagram_id == diagram_id
                    )
                )
            )
        )
    ).delete(synchronize_session=False)

    # Delete statements in discussions of this diagram
    Statement.query.filter(
        Statement.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # Delete speakers in discussions of this diagram
    Speaker.query.filter(
        Speaker.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # Delete discussions for this diagram
    Discussion.query.filter(Discussion.diagram_id == diagram_id).delete(
        synchronize_session=False
    )

    _log.info(f"Cascade deleted all training data for diagram {diagram_id}")


def get_discussions_for_diagram(diagram_id):
    """Get all discussions associated with a diagram."""
    discussions = Discussion.query.filter_by(diagram_id=diagram_id).all()
    return [
        discussion.as_dict(include=["statements", "speakers"])
        for discussion in discussions
    ]
