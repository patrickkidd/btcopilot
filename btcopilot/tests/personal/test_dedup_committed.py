"""Tests for deterministic deduplication of extraction results against committed items.

Verifies that re-extraction on an already-populated diagram is idempotent:
duplicate people, events, and pair bonds are stripped before they enter the PDP.
"""

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
from btcopilot.pdp import (
    dedup_against_committed,
    apply_deltas,
    validate_pdp_deltas,
    _normalize_name,
)


# ── helpers ──────────────────────────────────────────────────────────


def _committed_person(id: int, name: str, **kw) -> dict:
    """Create a committed person dict (positive ID, confidence 1.0)."""
    return {**asdict(Person(id=id, name=name, confidence=1.0, **kw))}


def _committed_event(id: int, kind: EventKind, **kw) -> dict:
    return {**asdict(Event(id=id, kind=kind, confidence=1.0, **kw))}


def _committed_pair_bond(id: int, person_a: int, person_b: int) -> dict:
    return {**asdict(PairBond(id=id, person_a=person_a, person_b=person_b, confidence=1.0))}


# ── _normalize_name ──────────────────────────────────────────────────


class TestNormalizeName:
    def test_basic(self):
        assert _normalize_name("John") == "john"

    def test_strips_whitespace(self):
        assert _normalize_name("  John  ") == "john"

    def test_collapses_inner_whitespace(self):
        assert _normalize_name("John   Doe") == "john doe"

    def test_none(self):
        assert _normalize_name(None) == ""

    def test_empty(self):
        assert _normalize_name("") == ""


# ── People dedup ─────────────────────────────────────────────────────


class TestPeopleDedup:
    def test_exact_name_match_removes_duplicate(self):
        """Person with same name as committed person is removed from deltas."""
        diagram_data = DiagramData(
            people=[_committed_person(5, "John")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_case_insensitive_match(self):
        diagram_data = DiagramData(
            people=[_committed_person(5, "John")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="john", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_whitespace_normalization(self):
        diagram_data = DiagramData(
            people=[_committed_person(5, "  John  ")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_different_name_kept(self):
        diagram_data = DiagramData(
            people=[_committed_person(5, "John")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Jane", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Jane"

    def test_first_and_last_name_match(self):
        diagram_data = DiagramData(
            people=[_committed_person(5, "John", last_name="Smith")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John", last_name="Smith", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0

    def test_same_first_different_last_kept(self):
        diagram_data = DiagramData(
            people=[_committed_person(5, "John", last_name="Smith")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John", last_name="Doe", confidence=0.7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1

    def test_event_refs_remapped_to_committed_id(self):
        """When a person is deduped, event references are updated to committed ID."""
        diagram_data = DiagramData(
            people=[_committed_person(5, "John")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John", confidence=0.7)],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="felt anxious",
                    dateTime="2024-01-15",
                )
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0
        assert len(deltas.events) == 1
        assert deltas.events[0].person == 5  # remapped to committed ID

    def test_pair_bond_refs_remapped(self):
        """When people are deduped, pair bond person refs are updated."""
        diagram_data = DiagramData(
            people=[
                _committed_person(5, "John"),
                _committed_person(6, "Jane"),
            ],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="John", confidence=0.7),
                Person(id=-2, name="Jane", confidence=0.7),
            ],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 0
        assert len(deltas.pair_bonds) == 1
        assert deltas.pair_bonds[0].person_a == 5
        assert deltas.pair_bonds[0].person_b == 6

    def test_positive_id_people_not_touched(self):
        """People with positive IDs (committed updates) are never deduped."""
        diagram_data = DiagramData(
            people=[_committed_person(5, "John")],
        )
        deltas = PDPDeltas(
            people=[Person(id=5, name="John", confidence=1.0)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert deltas.people[0].id == 5


# ── PairBond dedup ───────────────────────────────────────────────────


class TestPairBondDedup:
    def test_matching_dyad_removed(self):
        diagram_data = DiagramData(
            pair_bonds=[_committed_pair_bond(10, 5, 6)],
        )
        deltas = PDPDeltas(
            pair_bonds=[PairBond(id=-3, person_a=5, person_b=6)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.pair_bonds) == 0

    def test_reversed_dyad_still_matches(self):
        """Dyad (5,6) matches committed (6,5) since order is irrelevant."""
        diagram_data = DiagramData(
            pair_bonds=[_committed_pair_bond(10, 6, 5)],
        )
        deltas = PDPDeltas(
            pair_bonds=[PairBond(id=-3, person_a=5, person_b=6)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.pair_bonds) == 0

    def test_different_dyad_kept(self):
        diagram_data = DiagramData(
            pair_bonds=[_committed_pair_bond(10, 5, 6)],
        )
        deltas = PDPDeltas(
            pair_bonds=[PairBond(id=-3, person_a=5, person_b=7)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.pair_bonds) == 1

    def test_parents_ref_remapped(self):
        """When a pair bond is deduped, person.parents refs are updated."""
        diagram_data = DiagramData(
            pair_bonds=[_committed_pair_bond(10, 5, 6)],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Child", parents=-3)],
            pair_bonds=[PairBond(id=-3, person_a=5, person_b=6)],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.pair_bonds) == 0
        assert deltas.people[0].parents == 10  # remapped to committed ID


# ── Event dedup ──────────────────────────────────────────────────────


class TestEventDedup:
    def test_structural_event_match(self):
        """Birth event with same kind + person refs is removed."""
        diagram_data = DiagramData(
            events=[
                _committed_event(
                    20,
                    EventKind.Birth,
                    person=5,
                    spouse=6,
                    child=7,
                    dateTime="2020-06-15",
                )
            ],
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-10,
                    kind=EventKind.Birth,
                    person=5,
                    spouse=6,
                    child=7,
                    dateTime="2020-06-15",
                )
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 0

    def test_shift_event_same_description_removed(self):
        """Shift events also match on normalized description."""
        diagram_data = DiagramData(
            events=[
                _committed_event(
                    20,
                    EventKind.Shift,
                    person=5,
                    description="Felt anxious about work",
                    dateTime="2024-01-15",
                )
            ],
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-10,
                    kind=EventKind.Shift,
                    person=5,
                    description="felt anxious about work",
                    dateTime="2024-01-15",
                )
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 0

    def test_shift_event_different_description_kept(self):
        diagram_data = DiagramData(
            events=[
                _committed_event(
                    20,
                    EventKind.Shift,
                    person=5,
                    description="Felt anxious about work",
                    dateTime="2024-01-15",
                )
            ],
        )
        deltas = PDPDeltas(
            events=[
                Event(
                    id=-10,
                    kind=EventKind.Shift,
                    person=5,
                    description="Started new medication",
                    dateTime="2024-02-01",
                )
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 1

    def test_different_kind_kept(self):
        diagram_data = DiagramData(
            events=[
                _committed_event(20, EventKind.Married, person=5, spouse=6)
            ],
        )
        deltas = PDPDeltas(
            events=[
                Event(id=-10, kind=EventKind.Divorced, person=5, spouse=6, dateTime="2024-06-01"),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 1

    def test_positive_id_events_not_touched(self):
        """Events with positive IDs are not candidates for dedup removal."""
        diagram_data = DiagramData(
            events=[
                _committed_event(20, EventKind.Shift, person=5, description="X", dateTime="2024-01-01")
            ],
        )
        deltas = PDPDeltas(
            events=[
                Event(id=20, kind=EventKind.Shift, person=5, description="X", dateTime="2024-01-01"),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.events) == 1


# ── Integration: full pipeline idempotency ───────────────────────────


class TestReExtractionIdempotency:
    """Simulate re-extraction on an already-populated diagram and verify
    the resulting PDP contains no duplicates of committed items."""

    def test_full_idempotency_people_and_events(self):
        """After committing items, re-extraction producing the same data
        should yield an empty PDP."""
        # Setup: diagram already has committed people + events
        diagram_data = DiagramData(
            lastItemId=25,
            people=[
                _committed_person(5, "John"),
                _committed_person(6, "Jane"),
                _committed_person(7, "Baby"),
            ],
            events=[
                _committed_event(
                    20,
                    EventKind.Married,
                    person=5,
                    spouse=6,
                    dateTime="2015-06-01",
                ),
                _committed_event(
                    21,
                    EventKind.Birth,
                    person=5,
                    spouse=6,
                    child=7,
                    dateTime="2018-03-10",
                ),
            ],
            pair_bonds=[_committed_pair_bond(10, 5, 6)],
            pdp=PDP(),  # cleared before extraction
        )

        # LLM re-extracts the same people/events (with negative IDs)
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="John", confidence=0.8),
                Person(id=-2, name="Jane", confidence=0.8),
                Person(id=-5, name="Baby", confidence=0.8),
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Married,
                    person=-1,
                    spouse=-2,
                    dateTime="2015-06-01",
                ),
                Event(
                    id=-4,
                    kind=EventKind.Birth,
                    person=-1,
                    spouse=-2,
                    child=-5,
                    dateTime="2018-03-10",
                ),
            ],
            pair_bonds=[PairBond(id=-6, person_a=-1, person_b=-2)],
        )

        dedup_against_committed(deltas, diagram_data)

        # Everything should be removed as duplicates
        assert len(deltas.people) == 0
        assert len(deltas.pair_bonds) == 0
        assert len(deltas.events) == 0

    def test_mixed_new_and_duplicate(self):
        """Duplicates removed but genuinely new items preserved."""
        diagram_data = DiagramData(
            lastItemId=25,
            people=[_committed_person(5, "John")],
            events=[
                _committed_event(
                    20, EventKind.Shift, person=5,
                    description="felt anxious", dateTime="2024-01-15",
                ),
            ],
            pdp=PDP(),
        )

        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="John", confidence=0.8),  # duplicate
                Person(id=-2, name="Sarah", confidence=0.7),  # new
            ],
            events=[
                Event(
                    id=-3, kind=EventKind.Shift, person=-1,
                    description="felt anxious", dateTime="2024-01-15",
                ),  # duplicate (person ref will be remapped to 5)
                Event(
                    id=-4, kind=EventKind.Shift, person=-2,
                    description="started therapy", dateTime="2024-02-01",
                ),  # new
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Sarah"
        assert len(deltas.events) == 1
        assert deltas.events[0].description == "started therapy"
        assert deltas.events[0].person == -2  # Sarah's PDP ID unchanged

    def test_dedup_then_apply_deltas(self):
        """Full pipeline: dedup then apply_deltas produces clean PDP."""
        diagram_data = DiagramData(
            lastItemId=25,
            people=[
                _committed_person(5, "John"),
                _committed_person(6, "Jane"),
            ],
            pair_bonds=[_committed_pair_bond(10, 5, 6)],
            pdp=PDP(),
        )

        # LLM produces: duplicates of John/Jane + new person Sarah
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="John", confidence=0.8),
                Person(id=-2, name="Jane", confidence=0.8),
                Person(id=-3, name="Sarah", confidence=0.7),
            ],
            pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
            events=[
                Event(
                    id=-5, kind=EventKind.Shift, person=-3,
                    description="new event", dateTime="2024-03-01",
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)
        validate_pdp_deltas(diagram_data.pdp, deltas, diagram_data)
        new_pdp = apply_deltas(diagram_data.pdp, deltas)

        # Only Sarah and her event should be in PDP
        assert len(new_pdp.people) == 1
        assert new_pdp.people[0].name == "Sarah"
        assert len(new_pdp.events) == 1
        assert new_pdp.events[0].description == "new event"
        # Duplicate pair bond should be gone
        assert len(new_pdp.pair_bonds) == 0

    def test_dedup_with_relationship_targets_remapped(self):
        """Relationship event targets are remapped when people are deduped."""
        diagram_data = DiagramData(
            people=[
                _committed_person(5, "John"),
                _committed_person(6, "Jane"),
            ],
            pdp=PDP(),
        )

        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="John", confidence=0.8),
                Person(id=-2, name="Jane", confidence=0.8),
                Person(id=-3, name="Bob", confidence=0.7),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Shift,
                    person=-3,
                    description="triangle activation",
                    dateTime="2024-01-01",
                    relationshipTargets=[-1],
                    relationshipTriangles=[-2],
                ),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1  # only Bob
        event = deltas.events[0]
        assert event.relationshipTargets == [5]  # remapped John
        assert event.relationshipTriangles == [6]  # remapped Jane

    def test_empty_diagram_no_dedup(self):
        """No committed items → no dedup → all deltas kept."""
        diagram_data = DiagramData(pdp=PDP())
        deltas = PDPDeltas(
            people=[Person(id=-1, name="John")],
            events=[
                Event(id=-2, kind=EventKind.Shift, person=-1, description="X", dateTime="2024-01-01"),
            ],
        )

        dedup_against_committed(deltas, diagram_data)

        assert len(deltas.people) == 1
        assert len(deltas.events) == 1

    def test_none_diagram_data_no_crash(self):
        """None diagram_data is a no-op."""
        deltas = PDPDeltas(people=[Person(id=-1, name="John")])
        dedup_against_committed(deltas, None)
        assert len(deltas.people) == 1
