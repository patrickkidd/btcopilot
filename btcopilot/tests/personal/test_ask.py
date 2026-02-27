import logging

import pytest

from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion


@pytest.mark.chat_flow(response="That's too bad")
def test_ask(test_user):
    message = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    response = ask(discussion, message)
    assert response.statement == "That's too bad"


@pytest.mark.chat_flow
def test_chat(subscriber, discussions):
    discussion = discussions[0]
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/statements",
        json={"discussion_id": discussion.id, "statement": "Hello"},
    )
    assert response.status_code == 200
    assert response.json == {"statement": "some response"}


def test_chat_bad_content_type(subscriber, discussions):
    discussion = discussions[0]
    response = subscriber.post(
        f"/personal/discussions/{discussion.id}/statements", data=b"123"
    )
    assert response.status_code == 415


@pytest.mark.e2e
def test_ask_e2e(test_user):
    logging.getLogger("btcopilot").setLevel(logging.DEBUG)
    message = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ask(discussion, message)
