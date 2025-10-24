from dataclasses import asdict

import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    Person,
    Event,
    EventKind,
    RelationshipKind,
)
from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.personal.models import Discussion


def test_get(subscriber):
    database = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="you")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="something happened",
                )
            ],
        )
    )
    subscriber.user.free_diagram.set_diagram_data(database)
    db.session.commit()

    response = subscriber.get("/personal/pdp")
    assert response.status_code == 200
    assert response.json == asdict(database.pdp)


@pytest.mark.parametrize(
    "id, pdp",
    [
        (-1, PDP(people=[Person(id=-1, name="you")])),
        (
            -2,
            PDP(
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        person=-1,
                        description="something happened",
                    )
                ]
            ),
        ),
    ],
    ids=["person", "event"],
)
def test_accept(subscriber, id, pdp):
    discussion = Discussion(
        user_id=subscriber.user.id, diagram_id=subscriber.user.free_diagram.id
    )
    db.session.add(discussion)
    db.session.commit()

    subscriber.user.free_diagram.set_diagram_data(DiagramData(pdp=pdp))
    db.session.commit()

    response = subscriber.post(
        f"/personal/diagrams/{subscriber.user.free_diagram_id}/pdp/{-id}/accept"
    )
    assert response.status_code == 200
    assert response.json["success"] is True

    user = User.query.get(subscriber.user.id)
    returned = user.free_diagram.get_diagram_data()
    expected = DiagramData()
    if pdp.people:
        expected.add_person(pdp.people[0])
    else:
        expected.add_event(pdp.events[0])
    assert returned == expected


@pytest.mark.parametrize(
    "id, pdp",
    [
        (-1, PDP(people=[Person(id=-1, name="you")])),
        (
            -2,
            PDP(
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        person=-1,
                        description="something happened",
                    )
                ]
            ),
        ),
    ],
    ids=["person", "event"],
)
def test_reject(subscriber, id, pdp):
    discussion = Discussion(
        user_id=subscriber.user.id, diagram_id=subscriber.user.free_diagram.id
    )
    db.session.add(discussion)
    db.session.commit()

    subscriber.user.free_diagram.set_diagram_data(DiagramData(pdp=pdp))
    db.session.commit()

    response = subscriber.post(
        f"/personal/diagrams/{subscriber.user.free_diagram_id}/pdp/{-id}/reject"
    )
    assert response.status_code == 200
    assert response.json["success"] is True

    user = User.query.get(subscriber.user.id)
    returned = user.free_diagram.get_diagram_data()
    expected = DiagramData()
    assert returned == expected
