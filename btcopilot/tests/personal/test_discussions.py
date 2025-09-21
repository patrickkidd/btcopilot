import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.personal.database import PDPDeltas, Person, Event

from btcopilot.tests.training.conftest import flask_json


def test_create(logged_in):
    response = logged_in.post("/personal/discussions/")
    data = response.get_json()
    assert response.status_code == 200
    assert Discussion.query.count() == 1
    assert "id" in data
    assert data["user_id"] is not None
    assert data == flask_json(
        Discussion.query.first().as_dict(include=["speakers", "statements"])
    )


def test_list(logged_in, discussions):
    response = logged_in.get("/personal/discussions/")
    assert response.json == flask_json([x.as_dict() for x in discussions])


def test_list_401(anonymous, discussions):
    response = anonymous.get("/personal/discussions/")
    # Anonymous users get redirected to login
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_get(logged_in, discussions):
    discussion = Discussion(
        user_id=logged_in.user.id,
        statements=[
            Statement(
                text="blah",
                speaker=Speaker(type=SpeakerType.Subject),
                pdp_deltas=PDPDeltas(
                    people=[Person(id=-1, name="hey")], events=[]
                ).model_dump(),
            ),
            Statement(
                text="blah",
                speaker=Speaker(type=SpeakerType.Subject),
                pdp_deltas=PDPDeltas(
                    people=[],
                    events=[
                        Event(id=-2, description="something happened", people=[-1])
                    ],
                ).model_dump(),
            ),
        ],
    )
    db.session.add(discussion)
    db.session.commit()
    response = logged_in.get(f"/personal/discussions/{discussion.id}")
    assert response.status_code == 200
    assert response.get_json() == flask_json(
        discussion.as_dict(include=["statements", "speakers"])
    )


def test_get_404(auditor):
    response = auditor.get("/personal/discussions/99999")
    assert response.status_code == 404


def test_get_statements(auditor, discussion):
    """Test getting statements for a discussion"""
    discussion_id = discussion.id
    response = auditor.get(f"/personal/discussions/{discussion_id}/statements")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
