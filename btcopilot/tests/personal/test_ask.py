import logging
from dataclasses import asdict

import pytest

from btcopilot.schema import Person, Event, EventKind, RelationshipKind, PairBond, PDP
from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion


@pytest.mark.chat_flow(
    pdp={
        "people": [
            Person(id=-1, name="Bob"),
            Person(id=-2, name="Alice"),
        ],
        "events": [
            Event(
                id=-3,
                kind=EventKind.Shift,
                description="Argued at birthday party",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-2],
            ),
        ],
        "pair_bonds": [
            PairBond(id=-4, person_a=-1, person_b=-2),
        ],
    },
    response="That's too bad",
)
def test_ask(test_user):
    logging.getLogger("btcopilot").setLevel(logging.DEBUG)

    message = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    response = ask(discussion, message)
    assert response.statement == "That's too bad"
    assert response.pdp is not None
    assert len(response.pdp.pair_bonds) == 1
    assert response.pdp.pair_bonds[0].person_a == -1
    assert response.pdp.pair_bonds[0].person_b == -2


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


# TODO: Add more scenarios


@pytest.mark.e2e
def test_ask_e2e(test_user):
    logging.getLogger("btcopilot").setLevel(logging.DEBUG)
    message = "I am having trouble with my mom and dad every since my dog died and I lost my job."

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ask(discussion, message)
