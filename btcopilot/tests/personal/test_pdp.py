import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    Person,
    Event,
    EventKind,
    asdict,
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
                people=[Person(id=-1, name="you")],
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        person=-1,
                        description="something happened",
                    )
                ],
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

    # Verify items were committed (removed from PDP)
    assert len(returned.pdp.people) == 0
    assert len(returned.pdp.events) == 0

    # Verify items were added to main diagram
    # commit_pdp_items uses transitive closure, so all referenced items get committed
    assert len(returned.people) == len(pdp.people)
    assert len(returned.events) == len(pdp.events)


@pytest.mark.parametrize(
    "id, pdp",
    [
        (
            -1,
            PDP(
                people=[Person(id=-1, name="you")],
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        person=-1,
                        description="person event",
                    )
                ],
            ),
        ),
        (
            -2,
            PDP(
                people=[Person(id=-1, name="you")],
                events=[
                    Event(
                        id=-2,
                        kind=EventKind.Shift,
                        person=-1,
                        description="something happened",
                    )
                ],
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

    # Verify the specific item was rejected
    if id == -1:
        # Person test: person removed AND event cascade-deleted
        assert len(returned.pdp.people) == 0
        assert len(returned.pdp.events) == 0
    else:
        # Event test: event removed, but person remains
        assert len(returned.pdp.people) == 1
        assert returned.pdp.people[0].id == -1
        assert len(returned.pdp.events) == 0

    # Nothing committed to main diagram
    assert len(returned.people) == 0
    assert len(returned.events) == 0
