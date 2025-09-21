import pytest

from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.personal import pdp
from btcopilot.personal.database import Database, PDP, Person, Event
from btcopilot.personal.models import Discussion


def test_get(test_user, logged_in):
    database = Database(
        pdp=PDP(
            people=[Person(id=-1, name="you")],
            events=[Event(id=-2, description="something happened")],
        )
    )
    test_user.free_diagram.set_database(database)
    db.session.commit()

    response = logged_in.get("/personal/pdp")
    assert response.status_code == 200
    assert response.json == database.pdp.model_dump()


@pytest.mark.parametrize(
    "id, pdp",
    [
        (-1, PDP(people=[Person(id=-1, name="you")])),
        (-2, PDP(events=[Event(id=-2, description="something happened")])),
    ],
    ids=["person", "event"],
)
def test_accept(test_user, logged_in, id, pdp):
    discussion = Discussion(user_id=test_user.id, diagram_id=test_user.free_diagram.id)
    db.session.add(discussion)
    db.session.commit()

    test_user.free_diagram.set_database(Database(pdp=pdp))
    db.session.commit()

    response = logged_in.post(
        f"/personal/diagrams/{logged_in.user.free_diagram_id}/pdp/{-id}/accept"
    )
    assert response.status_code == 200
    assert response.json["success"] is True

    user = User.query.get(test_user.id)
    returned = user.free_diagram.get_database()
    expected = Database()
    if pdp.people:
        expected.add_person(pdp.people[0])
    else:
        expected.add_event(pdp.events[0])
    assert returned == expected


@pytest.mark.parametrize(
    "id, pdp",
    [
        (-1, PDP(people=[Person(id=-1, name="you")])),
        (-2, PDP(events=[Event(id=-2, description="something happened")])),
    ],
    ids=["person", "event"],
)
def test_reject(test_user, logged_in, id, pdp):
    discussion = Discussion(user_id=test_user.id, diagram_id=test_user.free_diagram.id)
    db.session.add(discussion)
    db.session.commit()

    test_user.free_diagram.set_database(Database(pdp=pdp))
    db.session.commit()

    response = logged_in.post(
        f"/personal/diagrams/{logged_in.user.free_diagram_id}/pdp/{-id}/reject"
    )
    assert response.status_code == 200
    assert response.json["success"] is True

    user = User.query.get(test_user.id)
    returned = user.free_diagram.get_database()
    expected = Database()
    assert returned == expected
