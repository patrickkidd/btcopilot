"""Tests for dedup_against_committed() — deterministic post-filter that removes
LLM-extracted items duplicating already-committed diagram data.

Three phases:
  1. People matched by normalized name (case-insensitive, whitespace-collapsed)
  2. PairBonds matched by unordered person dyad (after person remapping)
  3. Self-describing events matched by kind + person refs (Shift excluded)
"""

import copy
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
from btcopilot.pdp import dedup_against_committed, _normalize_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _diagram_with_committed(
    people: list[dict] | None = None,
    events: list[dict] | None = None,
    pair_bonds: list[dict] | None = None,
) -> DiagramData:
    """Create a DiagramData with committed items (positive IDs, dict format)."""
    return DiagramData(
        people=people or [],
        events=events or [],
        pair_bonds=pair_bonds or [],
    )


def _person_dict(id: int, name: str, **kwargs) -> dict:
    d = {"id": id, "name": name}
    d.update(kwargs)
    return d


def _event_dict(id: int, kind: str, **kwargs) -> dict:
    d = {"id": id, "kind": kind}
    d.update(kwargs)
    return d


def _pb_dict(id: int, person_a: int, person_b: int) -> dict:
    return {"id": id, "person_a": person_a, "person_b": person_b}


# ===========================================================================
# _normalize_name
# ===========================================================================

class TestNormalizeName:
    def test_none(self):
        assert _normalize_name(None) is None

    def test_basic(self):
        assert _normalize_name("Alice") == "alice"

    def test_case_insensitive(self):
        assert _normalize_name("ALICE") == "alice"

    def test_whitespace_collapse(self):
        assert _normalize_name("  Alice   Smith  ") == "alice smith"

    def test_mixed(self):
        assert _normalize_name("  ALICE   smith  ") == "alice smith"


# ===========================================================================
# Phase 1: People by normalized name
# ===========================================================================

class TestDedupPeople:
    def test_no_committed_people(self):
        """No committed people → nothing removed."""
        diagram = _diagram_with_committed()
        deltas = PDPDeltas(people=[Person(id=-1, name="Alice")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 1
        assert stats["people_removed"] == 0

    def test_no_match(self):
        """Different names → nothing removed."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[Person(id=-1, name="Bob")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 1
        assert stats["people_removed"] == 0

    def test_exact_match(self):
        """Exact name match → person removed."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[Person(id=-1, name="Alice")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 0
        assert stats["people_removed"] == 1

    def test_case_insensitive_match(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[Person(id=-1, name="alice")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 0
        assert stats["people_removed"] == 1

    def test_whitespace_match(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice Smith")])
        deltas = PDPDeltas(people=[Person(id=-1, name="  Alice   Smith  ")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 0
        assert stats["people_removed"] == 1

    def test_multiple_people_mixed(self):
        """One match, one novel → only match removed."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Bob"
        assert stats["people_removed"] == 1

    def test_positive_id_not_removed(self):
        """People with positive IDs (committed updates) are never removed."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[Person(id=1, name="Alice")])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 1
        assert stats["people_removed"] == 0

    def test_empty_deltas(self):
        """Empty deltas → no-op."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas()
        stats = dedup_against_committed(deltas, diagram)
        assert stats["people_removed"] == 0

    def test_none_name_not_matched(self):
        """Person with None name is never matched."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(people=[Person(id=-1, name=None)])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 1
        assert stats["people_removed"] == 0


# ===========================================================================
# Phase 1 → Reference remapping
# ===========================================================================

class TestPersonRemapping:
    def test_event_person_remapped(self):
        """When person is deduped, event.person remaps to committed ID."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[Event(id=-2, kind=EventKind.Shift, person=-1, description="test", dateTime="2024-01-01")],
        )
        dedup_against_committed(deltas, diagram)
        assert len(deltas.people) == 0
        assert deltas.events[0].person == 1  # remapped to committed

    def test_event_spouse_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[Event(id=-2, kind=EventKind.Married, spouse=-1, person=-3, dateTime="2024-01-01")],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.events[0].spouse == 1

    def test_event_child_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[Event(id=-2, kind=EventKind.Birth, child=-1, person=-3, dateTime="2024-01-01")],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.events[0].child == 1

    def test_pair_bond_person_a_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.pair_bonds[0].person_a == 1  # Alice remapped
        assert deltas.pair_bonds[0].person_b == -2  # Bob kept

    def test_pair_bond_person_b_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Bob")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.pair_bonds[0].person_a == -1
        assert deltas.pair_bonds[0].person_b == 1  # Bob remapped

    def test_person_parents_remapped_from_person_remap(self):
        """When parent person is deduped, child's parents ref stays unchanged
        (parents is a pair bond ref, not person ref)."""
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice"),
                Person(id=-2, name="Child", parents=-5),
            ],
            pair_bonds=[PairBond(id=-5, person_a=-1, person_b=-3)],
        )
        dedup_against_committed(deltas, diagram)
        # parents is a pair_bond ref, not affected by person remap
        assert deltas.people[0].parents == -5

    def test_relationship_targets_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[Event(
                id=-2, kind=EventKind.Shift, person=-3,
                description="test", dateTime="2024-01-01",
                relationshipTargets=[-1, -4],
            )],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.events[0].relationshipTargets == [1, -4]

    def test_relationship_triangles_remapped(self):
        diagram = _diagram_with_committed(people=[_person_dict(1, "Alice")])
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice")],
            events=[Event(
                id=-2, kind=EventKind.Shift, person=-3,
                description="test", dateTime="2024-01-01",
                relationshipTriangles=[-1, -4],
            )],
        )
        dedup_against_committed(deltas, diagram)
        assert deltas.events[0].relationshipTriangles == [1, -4]


# ===========================================================================
# Phase 2: PairBonds by dyad
# ===========================================================================

class TestDedupPairBonds:
    def test_no_committed_pair_bonds(self):
        diagram = _diagram_with_committed()
        deltas = PDPDeltas(pair_bonds=[PairBond(id=-1, person_a=1, person_b=2)])
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.pair_bonds) == 1
        assert stats["pair_bonds_removed"] == 0

    def test_dyad_match(self):
        """Pair bond with same dyad as committed → removed."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(2, "Bob")],
            pair_bonds=[_pb_dict(10, 1, 2)],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )
        stats = dedup_against_committed(deltas, diagram)
        # After person dedup: person_a=1, person_b=2 → matches committed dyad
        assert len(deltas.pair_bonds) == 0
        assert stats["pair_bonds_removed"] == 1

    def test_dyad_match_reversed(self):
        """Reversed order dyad still matches."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(2, "Bob")],
            pair_bonds=[_pb_dict(10, 2, 1)],  # reversed
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.pair_bonds) == 0
        assert stats["pair_bonds_removed"] == 1

    def test_parents_remapped_after_pb_dedup(self):
        """When pair bond is deduped, person.parents remaps to committed pair bond ID."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(2, "Bob")],
            pair_bonds=[_pb_dict(10, 1, 2)],
        )
        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice"),
                Person(id=-2, name="Bob"),
                Person(id=-3, name="Child", parents=-4),
            ],
            pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.pair_bonds) == 0
        # Child's parents should remap to committed pair bond ID
        child = deltas.people[0]  # only Child remains
        assert child.name == "Child"
        assert child.parents == 10

    def test_novel_pair_bond_kept(self):
        """Pair bond with novel dyad → kept."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(2, "Bob")],
            pair_bonds=[_pb_dict(10, 1, 2)],
        )
        deltas = PDPDeltas(
            pair_bonds=[PairBond(id=-1, person_a=1, person_b=3)],  # novel dyad
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.pair_bonds) == 1
        assert stats["pair_bonds_removed"] == 0

    def test_positive_id_pair_bond_kept(self):
        """Pair bond with positive ID (committed update) is never removed."""
        diagram = _diagram_with_committed(
            pair_bonds=[_pb_dict(10, 1, 2)],
        )
        deltas = PDPDeltas(
            pair_bonds=[PairBond(id=10, person_a=1, person_b=2)],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.pair_bonds) == 1
        assert stats["pair_bonds_removed"] == 0


# ===========================================================================
# Phase 3: Self-describing events
# ===========================================================================

class TestDedupEvents:
    def test_no_committed_events(self):
        diagram = _diagram_with_committed()
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Married, person=1, spouse=2, dateTime="2024-01-01")]
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 1
        assert stats["events_removed"] == 0

    def test_married_event_deduped(self):
        """Married event matching committed kind+person → removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "married", person=1, spouse=2)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Married, person=1, spouse=2, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 0
        assert stats["events_removed"] == 1

    def test_birth_event_deduped_by_child(self):
        """Birth event matching committed kind+child → removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "birth", person=1, spouse=2, child=3)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Birth, child=3, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 0
        assert stats["events_removed"] == 1

    def test_birth_event_deduped_by_person(self):
        """Birth event matching committed kind+person → removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "birth", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Birth, person=1, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 0
        assert stats["events_removed"] == 1

    def test_death_event_deduped(self):
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "death", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Death, person=1, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 0
        assert stats["events_removed"] == 1

    def test_shift_event_NOT_deduped(self):
        """Shift events are intentionally kept — require description matching."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "shift", person=1, description="anxiety went up")],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Shift, person=1, description="anxiety went up", dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 1
        assert stats["events_removed"] == 0

    def test_different_kind_not_deduped(self):
        """Different event kind for same person → not removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "married", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Divorced, person=1, spouse=2, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 1
        assert stats["events_removed"] == 0

    def test_different_person_not_deduped(self):
        """Same kind, different person → not removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "married", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Married, person=99, spouse=2, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 1
        assert stats["events_removed"] == 0

    def test_positive_id_event_not_removed(self):
        """Events with positive IDs (committed updates) are never removed."""
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "married", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=10, kind=EventKind.Married, person=1, spouse=2, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 1
        assert stats["events_removed"] == 0

    def test_moved_event_deduped(self):
        diagram = _diagram_with_committed(
            events=[_event_dict(10, "moved", person=1)],
        )
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=EventKind.Moved, person=1, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert len(deltas.events) == 0
        assert stats["events_removed"] == 1


# ===========================================================================
# Integration: full family re-extraction
# ===========================================================================

class TestIntegration:
    def test_full_family_reextraction(self):
        """Simulate re-extracting a family that's already committed.

        Committed: Alice (1), Bob (2), pair bond (10), married event (20), birth of Child (21), Child (3).
        LLM re-extracts all of them plus a new Shift event.
        Expected: only the Shift event survives.
        """
        diagram = _diagram_with_committed(
            people=[
                _person_dict(1, "Alice", gender="female"),
                _person_dict(2, "Bob", gender="male"),
                _person_dict(3, "Child", gender="male", parents=10),
            ],
            pair_bonds=[_pb_dict(10, 1, 2)],
            events=[
                _event_dict(20, "married", person=1, spouse=2),
                _event_dict(21, "birth", person=1, spouse=2, child=3),
            ],
        )

        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice", gender="female"),
                Person(id=-2, name="Bob", gender="male"),
                Person(id=-3, name="Child", gender="male", parents=-4),
            ],
            pair_bonds=[PairBond(id=-4, person_a=-1, person_b=-2)],
            events=[
                Event(id=-5, kind=EventKind.Married, person=-1, spouse=-2, dateTime="2024-01-01"),
                Event(id=-6, kind=EventKind.Birth, person=-1, spouse=-2, child=-3, dateTime="2024-06-01"),
                Event(id=-7, kind=EventKind.Shift, person=-1, description="anxiety spike", dateTime="2024-09-01"),
            ],
        )

        stats = dedup_against_committed(deltas, diagram)

        # All 3 people removed
        assert stats["people_removed"] == 3
        assert len(deltas.people) == 0

        # Pair bond removed
        assert stats["pair_bonds_removed"] == 1
        assert len(deltas.pair_bonds) == 0

        # Married + Birth removed, Shift kept
        assert stats["events_removed"] == 2
        assert len(deltas.events) == 1
        assert deltas.events[0].kind == EventKind.Shift
        # Shift event person remapped to committed Alice
        assert deltas.events[0].person == 1

    def test_partial_overlap(self):
        """Some items are committed, some are genuinely new."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice")],
        )

        deltas = PDPDeltas(
            people=[
                Person(id=-1, name="Alice"),  # duplicate
                Person(id=-2, name="Charlie"),  # new
            ],
            events=[
                Event(id=-3, kind=EventKind.Shift, person=-1, description="test", dateTime="2024-01-01"),
                Event(id=-4, kind=EventKind.Shift, person=-2, description="new shift", dateTime="2024-01-01"),
            ],
        )

        stats = dedup_against_committed(deltas, diagram)

        assert stats["people_removed"] == 1
        assert len(deltas.people) == 1
        assert deltas.people[0].name == "Charlie"

        # Both shifts kept (Shift not deduped)
        assert len(deltas.events) == 2
        # Alice's shift remapped
        assert deltas.events[0].person == 1
        # Charlie's shift unchanged
        assert deltas.events[1].person == -2

    def test_no_committed_items_passthrough(self):
        """Empty committed diagram → all deltas pass through unchanged."""
        diagram = _diagram_with_committed()
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
            events=[
                Event(id=-4, kind=EventKind.Married, person=-1, spouse=-2, dateTime="2024-01-01"),
                Event(id=-5, kind=EventKind.Shift, person=-1, description="test", dateTime="2024-01-01"),
            ],
        )
        original_counts = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
        stats = dedup_against_committed(deltas, diagram)
        assert (len(deltas.people), len(deltas.pair_bonds), len(deltas.events)) == original_counts
        assert stats == {"people_removed": 0, "pair_bonds_removed": 0, "events_removed": 0}

    def test_adopted_event_deduped_by_child(self):
        """Adopted event matched by kind + child ref."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(3, "Child")],
            events=[_event_dict(20, "adopted", person=1, child=3)],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-3, name="Child")],
            events=[Event(id=-5, kind=EventKind.Adopted, person=-1, child=-3, dateTime="2024-01-01")],
        )
        stats = dedup_against_committed(deltas, diagram)
        assert stats["events_removed"] == 1
        assert len(deltas.events) == 0

    def test_chained_remapping(self):
        """Events referencing deduped people get their refs correctly chained through."""
        diagram = _diagram_with_committed(
            people=[_person_dict(1, "Alice"), _person_dict(2, "Bob")],
        )
        deltas = PDPDeltas(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            events=[Event(
                id=-3, kind=EventKind.Shift, person=-1,
                description="test", dateTime="2024-01-01",
                relationshipTargets=[-2],
                relationshipTriangles=[-1, -2],
            )],
        )
        dedup_against_committed(deltas, diagram)
        event = deltas.events[0]
        assert event.person == 1  # Alice → committed
        assert event.relationshipTargets == [2]  # Bob → committed
        assert event.relationshipTriangles == [1, 2]  # both remapped
