import contextlib
import datetime

import pytest
from mock import patch, AsyncMock
import flask.json

import btcopilot
from btcopilot.extensions import db
from btcopilot.schema import PDPDeltas, PDP
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType

from btcopilot.tests.personal.conftest import discussion, discussions


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "extraction_flow: mock PDP extraction for testing extraction lifecycle",
    )


def set_test_session(sess, user_id):
    sess["user_id"] = user_id
    sess["logged_in_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()


@pytest.fixture
def logged_in(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def subscriber(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def auditor(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def admin(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_ADMIN
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture(autouse=True)
def extraction_flow(request):
    marker = request.node.get_closest_marker("extraction_flow")

    with contextlib.ExitStack() as stack:
        if marker is not None:
            extractions = marker.kwargs.get("extractions", [])

            if not isinstance(extractions, list):
                extractions = [extractions]

            extraction_iter = iter(extractions)

            def mock_update(*args, **kwargs):
                try:
                    result = next(extraction_iter)
                    if isinstance(result, tuple):
                        return result
                    else:
                        return (PDP(), result if result else PDPDeltas())
                except StopIteration:
                    return (PDP(), PDPDeltas())

            stack.enter_context(
                patch(
                    "btcopilot.training.routes.discussions.pdp.update",
                    AsyncMock(side_effect=mock_update),
                )
            )
            yield {"extractions": extractions}
        else:
            yield None


@pytest.fixture
def diagram_with_full_data(test_user):
    """Create a diagram with discussions, speakers, statements, feedbacks, and access rights"""
    from btcopilot.pro.models import Diagram, AccessRight
    from btcopilot.schema import DiagramData
    from btcopilot.training.models import Feedback

    diagram = Diagram(
        user_id=test_user.id,
        name="Test Diagram",
        data=b"",
    )

    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=diagram.id,
        summary="Test discussion",
    )
    db.session.add(discussion)
    db.session.commit()

    subject_speaker = Speaker(
        discussion_id=discussion.id,
        name="User",
        type=SpeakerType.Subject,
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id,
        name="AI",
        type=SpeakerType.Expert,
    )
    db.session.add_all([subject_speaker, expert_speaker])
    db.session.commit()

    statement1 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I feel anxious",
        order=0,
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Tell me more",
        order=1,
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    feedback = Feedback(
        statement_id=statement1.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db.session.add(feedback)

    access_right = AccessRight(
        diagram_id=diagram.id,
        user_id=test_user.id,
        right="read_write",
    )
    db.session.add(access_right)
    db.session.commit()

    return {
        "diagram": diagram,
        "discussion": discussion,
        "speakers": [subject_speaker, expert_speaker],
        "statements": [statement1, statement2],
        "feedback": feedback,
        "access_right": access_right,
    }


@pytest.fixture
def simple_diagram(test_user):
    """Create a simple diagram without discussions"""
    from btcopilot.pro.models import Diagram
    from btcopilot.schema import DiagramData

    diagram = Diagram(
        user_id=test_user.id,
        name="Simple Diagram",
        data=b"",
    )

    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    return diagram


def flask_json(data: dict) -> dict:
    sdata = flask.json.dumps(data)
    return flask.json.loads(sdata)
