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


def test_accept_person():
    """Test accepting a person commits it to the main diagram."""
    pdp = PDP(people=[Person(id=-1, name="you")])
    diagram_data = DiagramData(pdp=pdp)

    diagram_data.commit_pdp_items([-1])

    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.people) == 1
    assert diagram_data.people[0]["name"] == "you"


def test_accept_event():
    """Test accepting an event commits it and its referenced person."""
    pdp = PDP(
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
    diagram_data = DiagramData(pdp=pdp)

    diagram_data.commit_pdp_items([-2])

    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.pdp.events) == 0
    assert len(diagram_data.people) == 1
    assert len(diagram_data.events) == 1


def test_reject_person():
    """Test rejecting a person removes it and cascade-deletes its events."""
    pdp = PDP(
        people=[Person(id=-1, name="you")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="person event",
            )
        ],
    )
    diagram_data = DiagramData(pdp=pdp)

    diagram_data.reject_pdp_item(-1)

    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.pdp.events) == 0
    assert len(diagram_data.people) == 0
    assert len(diagram_data.events) == 0


def test_reject_event():
    """Test rejecting an event removes it but keeps the person."""
    pdp = PDP(
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
    diagram_data = DiagramData(pdp=pdp)

    diagram_data.reject_pdp_item(-2)

    assert len(diagram_data.pdp.people) == 1
    assert diagram_data.pdp.people[0].id == -1
    assert len(diagram_data.pdp.events) == 0
    assert len(diagram_data.people) == 0
    assert len(diagram_data.events) == 0


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
