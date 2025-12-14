"""Tests for GT status functionality"""

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement
from btcopilot.training.models import Feedback
from btcopilot.training.utils import get_discussion_gt_statuses, GTStatus


def test_gt_status_empty_list(flask_app):
    result = get_discussion_gt_statuses([])
    assert result == {}


def test_gt_status_no_feedbacks(flask_app):
    discussion = Discussion(user_id=1)
    db.session.add(discussion)
    db.session.commit()

    result = get_discussion_gt_statuses([discussion.id])

    assert discussion.id in result
    assert result[discussion.id]["status"] == GTStatus.None_
    assert result[discussion.id]["total"] == 0
    assert result[discussion.id]["approved"] == 0


def test_gt_status_full_approval(flask_app):
    discussion = Discussion(user_id=1)
    db.session.add(discussion)
    db.session.flush()

    statement = Statement(discussion_id=discussion.id, text="test", order=0)
    db.session.add(statement)
    db.session.flush()

    feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=True,
    )
    db.session.add(feedback)
    db.session.commit()

    result = get_discussion_gt_statuses([discussion.id])

    assert result[discussion.id]["status"] == GTStatus.Full
    assert result[discussion.id]["total"] == 1
    assert result[discussion.id]["approved"] == 1


def test_gt_status_partial_approval(flask_app):
    discussion = Discussion(user_id=1)
    db.session.add(discussion)
    db.session.flush()

    statement1 = Statement(discussion_id=discussion.id, text="test1", order=0)
    statement2 = Statement(discussion_id=discussion.id, text="test2", order=1)
    db.session.add_all([statement1, statement2])
    db.session.flush()

    feedback1 = Feedback(
        statement_id=statement1.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=True,
    )
    feedback2 = Feedback(
        statement_id=statement2.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=False,
    )
    db.session.add_all([feedback1, feedback2])
    db.session.commit()

    result = get_discussion_gt_statuses([discussion.id])

    assert result[discussion.id]["status"] == GTStatus.Partial
    assert result[discussion.id]["total"] == 2
    assert result[discussion.id]["approved"] == 1


def test_gt_status_no_approval(flask_app):
    discussion = Discussion(user_id=1)
    db.session.add(discussion)
    db.session.flush()

    statement = Statement(discussion_id=discussion.id, text="test", order=0)
    db.session.add(statement)
    db.session.flush()

    feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=False,
    )
    db.session.add(feedback)
    db.session.commit()

    result = get_discussion_gt_statuses([discussion.id])

    assert result[discussion.id]["status"] == GTStatus.None_
    assert result[discussion.id]["total"] == 1
    assert result[discussion.id]["approved"] == 0


def test_gt_status_ignores_conversation_feedback(flask_app):
    discussion = Discussion(user_id=1)
    db.session.add(discussion)
    db.session.flush()

    statement = Statement(discussion_id=discussion.id, text="test", order=0)
    db.session.add(statement)
    db.session.flush()

    # Conversation feedback should be ignored
    conversation_feedback = Feedback(
        statement_id=statement.id,
        auditor_id="test_auditor",
        feedback_type="conversation",
        approved=True,
    )
    db.session.add(conversation_feedback)
    db.session.commit()

    result = get_discussion_gt_statuses([discussion.id])

    # Should have no extraction feedbacks, so None_ status
    assert result[discussion.id]["status"] == GTStatus.None_
    assert result[discussion.id]["total"] == 0


def test_gt_status_multiple_discussions(flask_app):
    discussion1 = Discussion(user_id=1)
    discussion2 = Discussion(user_id=1)
    db.session.add_all([discussion1, discussion2])
    db.session.flush()

    statement1 = Statement(discussion_id=discussion1.id, text="test1", order=0)
    statement2 = Statement(discussion_id=discussion2.id, text="test2", order=0)
    db.session.add_all([statement1, statement2])
    db.session.flush()

    feedback1 = Feedback(
        statement_id=statement1.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=True,
    )
    feedback2 = Feedback(
        statement_id=statement2.id,
        auditor_id="test_auditor",
        feedback_type="extraction",
        approved=False,
    )
    db.session.add_all([feedback1, feedback2])
    db.session.commit()

    result = get_discussion_gt_statuses([discussion1.id, discussion2.id])

    assert result[discussion1.id]["status"] == GTStatus.Full
    assert result[discussion2.id]["status"] == GTStatus.None_
