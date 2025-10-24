import pickle
from dataclasses import asdict

import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import PDPDeltas, Person, Event, EventKind

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


# def test_get_statements(subscriber, discussion):
#     """Test getting statements for a discussion"""
#     discussion_id = discussion.id
#     response = subscriber.get(f"/personal/discussions/{discussion_id}/statements")
#     assert response.status_code == 200
#     data = response.get_json()
#     assert isinstance(data, list)
