"""
Test the logic of ask with the different scenarios mocked. Should not make llm
calls.
"""

import logging

import pytest

from btcopilot.extensions import db
from btcopilot.personal import ResponseDirection, ask
from btcopilot.personal.models import Discussion
from btcopilot.schema import Person, Event, Conflict


@pytest.mark.chat_flow(
    response_direction=ResponseDirection.Follow,
    pdp={
        "people": [
            Person(
                id=-1,
                name="Bob",
                spouses=[-2],
            ),
            Person(id=-2, name="Alice", spouses=[-1]),
        ],
        "events": [
            Event(
                id=-3,
                description="Argued at birthday party",
                relationship=Conflict(movers=[-1], recipients=[-2]),
            ),
        ],
    },
    response="That's too bad",
)
def test_ask(test_user):
    logging.getLogger("btcopilot").setLevel(logging.DEBUG)

    MESSAGE = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    response = ask(discussion, MESSAGE)
    assert response.message == "That's too bad"


# TODO: Add more scenarios


@pytest.mark.e2e
def test_ask(test_user):
    logging.getLogger("btcopilot").setLevel(logging.DEBUG)
    MESSAGE = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ask(discussion, MESSAGE)
