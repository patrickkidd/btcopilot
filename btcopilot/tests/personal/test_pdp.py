import asyncio
import logging

import pytest
from mock import patch, AsyncMock

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    PDPValidationError,
    Person,
    Event,
    EventKind,
    PairBond,
)
from btcopilot.pdp import (
    MAX_EXTRACTION_RETRIES,
    _extract_and_validate,
    validate_pdp_deltas,
    apply_deltas,
    fix_birth_event_self_references,
    fix_self_parent_references,
    fix_committed_person_duplicates,
    fix_unresolved_person_refs,
    infer_parents_from_birth_events,
    _committed_person_matches,
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
    assert (
        event["person"] != event["child"]
    ), "Birth event must not have person==child after commit"

    # Barbara should be the child, inferred parents should be created
    barbara = next(p for p in diagram_data.people if p["name"] == "Barbara")
    assert barbara["id"] == event["child"]

    # Inferred mother and father should exist
    assert (
        len(diagram_data.people) == 3
    ), "Should have Barbara + inferred mother + inferred father"
    assert (
        len(diagram_data.pair_bonds) == 1
    ), "Should have one pair bond between inferred parents"

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


# Self-parent reference fix


def test_fix_self_parent_reference_clears_parents():
    """fix_self_parent_references must clear Person.parents when the
    referenced PairBond contains the same person."""
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Person A"),
            Person(id=-2, name="Spouse"),
        ],
        pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
    )
    deltas.people[0].parents = -3

    fix_self_parent_references(deltas)

    assert deltas.people[0].parents is None
    assert len(deltas.pair_bonds) == 1
    assert deltas.pair_bonds[0].person_a == -1
    assert deltas.pair_bonds[0].person_b == -2


def test_fix_self_parent_reference_preserves_correct():
    """fix_self_parent_references must not touch a legitimate parents reference."""
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
            Person(id=-3, name="Child", parents=-4),
        ],
        pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
    )

    fix_self_parent_references(deltas)

    child = next(p for p in deltas.people if p.id == -3)
    assert child.parents == -4


def test_fix_self_parent_reference_resolves_committed_pair_bond():
    """fix_self_parent_references must resolve positive parents IDs against
    diagram_data.pair_bonds and clear when the committed PairBond contains self."""
    diagram_data = DiagramData(
        people=[
            {"id": 10, "name": "Person A"},
            {"id": 11, "name": "Spouse"},
        ],
        pair_bonds=[{"id": 20, "person_a": 10, "person_b": 11}],
    )
    deltas = PDPDeltas(
        people=[Person(id=10, parents=20)],
    )

    fix_self_parent_references(deltas, diagram_data)

    assert deltas.people[0].parents is None


def test_validate_pdp_deltas_raises_on_self_parent():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Person A"),
            Person(id=-2, name="Spouse"),
        ],
        pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
    )
    deltas.people[0].parents = -3

    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)

    assert any("contains self" in err for err in exc_info.value.errors)


def test_validate_pdp_deltas_raises_on_birth_event_self_reference():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Mom")],
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

    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)

    assert any("self-reference" in err for err in exc_info.value.errors)


def _bad_self_parent_deltas() -> PDPDeltas:
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Person A"),
            Person(id=-2, name="Spouse"),
        ],
        pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
    )
    deltas.people[0].parents = -3
    return deltas


def _bad_birth_event_deltas() -> PDPDeltas:
    return PDPDeltas(
        people=[Person(id=-1, name="Mom")],
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


def _bad_dup_pair_bond_deltas() -> PDPDeltas:
    return PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
        ],
        pair_bonds=[
            PairBond(id=-3, person_a=-1, person_b=-2),
            PairBond(id=-4, person_a=-1, person_b=-2),
        ],
    )


def _bad_id_collision_deltas() -> PDPDeltas:
    return PDPDeltas(
        people=[Person(id=-1, name="Mom")],
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=-1,
                description="Anxiety spike",
                dateTime="2025-01-01",
            )
        ],
    )


def _run_extract_and_assert_repair(caplog, builder):
    diagram_data = DiagramData()
    counter = {"calls": 0}

    async def fake(*args, **kwargs):
        counter["calls"] += 1
        return builder()

    with patch("btcopilot.pdp.gemini_structured", AsyncMock(side_effect=fake)):
        with caplog.at_level(logging.WARNING, logger="btcopilot.pdp"):
            new_pdp, deltas = asyncio.run(
                _extract_and_validate("prompt", diagram_data, "test_source")
            )

    assert counter["calls"] == 1 + MAX_EXTRACTION_RETRIES
    validate_pdp_deltas(diagram_data.pdp, deltas, diagram_data, "test_source")
    assert any(
        "PDP repair pass succeeded after retry exhaustion" in rec.message
        for rec in caplog.records
    )
    return new_pdp, deltas


def test_extract_and_validate_self_parent_repair_after_exhaustion(caplog):
    new_pdp, deltas = _run_extract_and_assert_repair(caplog, _bad_self_parent_deltas)
    assert deltas.people[0].parents is None
    assert any("fix_self_parent_references:" in rec.message for rec in caplog.records)


def test_extract_and_validate_birth_event_self_reference_repair_after_exhaustion(
    caplog,
):
    new_pdp, deltas = _run_extract_and_assert_repair(caplog, _bad_birth_event_deltas)
    event = deltas.events[0]
    assert event.person is None
    assert event.child == -1
    assert any(
        "fix_birth_event_self_references:" in rec.message for rec in caplog.records
    )


def test_extract_and_validate_dedup_pair_bonds_repair_after_exhaustion(caplog):
    new_pdp, deltas = _run_extract_and_assert_repair(caplog, _bad_dup_pair_bond_deltas)
    assert len(deltas.pair_bonds) == 1
    assert any("dedup_pair_bonds:" in rec.message for rec in caplog.records)


def test_extract_and_validate_id_collision_repair_after_exhaustion(caplog):
    new_pdp, deltas = _run_extract_and_assert_repair(caplog, _bad_id_collision_deltas)
    person_ids = {p.id for p in deltas.people}
    event_ids = {e.id for e in deltas.events}
    assert not (person_ids & event_ids)
    assert any("reassign_delta_ids:" in rec.message for rec in caplog.records)


# --- FD-319: committed-person duplication ---


def _committed_couple_diagram() -> DiagramData:
    return DiagramData(
        people=[
            {"id": 1, "name": "Mary", "gender": "female"},
            {"id": 2, "name": "John", "gender": "male"},
        ],
        pair_bonds=[{"id": 10, "person_a": 1, "person_b": 2}],
        events=[
            {
                "id": 20,
                "kind": "married",
                "person": 1,
                "spouse": 2,
                "dateTime": "1990-06-15",
            }
        ],
    )


def _committed_dup_deltas() -> PDPDeltas:
    """LLM recreated the two committed parents and re-emitted their marriage,
    plus a genuinely-new child Sarah."""
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mary", gender="female"),
            Person(id=-2, name="John", gender="male"),
            Person(id=-3, name="Sarah", gender="female"),
        ],
        pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
        events=[
            Event(
                id=-5,
                kind=EventKind.Married,
                person=-1,
                spouse=-2,
                dateTime="1990-06-15",
            ),
            Event(
                id=-6,
                kind=EventKind.Birth,
                person=-1,
                spouse=-2,
                child=-3,
                dateTime="1995-01-01",
            ),
        ],
    )
    deltas.people[2].parents = -4
    return deltas


def test_validate_raises_on_committed_person_duplicate():
    diagram_data = _committed_couple_diagram()
    pdp = PDP()
    deltas = _committed_dup_deltas()

    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas, diagram_data)

    assert any(
        "duplicates committed person" in err for err in exc_info.value.errors
    )


def test_fix_committed_person_duplicates_remaps_refs():
    diagram_data = _committed_couple_diagram()
    deltas = _committed_dup_deltas()

    fix_committed_person_duplicates(deltas, diagram_data)

    names = {p.name for p in deltas.people}
    assert names == {"Sarah"}

    sarah = next(p for p in deltas.people if p.name == "Sarah")
    assert sarah.id == -3

    birth = next(e for e in deltas.events if e.kind == EventKind.Birth)
    assert birth.person == 1
    assert birth.spouse == 2
    assert birth.child == -3

    # Committed marriage must not be re-added; committed pair_bond dyad dropped
    assert all(e.kind != EventKind.Married for e in deltas.events)
    committed_dyad_present = any(
        {pb.person_a, pb.person_b} == {1, 2} for pb in deltas.pair_bonds
    )
    assert not committed_dyad_present
    # FD-319 PR#119 #2: the dropped duplicate bond's child keeps its parent
    # link, remapped onto the surviving committed pair_bond (id 10).
    assert sarah.parents == 10


def test_fix_committed_person_duplicates_reaches_fixed_point():
    """Re-extraction recreating a whole committed family. match_people is a
    global assignment: dropping the first round of duplicates shifts the
    optimal matching and exposes committed duplicates a single repair pass
    never sees. validate_pdp_deltas recomputes the same matcher, so any
    residual dead-ends extraction (the disc-55 production 500). The repair
    must leave zero residual committed-person matches."""
    diagram_data = DiagramData(
        people=[
            {"id": 1, "name": "Mary", "gender": "female"},
            {"id": 2, "name": "John", "gender": "male"},
            {"id": 3, "name": "Sarah", "gender": "female"},
            {"id": 4, "name": "Mark", "gender": "male"},
            {"id": 5, "name": "Anne", "gender": "female"},
        ],
        pair_bonds=[{"id": 10, "person_a": 1, "person_b": 2}],
        events=[],
    )
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mary", gender="female"),
            Person(id=-2, name="John", gender="male"),
            Person(id=-3, name="Sarah", gender="female"),
            Person(id=-4, name="Mark", gender="male"),
            Person(id=-5, name="Anne", gender="female"),
            Person(id=-6, name="Liam", gender="male"),  # genuinely new
        ],
        pair_bonds=[PairBond(id=-7, person_a=-1, person_b=-2)],
        events=[
            Event(id=-8, kind=EventKind.Birth, person=-1, spouse=-2,
                  child=-6, dateTime="2015-01-01"),
        ],
    )

    fix_committed_person_duplicates(deltas, diagram_data)

    assert _committed_person_matches(deltas, diagram_data) == {}
    validate_pdp_deltas(PDP(), deltas, diagram_data)  # must not raise
    assert [p.name for p in deltas.people] == ["Liam"]
    assert deltas.people[0].id == -6


def test_fix_committed_person_duplicates_preserves_new_people():
    """A delta person with no committed counterpart must be untouched."""
    diagram_data = _committed_couple_diagram()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Sarah", gender="female")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="anxiety up",
                dateTime="2020-01-01",
            )
        ],
    )

    fix_committed_person_duplicates(deltas, diagram_data)

    assert [p.name for p in deltas.people] == ["Sarah"]
    assert deltas.people[0].id == -1
    assert deltas.events[0].person == -1


def _committed_dup_positive_id_deltas() -> PDPDeltas:
    """LLM correctly references the committed couple by positive ID but
    re-emits their marriage and pair_bond — zero delta people to remap."""
    return PDPDeltas(
        people=[],
        pair_bonds=[PairBond(id=-1, person_a=1, person_b=2)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Married,
                person=1,
                spouse=2,
                dateTime="1990-06-01",
            )
        ],
    )


def test_extract_and_validate_drops_committed_dups_pre_validate(caplog):
    """Pre-validate repair drops committed-dup people AND bond/event in the
    single deterministic pass — no Ralph retry."""
    diagram_data = _committed_couple_diagram()
    counter = {"calls": 0}

    async def fake(*args, **kwargs):
        counter["calls"] += 1
        return _committed_dup_deltas()

    with patch("btcopilot.pdp.gemini_structured", AsyncMock(side_effect=fake)):
        with caplog.at_level(logging.WARNING, logger="btcopilot.pdp"):
            new_pdp, deltas = asyncio.run(
                _extract_and_validate("prompt", diagram_data, "test_source")
            )

    assert counter["calls"] == 1
    validate_pdp_deltas(diagram_data.pdp, deltas, diagram_data, "test_source")
    assert {p.name for p in deltas.people} == {"Sarah"}
    assert all(e.kind != EventKind.Married for e in deltas.events)
    assert not any(
        {pb.person_a, pb.person_b} == {1, 2} for pb in deltas.pair_bonds
    )
    assert any(
        "fix_committed_person_duplicates:" in rec.message
        for rec in caplog.records
    )


def test_extract_and_validate_drops_committed_dups_no_remap(caplog):
    """LLM references committed people by positive ID and re-emits their
    marriage with no delta people: bond/event still dropped pre-validate,
    no retry."""
    diagram_data = _committed_couple_diagram()
    counter = {"calls": 0}

    async def fake(*args, **kwargs):
        counter["calls"] += 1
        return _committed_dup_positive_id_deltas()

    with patch("btcopilot.pdp.gemini_structured", AsyncMock(side_effect=fake)):
        with caplog.at_level(logging.WARNING, logger="btcopilot.pdp"):
            new_pdp, deltas = asyncio.run(
                _extract_and_validate("prompt", diagram_data, "test_source")
            )

    assert counter["calls"] == 1
    validate_pdp_deltas(diagram_data.pdp, deltas, diagram_data, "test_source")
    assert deltas.events == []
    assert deltas.pair_bonds == []
    assert any(
        "committed-duplicate" in rec.message for rec in caplog.records
    )


def test_validate_flags_event_positive_ref_not_committed():
    from btcopilot.pdp import fix_unresolved_person_refs

    dd = DiagramData(people=[{"id": 1, "name": "Speaker"}])
    deltas = PDPDeltas(
        events=[Event(id=-2, kind=EventKind.Bonded, person=821, spouse=819,
                       dateTime="1994-01-01")],
    )
    with pytest.raises(PDPValidationError) as exc:
        validate_pdp_deltas(PDP(), deltas, dd)
    assert any("non-existent committed" in e for e in exc.value.errors)

    # deterministic repair drops the unanchorable event
    fix_unresolved_person_refs(deltas, PDP(), dd)
    assert deltas.events == []
    validate_pdp_deltas(PDP(), deltas, dd)  # now clean


def test_fix_unresolved_refs_clears_orphaned_parents():
    """Dropping an unresolvable pair_bond must also clear Person.parents that
    point at it, or validation never converges (FD-319 disc 60 500)."""
    from btcopilot.pdp import fix_unresolved_person_refs

    deltas = PDPDeltas(
        people=[
            Person(id=-3, name="A", parents=-14),
            Person(id=-4, name="B", parents=-14),
        ],
        pair_bonds=[PairBond(id=-14, person_a=-2, person_b=-15)],  # -2,-15 absent
    )
    fix_unresolved_person_refs(deltas, PDP())
    assert deltas.pair_bonds == []
    assert all(p.parents is None for p in deltas.people)
    validate_pdp_deltas(PDP(), deltas)  # converges, no error


# --- FD-333: committed-entity edits and deletes ---

def test_apply_deltas_stages_committed_edit():
    """Positive-id delta for a committed person is added to pdp.people."""
    deltas = PDPDeltas(people=[Person(id=10, name="Alicia")])
    new_pdp = apply_deltas(PDP(), deltas)
    assert len(new_pdp.people) == 1
    assert new_pdp.people[0].id == 10
    assert new_pdp.people[0].name == "Alicia"


def test_apply_deltas_stages_committed_delete():
    """Positive-id in deltas.delete is staged in committed_deletes."""
    deltas = PDPDeltas(delete=[10])
    new_pdp = apply_deltas(PDP(), deltas)
    assert 10 in new_pdp.committed_deletes


def test_accept_committed_edit_applies_to_diagram():
    """accept_committed_edit merges pdp.people entry into the committed entity."""
    diagram_data = DiagramData(
        people=[{"id": 10, "name": "Alice", "gender": "female"}],
        pdp=PDP(people=[Person(id=10, name="Alicia")]),
    )
    diagram_data.accept_committed_edit(10)
    assert diagram_data.people[0]["name"] == "Alicia"
    assert diagram_data.pdp.people == []


def test_reject_committed_edit_discards_staged_edit():
    """reject_committed_edit drops the pdp entry without touching the committed entity."""
    diagram_data = DiagramData(
        people=[{"id": 10, "name": "Alice"}],
        pdp=PDP(people=[Person(id=10, name="Alicia")]),
    )
    diagram_data.reject_committed_edit(10)
    assert diagram_data.people[0]["name"] == "Alice"
    assert diagram_data.pdp.people == []


def test_accept_committed_delete_cascade():
    """accept_committed_delete removes the person plus all dependent events and pair bonds."""
    diagram_data = DiagramData(
        people=[
            {"id": 10, "name": "Alice"},
            {"id": 11, "name": "Bob"},
        ],
        events=[
            {"id": 20, "kind": "shift", "person": 10, "description": "x", "dateTime": "2000-01-01"},
        ],
        pair_bonds=[{"id": 30, "person_a": 10, "person_b": 11}],
        pdp=PDP(committed_deletes=[10]),
    )
    diagram_data.accept_committed_delete(10)
    assert all(p["id"] != 10 for p in diagram_data.people)
    assert diagram_data.events == []
    assert diagram_data.pair_bonds == []
    assert 10 not in diagram_data.pdp.committed_deletes


def test_reject_committed_delete_clears_queue():
    """reject_committed_delete drops the pending delete; committed entity unchanged."""
    diagram_data = DiagramData(
        people=[{"id": 10, "name": "Alice"}],
        pdp=PDP(committed_deletes=[10]),
    )
    diagram_data.reject_committed_delete(10)
    assert diagram_data.people[0]["id"] == 10
    assert diagram_data.pdp.committed_deletes == []


def test_accept_committed_edit_raises_on_missing():
    """accept_committed_edit raises ValueError when no staged edit for id."""
    diagram_data = DiagramData(
        people=[{"id": 10, "name": "Alice"}],
        pdp=PDP(),
    )
    with pytest.raises(ValueError, match="No pending committed edit"):
        diagram_data.accept_committed_edit(10)


def test_accept_committed_delete_raises_on_missing():
    """accept_committed_delete raises ValueError when id not in committed_deletes."""
    diagram_data = DiagramData(
        people=[{"id": 10, "name": "Alice"}],
        pdp=PDP(),
    )
    with pytest.raises(ValueError, match="No pending committed delete"):
        diagram_data.accept_committed_delete(10)


# ── infer_parents_from_birth_events ─────────────────────────────────────────


def test_infer_parents_sets_child_parents():
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
            Person(id=-3, name="Child"),
        ],
        pair_bonds=[PairBond(id=-10, person_a=-1, person_b=-2)],
        events=[
            Event(id=-20, kind=EventKind.Birth, person=-1, spouse=-2, child=-3, dateTime="2000-01-01")
        ],
    )
    infer_parents_from_birth_events(deltas)
    assert deltas.people[2].parents == -10


def test_infer_parents_does_not_overwrite_existing():
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
            Person(id=-3, name="Child", parents=-99),
        ],
        pair_bonds=[PairBond(id=-10, person_a=-1, person_b=-2)],
        events=[
            Event(id=-20, kind=EventKind.Birth, person=-1, spouse=-2, child=-3, dateTime="2000-01-01")
        ],
    )
    infer_parents_from_birth_events(deltas)
    assert deltas.people[2].parents == -99


def test_infer_parents_skips_missing_bond():
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
            Person(id=-3, name="Child"),
        ],
        pair_bonds=[],
        events=[
            Event(id=-20, kind=EventKind.Birth, person=-1, spouse=-2, child=-3, dateTime="2000-01-01")
        ],
    )
    infer_parents_from_birth_events(deltas)
    assert deltas.people[2].parents is None


def test_infer_parents_adopted_event():
    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Mom"),
            Person(id=-2, name="Dad"),
            Person(id=-3, name="Child"),
        ],
        pair_bonds=[PairBond(id=-10, person_a=-1, person_b=-2)],
        events=[
            Event(id=-20, kind=EventKind.Adopted, person=-1, spouse=-2, child=-3, dateTime="2005-06-01")
        ],
    )
    infer_parents_from_birth_events(deltas)
    assert deltas.people[2].parents == -10


def test_infer_parents_ignores_non_birth_events():
    deltas = PDPDeltas(
        people=[Person(id=-3, name="Child")],
        pair_bonds=[PairBond(id=-10, person_a=-1, person_b=-2)],
        events=[
            Event(id=-20, kind=EventKind.Shift, person=-3, description="Anxiety spike")
        ],
    )
    infer_parents_from_birth_events(deltas)
    assert deltas.people[0].parents is None
