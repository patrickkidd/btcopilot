import contextlib

import pytest
from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal import ResponseDirection
from btcopilot.schema import PDP, PDPDeltas, from_dict
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.tests.pro.conftest import pro_client, subscriber, admin


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "chat_flow: mock various parts of the intelligence flow",
    )


@pytest.fixture(autouse=True)
def chat_flow(request):

    marker = request.node.get_closest_marker("chat_flow")

    with contextlib.ExitStack() as stack:
        if marker is not None:

            response = marker.kwargs.get("response", "some response")
            pdp_dict = marker.kwargs.get("pdp", {})
            pdp_obj = from_dict(PDP, pdp_dict) if pdp_dict else PDP()
            pdp = (pdp_obj, PDPDeltas())
            response_direction = marker.kwargs.get(
                "response_direction", ResponseDirection.Follow
            )

            stack.enter_context(
                patch(
                    "btcopilot.pdp.update",
                    AsyncMock(return_value=pdp),
                )
            )
            stack.enter_context(
                patch(
                    "btcopilot.personal.chat.detect_response_direction",
                    AsyncMock(return_value=response_direction),
                )
            )
            stack.enter_context(
                patch(
                    "btcopilot.personal.chat._generate_response",
                    return_value=response,
                )
            )
            ret = {
                "response": response,
                "pdp": pdp,
                "response_direction": response_direction,
            }
        else:
            ret = None
        yield ret


@pytest.fixture
def discussions(test_user):
    _discussions = [
        Discussion(user_id=test_user.id, summary=f"test thread {i}") for i in range(3)
    ]
    db.session.add_all(_discussions)
    db.session.commit()
    return _discussions


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
        pdp_deltas={"events": [{"symptom": {"shift": "better"}}]},
        order=1,
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    return discussion
