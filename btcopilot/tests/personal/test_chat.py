import pytest
from dataclasses import asdict

from btcopilot.schema import PDP


@pytest.mark.chat_flow
def test_chat(subscriber, discussions):
    discussion = discussions[0]
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/statements",
        json={"discussion_id": discussion.id, "statement": "Hello"},
    )
    assert response.status_code == 200
    assert response.json == {"statement": "some response", "pdp": asdict(PDP())}


def test_chat_bad_content_type(subscriber, discussions):
    discussion = discussions[0]
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/statements", data=b"123"
    )
    assert response.status_code == 415
