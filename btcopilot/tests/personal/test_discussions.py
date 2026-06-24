import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import PDPDeltas, Person, Event, EventKind, asdict

from btcopilot.tests.training.conftest import flask_json


def test_create(subscriber):
    response = subscriber.post("/personal/discussions/")
    data = response.get_json()
    assert response.status_code == 200
    assert Discussion.query.count() == 1
    assert "id" in data
    assert data["user_id"] is not None
    assert data == flask_json(
        Discussion.query.first().as_dict(include=["speakers", "statements"])
    )


def test_list(subscriber, discussions):
    response = subscriber.get("/personal/discussions/")
    assert response.json == flask_json([x.as_dict() for x in discussions])


def test_get(subscriber, discussions):
    discussion = Discussion(
        user_id=subscriber.user.id,
        statements=[
            Statement(
                text="blah",
                speaker=Speaker(type=SpeakerType.Subject),
                pdp_deltas=asdict(
                    PDPDeltas(people=[Person(id=-1, name="hey")], events=[])
                ),
            ),
            Statement(
                text="blah",
                speaker=Speaker(type=SpeakerType.Subject),
                pdp_deltas=asdict(
                    PDPDeltas(
                        people=[],
                        events=[
                            Event(
                                id=-2,
                                kind=EventKind.Shift,
                                description="something happened",
                                person=-1,
                            )
                        ],
                    )
                ),
            ),
        ],
    )
    db.session.add(discussion)
    db.session.commit()
    response = subscriber.get(f"/personal/discussions/{discussion.id}")
    assert response.status_code == 200
    assert response.get_json() == flask_json(
        discussion.as_dict(include=["statements", "speakers"])
    )


def test_get_404(subscriber):
    response = subscriber.get("/personal/discussions/99999")
    assert response.status_code == 404


def test_get_unauthorized(subscriber, test_user_2):
    """Accessing another user's discussion returns 401."""
    other_discussion = Discussion(user_id=test_user_2.id, summary="Other user's")
    db.session.add(other_discussion)
    db.session.commit()

    response = subscriber.get(f"/personal/discussions/{other_discussion.id}")
    assert response.status_code == 401


# def test_get_statements(subscriber, discussion):
#     """Test getting statements for a discussion"""
#     discussion_id = discussion.id
#     response = subscriber.get(f"/personal/discussions/{discussion_id}/statements")
#     assert response.status_code == 200
#     data = response.get_json()
#     assert isinstance(data, list)


def test_deep_reextract_default_k1(subscriber, discussion, mock_celery):
    mock_celery.send_task.return_value.id = "task-1"
    response = subscriber.post(f"/personal/discussions/{discussion.id}/deep-reextract")
    assert response.status_code == 200
    assert response.get_json() == {"task_id": "task-1"}
    mock_celery.send_task.assert_called_once_with(
        "deep_reextract", args=[discussion.id, 1]
    )


def test_deep_reextract_k8_still_valid(subscriber, discussion, mock_celery):
    """Existing client toggle contract: explicit k=4/8 keeps working."""
    mock_celery.send_task.return_value.id = "task-1"
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/deep-reextract", json={"k": 8}
    )
    assert response.status_code == 200
    mock_celery.send_task.assert_called_once_with(
        "deep_reextract", args=[discussion.id, 8]
    )


def test_deep_reextract_rejects_invalid_k(subscriber, discussion, mock_celery):
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/deep-reextract", json={"k": 2}
    )
    assert response.status_code == 400
    mock_celery.send_task.assert_not_called()
