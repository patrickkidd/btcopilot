import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    asdict,
)
from btcopilot.pdp import validate_pdp_deltas, apply_deltas
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


def test_pair_bond_field_names():
    """Test that PairBond uses person_a and person_b, not person_a_id and person_b_id"""
    pair_bond = PairBond(id=-1, person_a=-2, person_b=-3, confidence=0.9)
    assert pair_bond.person_a == -2
    assert pair_bond.person_b == -3
    assert not hasattr(pair_bond, "person_a_id")
    assert not hasattr(pair_bond, "person_b_id")


def test_person_parents_field_name():
    """Test that Person uses parents, not pair_bond_id"""
    person = Person(id=-1, name="Child", parents=-2)
    assert person.parents == -2
    assert not hasattr(person, "pair_bond_id")


def test_pdp_has_pair_bonds():
    """Test that PDP class has pair_bonds field"""
    pdp = PDP(
        people=[Person(id=-1, name="Child", parents=-3)],
        events=[],
        pair_bonds=[PairBond(id=-3, person_a=-4, person_b=-5)],
    )
    assert hasattr(pdp, "pair_bonds")
    assert len(pdp.pair_bonds) == 1
    assert pdp.pair_bonds[0].id == -3


def test_diagram_data_has_pair_bonds():
    """Test that DiagramData class has pair_bonds field"""
    data = DiagramData(
        people=[],
        events=[],
        pair_bonds=[{"id": 1, "person_a": 2, "person_b": 3}],
    )
    assert hasattr(data, "pair_bonds")
    assert len(data.pair_bonds) == 1


def test_validate_pdp_deltas_with_pair_bonds():
    """Test that validate_pdp_deltas works with new field names"""
    pdp = PDP(
        people=[Person(id=-1, name="Parent A"), Person(id=-2, name="Parent B")],
        pair_bonds=[],
        events=[],
    )

    deltas = PDPDeltas(
        people=[Person(id=-3, name="Child", parents=-4)],
        pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
    )

    # Should not raise
    validate_pdp_deltas(pdp, deltas)


def test_apply_deltas_with_pair_bonds():
    """Test that apply_deltas works with pair_bonds"""
    pdp = PDP(people=[], events=[], pair_bonds=[])

    deltas = PDPDeltas(
        people=[Person(id=-1, name="Child", parents=-2)],
        pair_bonds=[PairBond(id=-2, person_a=-3, person_b=-4)],
    )

    new_pdp = apply_deltas(pdp, deltas)

    assert len(new_pdp.people) == 1
    assert new_pdp.people[0].parents == -2
    assert len(new_pdp.pair_bonds) == 1
    assert new_pdp.pair_bonds[0].person_a == -3
    assert new_pdp.pair_bonds[0].person_b == -4


def test_commit_pdp_items_direct():
    """Test that commit_pdp_items correctly commits pair_bonds"""
    # Create PDP with pair_bond referencing two people
    pdp = PDP(
        people=[
            Person(id=-1, name="Parent A"),
            Person(id=-2, name="Parent B"),
            Person(id=-3, name="Child", parents=-4),
        ],
        pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
        events=[],
    )

    diagram_data = DiagramData(pdp=pdp)

    # Commit the child (which should transitively commit the pair_bond and parents)
    id_mapping = diagram_data.commit_pdp_items([-3])

    # Verify all items were committed (removed from PDP)
    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.pdp.pair_bonds) == 0

    # All items should be in main diagram
    assert len(diagram_data.people) == 3
    assert len(diagram_data.pair_bonds) == 1

    # Verify field names in committed data
    child = next(p for p in diagram_data.people if p["name"] == "Child")
    assert "parents" in child
    assert child["parents"] > 0  # Should be positive (committed) ID

    pair_bond = diagram_data.pair_bonds[0]
    assert "person_a" in pair_bond
    assert "person_b" in pair_bond
    assert pair_bond["person_a"] > 0
    assert pair_bond["person_b"] > 0


def test_commit_pdp_items_with_pair_bonds(subscriber):
    """Test that commit_pdp_items works with pair_bonds"""
    # Create PDP with pair_bond referencing two people
    pdp = PDP(
        people=[
            Person(id=-1, name="Parent A"),
            Person(id=-2, name="Parent B"),
            Person(id=-3, name="Child", parents=-4),
        ],
        pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
        events=[],
    )

    diagram_data = DiagramData(pdp=pdp)
    subscriber.user.free_diagram.set_diagram_data(diagram_data)
    db.session.commit()

    # Commit the child (which should transitively commit the pair_bond and parents)
    # URL uses absolute value of negative ID
    response = subscriber.post(
        f"/personal/diagrams/{subscriber.user.free_diagram_id}/pdp/{abs(-3)}/accept"
    )
    assert response.status_code == 200

    # Verify all items were committed
    user = User.query.get(subscriber.user.id)
    returned = user.free_diagram.get_diagram_data()

    # All PDP items should be committed (removed from PDP)
    assert len(returned.pdp.people) == 0
    assert len(returned.pdp.pair_bonds) == 0

    # All items should be in main diagram
    assert len(returned.people) == 3
    assert len(returned.pair_bonds) == 1

    # Verify field names in committed data
    child = next(p for p in returned.people if p["name"] == "Child")
    assert "parents" in child
    assert child["parents"] > 0  # Should be positive (committed) ID

    pair_bond = returned.pair_bonds[0]
    assert "person_a" in pair_bond
    assert "person_b" in pair_bond
    assert pair_bond["person_a"] > 0
    assert pair_bond["person_b"] > 0


def test_compute_spouses_from_events():
    """Test that compute_spouses_for_person correctly computes spouses from Events"""
    from btcopilot.schema import compute_spouses_for_person, Event, EventKind

    events = [
        Event(id=1, kind=EventKind.Married, person=1, spouse=2),
        Event(id=2, kind=EventKind.Birth, person=1, spouse=2, child=3),
        Event(id=3, kind=EventKind.Married, person=4, spouse=5),
        Event(id=4, kind=EventKind.Divorced, person=1, spouse=2),
    ]

    # Person 1 should have spouse 2 (appears in multiple pair bond events)
    spouses = compute_spouses_for_person(1, events)
    assert 2 in spouses
    assert len(spouses) == 1

    # Person 2 should have spouse 1
    spouses = compute_spouses_for_person(2, events)
    assert 1 in spouses
    assert len(spouses) == 1

    # Person 3 (child) should have no spouses
    spouses = compute_spouses_for_person(3, events)
    assert len(spouses) == 0

    # Person 4 should have spouse 5
    spouses = compute_spouses_for_person(4, events)
    assert 5 in spouses
    assert len(spouses) == 1
