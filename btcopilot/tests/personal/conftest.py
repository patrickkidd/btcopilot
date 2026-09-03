import contextlib
import datetime
import re

import flask.testing
import pytest
from mock import patch

import btcopilot
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.tests.pro.conftest import pro_client, subscriber, admin


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "chat_flow: mock various parts of the intelligence flow",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


@pytest.fixture(autouse=True)
def chat_flow(request):

    marker = request.node.get_closest_marker("chat_flow")

    with contextlib.ExitStack() as stack:
        if marker is not None:

            response = marker.kwargs.get("response", "some response")

            stack.enter_context(
                patch(
                    "btcopilot.personal.chat._generate_response",
                    return_value=response,
                )
            )
            title = marker.kwargs.get("title", "A session title")
            stack.enter_context(
                patch(
                    "btcopilot.personal.models.discussion.response_text_sync",
                    return_value=title,
                )
            )
            ret = {
                "response": response,
                "title": title,
            }
        else:
            ret = None
        yield ret


@pytest.fixture
def web(flask_app, test_user):
    """Browser client for the companion app: a logged-in session cookie, the
    way the page itself is served."""
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["logged_in_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield client


def csrf_token(web) -> str:
    page = web.get("/companion/").get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


@pytest.fixture
def discussions(test_user):
    items = [
        Discussion(user_id=test_user.id, summary=f"test thread {i}") for i in range(3)
    ]
    db.session.add_all(items)
    db.session.commit()
    return items


@pytest.fixture
def discussion(test_user):
    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        summary="Test discussion",
    )
    db.session.add(discussion)
    db.session.commit()

    # Create speakers for the discussion
    family_speaker = Speaker(
        discussion_id=discussion.id,
        name="Family Member",
        type=SpeakerType.Subject,
        person_id=1,
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id,
        name="Expert",
        type=SpeakerType.Expert,
    )
    db.session.add_all([family_speaker, expert_speaker])
    db.session.commit()

    # Create statements
    statement1 = Statement(
        discussion_id=discussion.id, speaker_id=family_speaker.id, text="Hello", order=0
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Hi there",
        pdp_deltas={
            "events": [
                {
                    "id": 1,
                    "kind": "shift",
                    "person": 1,
                    "symptom": "up",
                    "description": "Feeling better",
                }
            ],
            "people": [],
            "pair_bonds": [],
        },
        order=1,
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    return discussion
