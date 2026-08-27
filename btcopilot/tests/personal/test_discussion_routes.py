"""FD-336 item 1: a new discussion binds to the diagram the caller names, so
its extraction lands in that diagram instead of the free one."""

import pickle

from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.pro.models import Diagram
from btcopilot.schema import PDP, PDPDeltas, Person


def _owned_diagram(user):
    diagram = Diagram(user_id=user.id, name="Case File", data=pickle.dumps({}))
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _create_discussion(client, **payload):
    return client.post("/personal/discussions/", json=payload)


def test_create_binds_to_the_requested_diagram(subscriber):
    diagram = _owned_diagram(subscriber.user)

    response = _create_discussion(subscriber, diagram_id=diagram.id)
    assert response.status_code == 200
    assert Discussion.query.get(response.get_json()["id"]).diagram_id == diagram.id


def test_created_discussion_is_listed_under_its_diagram(subscriber):
    diagram = _owned_diagram(subscriber.user)
    discussion_id = _create_discussion(subscriber, diagram_id=diagram.id).get_json()[
        "id"
    ]

    listed = subscriber.get(f"/personal/diagrams/{diagram.id}/discussions").get_json()
    assert [d["id"] for d in listed] == [discussion_id]

    free_listed = subscriber.get(
        f"/personal/diagrams/{subscriber.user.free_diagram_id}/discussions"
    ).get_json()
    assert free_listed == []


def test_create_without_a_diagram_id_uses_the_free_diagram(subscriber):
    response = _create_discussion(subscriber)
    assert (
        Discussion.query.get(response.get_json()["id"]).diagram_id
        == subscriber.user.free_diagram_id
    )


def test_create_rejects_another_users_diagram(subscriber, test_user_2):
    test_user_2.set_free_diagram(pickle.dumps({}))
    db.session.commit()

    response = _create_discussion(subscriber, diagram_id=test_user_2.free_diagram_id)
    assert response.status_code == 403
    assert Discussion.query.count() == 0


def test_create_rejects_an_unknown_diagram(subscriber):
    response = _create_discussion(subscriber, diagram_id=99999)
    assert response.status_code == 404
    assert Discussion.query.count() == 0


def test_extraction_lands_in_the_bound_diagram(subscriber):
    diagram = _owned_diagram(subscriber.user)
    discussion_id = _create_discussion(subscriber, diagram_id=diagram.id).get_json()[
        "id"
    ]
    extracted = PDP(people=[Person(id=-1, name="Mom")])

    with patch(
        "btcopilot.pdp.extract_full",
        AsyncMock(return_value=(extracted, PDPDeltas(people=extracted.people))),
    ):
        response = subscriber.post(f"/personal/discussions/{discussion_id}/extract")
    assert response.status_code == 200

    bound = Diagram.query.get(diagram.id).get_diagram_data()
    assert [p.name for p in bound.pdp.people] == ["Mom"]

    free = Diagram.query.get(subscriber.user.free_diagram_id).get_diagram_data()
    assert free.pdp.people == []
