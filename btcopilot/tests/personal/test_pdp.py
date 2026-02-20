from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
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
    pdp = PDP(
        people=[Person(id=-3, name="Parent A"), Person(id=-4, name="Parent B")],
        events=[],
        pair_bonds=[],
    )

    deltas = PDPDeltas(
        people=[Person(id=-1, name="Child", parents=-2)],
        pair_bonds=[PairBond(id=-2, person_a=-3, person_b=-4)],
    )

    new_pdp = apply_deltas(pdp, deltas)

    assert len(new_pdp.people) == 3
    child = next(p for p in new_pdp.people if p.id == -1)
    assert child.parents == -2
    assert len(new_pdp.pair_bonds) == 1
    assert new_pdp.pair_bonds[0].person_a == -3
    assert new_pdp.pair_bonds[0].person_b == -4


def test_apply_deltas_delete_person_cascades_pair_bond():
    pdp = PDP(
        people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
        pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
    )
    deltas = PDPDeltas(delete=[-1])

    result = apply_deltas(pdp, deltas)

    assert len(result.people) == 1
    assert result.people[0].id == -2
    assert len(result.pair_bonds) == 0


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


def test_cumulative_pdp_with_unique_negative_ids():
    """Test that cumulative PDP correctly accumulates entries with unique negative IDs."""
    pdp = PDP()

    delta1 = PDPDeltas(
        people=[Person(id=-1, name="First Person", confidence=0.8)],
        events=[
            Event(id=-2, kind=EventKind.Shift, person=-1, description="First event")
        ],
    )
    pdp = apply_deltas(pdp, delta1)

    delta2 = PDPDeltas(
        people=[Person(id=-3, name="Second Person", confidence=0.9)],
        events=[
            Event(id=-4, kind=EventKind.Shift, person=-3, description="Second event")
        ],
    )
    pdp = apply_deltas(pdp, delta2)

    assert len(pdp.people) == 2
    assert pdp.people[0].id == -1
    assert pdp.people[0].name == "First Person"
    assert pdp.people[1].id == -3
    assert pdp.people[1].name == "Second Person"
    assert len(pdp.events) == 2
    assert pdp.events[0].id == -2
    assert pdp.events[1].id == -4
