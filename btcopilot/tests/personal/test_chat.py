import pytest

from btcopilot.personal.pdp import PDP


@pytest.mark.chat_flow
def test_chat(logged_in, discussions):
    discussion = discussions[0]
    response = logged_in.post(
        f"/personal/discussions/{discussion.id}/statements",
        json={"discussion_id": discussion.id, "statement": "Hello"},
    )
    assert response.status_code == 200
    assert response.json == {"statement": "some response", "pdp": PDP().model_dump()}


def test_chat_bad_content_type(logged_in, discussions):
    discussion = discussions[0]
    response = logged_in.post(
        f"/personal/discussions/{discussion.id}/statements", data=b"123"
    )
    assert response.status_code == 415
