from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
)
from btcopilot.pdp import (
    validate_pdp_deltas,
    apply_deltas,
    fix_birth_event_self_references,
)


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


def test_separated_event_infers_pair_bond():
    """Separated implies the couple existed — must create pair bond if missing."""
    pdp = PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        events=[
            Event(id=-20, kind=EventKind.Separated, person=-1, spouse=-2),
        ],
    )
    diagram_data = DiagramData(pdp=pdp)
    diagram_data.commit_pdp_items([-20])
    assert len(diagram_data.pair_bonds) == 1


def test_divorced_event_infers_pair_bond():
    """Divorced implies the couple existed — must create pair bond if missing."""
    pdp = PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        events=[
            Event(id=-20, kind=EventKind.Divorced, person=-1, spouse=-2),
        ],
    )
    diagram_data = DiagramData(pdp=pdp)
    diagram_data.commit_pdp_items([-20])
    assert len(diagram_data.pair_bonds) == 1


def test_birth_with_person_only_creates_inferred_child():
    """Birth event with only person set must create inferred spouse AND child."""
    pdp = PDP(
        people=[Person(id=-1, name="Dad")],
        events=[
            Event(id=-20, kind=EventKind.Birth, person=-1, description="Child born"),
        ],
    )
    diagram_data = DiagramData(pdp=pdp)
    diagram_data.commit_pdp_items([-20])

    assert len(diagram_data.people) == 3
    assert len(diagram_data.pair_bonds) == 1

    event = diagram_data.events[0]
    assert event["child"] is not None
    child = next(p for p in diagram_data.people if p["id"] == event["child"])
    assert child["parents"] is not None


# ── Birth event self-reference bug (T7-10) ──────────────────────────────────


def test_fix_birth_event_self_reference_clears_person():
    """fix_birth_event_self_references must clear person when person==child."""
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Barbara", confidence=0.9)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Birth,
                person=-1,
                child=-1,
                dateTime="1953-01-01",
            )
        ],
    )

    fix_birth_event_self_references(deltas)

    event = deltas.events[0]
    assert event.person is None, "person must be cleared when person==child"
    assert event.child == -1, "child must remain set to the born person"


def test_fix_birth_event_self_reference_preserves_correct_events():
    """fix_birth_event_self_references must not touch correctly structured events."""
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Baby"),
        ],
        events=[
            Event(
                id=-3,
                kind=EventKind.Birth,
                person=-1,
                child=-2,
                dateTime="2020-06-15",
            )
        ],
    )

    fix_birth_event_self_references(deltas)

    event = deltas.events[0]
    assert event.person == -1, "person (parent) must remain unchanged"
    assert event.child == -2, "child must remain unchanged"


def test_fix_birth_event_self_reference_child_only():
    """fix_birth_event_self_references must not touch events with child only."""
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Barbara")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Birth,
                child=-1,
                dateTime="1953-01-01",
            )
        ],
    )

    fix_birth_event_self_references(deltas)

    event = deltas.events[0]
    assert event.person is None
    assert event.child == -1


def test_fix_birth_event_self_reference_adopted():
    """fix_birth_event_self_references also handles adopted events."""
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alex")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Adopted,
                person=-1,
                child=-1,
                dateTime="2005-03-10",
            )
        ],
    )

    fix_birth_event_self_references(deltas)

    event = deltas.events[0]
    assert event.person is None, "person must be cleared for adopted self-reference too"
    assert event.child == -1


def test_birth_self_reference_commit_creates_inferred_parents():
    """After fixing self-reference, commit must create inferred parents via Case 1.

    Simulates the full pipeline: LLM outputs person==child (self-reference),
    fix_birth_event_self_references clears person, then commit_pdp_items
    creates inferred parents (mother + father + pair bond).
    """
    # Simulate LLM output with self-reference
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Barbara", confidence=0.9)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Birth,
                person=-1,
                child=-1,
                dateTime="1953-01-01",
            )
        ],
    )

    # Step 1: Fix self-reference (happens in _extract_and_validate pipeline)
    fix_birth_event_self_references(deltas)

    # Step 2: Apply deltas to empty PDP
    pdp = PDP()
    new_pdp = apply_deltas(pdp, deltas)

    # Step 3: Commit the birth event (triggers _create_inferred_birth_items)
    diagram_data = DiagramData(pdp=new_pdp)
    diagram_data.commit_pdp_items([-2])

    # Barbara must NOT be her own parent
    event = diagram_data.events[0]
    assert event["child"] is not None
    assert event["person"] is not None
    assert event["person"] != event["child"], (
        "Birth event must not have person==child after commit"
    )

    # Barbara should be the child, inferred parents should be created
    barbara = next(p for p in diagram_data.people if p["name"] == "Barbara")
    assert barbara["id"] == event["child"]

    # Inferred mother and father should exist
    assert len(diagram_data.people) == 3, (
        "Should have Barbara + inferred mother + inferred father"
    )
    assert len(diagram_data.pair_bonds) == 1, (
        "Should have one pair bond between inferred parents"
    )

    # Barbara should have parents reference to the pair bond
    assert barbara["parents"] is not None
    assert barbara["parents"] > 0  # committed positive ID


def test_fix_birth_self_reference_ignores_non_birth_events():
    """fix_birth_event_self_references must not touch shift events."""
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="Anxiety spike",
                dateTime="2025-01-01",
            )
        ],
    )

    fix_birth_event_self_references(deltas)

    event = deltas.events[0]
    assert event.person == -1, "Shift events must not be modified"
