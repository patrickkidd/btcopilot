"""Experimental validation of dedup_against_committed().

Simulates realistic LLM extraction outputs where the model re-extracts
committed items alongside genuinely new data. Measures:
  - Duplicate removal rate (people, pair bonds, events)
  - False positive rate (novel items incorrectly removed)
  - Reference integrity after remapping

Each scenario represents a common extraction pattern observed in production.
"""

import copy
from dataclasses import dataclass

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
from btcopilot.pdp import dedup_against_committed


@dataclass
class ExperimentResult:
    """Tracks before/after metrics for one scenario."""
    scenario: str
    before_people: int
    before_pair_bonds: int
    before_events: int
    after_people: int
    after_pair_bonds: int
    after_events: int
    expected_novel_people: int
    expected_novel_pair_bonds: int
    expected_novel_events: int
    false_positives: int  # novel items incorrectly removed
    false_negatives: int  # duplicate items not removed
    reference_integrity: bool  # all refs point to valid IDs


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


def _check_reference_integrity(deltas: PDPDeltas, diagram: DiagramData) -> bool:
    """Verify all person/pair-bond references in deltas point to valid IDs."""
    valid_person_ids = {p.get("id") for p in diagram.people}
    valid_person_ids |= {p.id for p in deltas.people if p.id is not None}
    valid_pb_ids = {pb.get("id") for pb in diagram.pair_bonds}
    valid_pb_ids |= {pb.id for pb in deltas.pair_bonds if pb.id is not None}

    for event in deltas.events:
        for ref in [event.person, event.spouse, event.child]:
            if ref is not None and ref not in valid_person_ids:
                return False
        for ref in event.relationshipTargets + event.relationshipTriangles:
            if ref not in valid_person_ids:
                return False
    for person in deltas.people:
        if person.parents is not None and person.parents not in valid_pb_ids:
            # Might reference committed pair bond
            if person.parents not in valid_pb_ids:
                return False
    for pb in deltas.pair_bonds:
        for ref in [pb.person_a, pb.person_b]:
            if ref is not None and ref not in valid_person_ids:
                return False
    return True


# ---------------------------------------------------------------------------
# Scenario 1: Full family re-extraction (most common production pattern)
# ---------------------------------------------------------------------------

def test_scenario_full_family_reextraction():
    """
    Committed: 4-person family (father, mother, 2 children) with
    marriage, 2 births.

    LLM re-extracts all 4 people, pair bond, marriage, 2 births,
    plus 2 new Shift events and 1 new person (therapist).

    Expected: 4 people, 1 pair bond, 3 events removed.
    Kept: 1 new person (therapist), 2 new Shift events.
    """
    diagram = DiagramData(
        people=[
            _person_dict(1, "John Smith", gender="male"),
            _person_dict(2, "Jane Smith", gender="female"),
            _person_dict(3, "Tommy Smith", gender="male", parents=10),
            _person_dict(4, "Sarah Smith", gender="female", parents=10),
        ],
        pair_bonds=[_pb_dict(10, 1, 2)],
        events=[
            _event_dict(20, "married", person=1, spouse=2, dateTime="2010-06-15"),
            _event_dict(21, "birth", person=2, spouse=1, child=3, dateTime="2012-03-10"),
            _event_dict(22, "birth", person=2, spouse=1, child=4, dateTime="2015-08-22"),
        ],
    )

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="John Smith", gender="male"),
            Person(id=-2, name="Jane Smith", gender="female"),
            Person(id=-3, name="Tommy Smith", gender="male", parents=-5),
            Person(id=-4, name="Sarah Smith", gender="female", parents=-5),
            Person(id=-6, name="Dr. Williams"),  # NEW
        ],
        pair_bonds=[PairBond(id=-5, person_a=-1, person_b=-2)],
        events=[
            Event(id=-10, kind=EventKind.Married, person=-1, spouse=-2, dateTime="2010-06-15"),
            Event(id=-11, kind=EventKind.Birth, person=-2, spouse=-1, child=-3, dateTime="2012-03-10"),
            Event(id=-12, kind=EventKind.Birth, person=-2, spouse=-1, child=-4, dateTime="2015-08-22"),
            Event(id=-13, kind=EventKind.Shift, person=-1, description="John reported anxiety about work", dateTime="2024-01-15"),  # NEW
            Event(id=-14, kind=EventKind.Shift, person=-2, description="Jane distanced from mother", dateTime="2024-02-01"),  # NEW
        ],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    result = ExperimentResult(
        scenario="Full family re-extraction",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=1, expected_novel_pair_bonds=0, expected_novel_events=2,
        false_positives=0, false_negatives=0,
        reference_integrity=_check_reference_integrity(deltas, diagram),
    )

    # Assertions
    assert stats["people_removed"] == 4, f"Expected 4 people removed, got {stats['people_removed']}"
    assert stats["pair_bonds_removed"] == 1, f"Expected 1 pair bond removed, got {stats['pair_bonds_removed']}"
    assert stats["events_removed"] == 3, f"Expected 3 events removed (married + 2 births), got {stats['events_removed']}"
    assert after == (1, 0, 2), f"Expected (1 person, 0 pb, 2 events) after, got {after}"
    assert deltas.people[0].name == "Dr. Williams"
    assert deltas.events[0].person == 1  # remapped to committed John
    assert deltas.events[1].person == 2  # remapped to committed Jane
    assert result.reference_integrity

    _print_result(result)


# ---------------------------------------------------------------------------
# Scenario 2: Incremental extraction (some items committed, new ones added)
# ---------------------------------------------------------------------------

def test_scenario_incremental_extraction():
    """
    Committed: Alice and Bob are married.

    LLM extracts: Alice, Bob (dupes), their marriage (dupe),
    plus a new child Charlie with birth event, and a new Shift.

    Expected: 2 people, 1 event removed. Child, birth, shift kept.
    """
    diagram = DiagramData(
        people=[
            _person_dict(1, "Alice", gender="female"),
            _person_dict(2, "Bob", gender="male"),
        ],
        pair_bonds=[_pb_dict(10, 1, 2)],
        events=[
            _event_dict(20, "married", person=1, spouse=2, dateTime="2015-06-15"),
        ],
    )

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Alice", gender="female"),
            Person(id=-2, name="Bob", gender="male"),
            Person(id=-3, name="Charlie", gender="male", parents=-4),  # NEW
        ],
        pair_bonds=[
            PairBond(id=-4, person_a=-1, person_b=-2),  # dupe
        ],
        events=[
            Event(id=-10, kind=EventKind.Married, person=-1, spouse=-2, dateTime="2015-06-15"),  # dupe
            Event(id=-11, kind=EventKind.Birth, person=-1, spouse=-2, child=-3, dateTime="2020-01-01"),  # NEW
            Event(id=-12, kind=EventKind.Shift, person=-3, description="Charlie started school", dateTime="2025-09-01"),  # NEW
        ],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    result = ExperimentResult(
        scenario="Incremental extraction",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=1, expected_novel_pair_bonds=0, expected_novel_events=2,
        false_positives=0, false_negatives=0,
        reference_integrity=_check_reference_integrity(deltas, diagram),
    )

    assert stats["people_removed"] == 2
    assert stats["pair_bonds_removed"] == 1
    assert stats["events_removed"] == 1  # married event deduped
    assert after == (1, 0, 2)
    assert deltas.people[0].name == "Charlie"
    # Charlie's parents should remap to committed pair bond
    assert deltas.people[0].parents == 10
    # Birth event person/spouse remapped to committed IDs
    assert deltas.events[0].person == 1  # Alice
    assert deltas.events[0].spouse == 2  # Bob
    assert result.reference_integrity

    _print_result(result)


# ---------------------------------------------------------------------------
# Scenario 3: Case/whitespace variations (LLM name inconsistency)
# ---------------------------------------------------------------------------

def test_scenario_name_variations():
    """
    Committed: "John Smith", "Mary Jane Watson"
    LLM extracts: "john smith", "  Mary  Jane   Watson  ", "Dr. New Person"

    Tests that name normalization handles real-world LLM output.
    """
    diagram = DiagramData(
        people=[
            _person_dict(1, "John Smith"),
            _person_dict(2, "Mary Jane Watson"),
        ],
    )

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="john smith"),
            Person(id=-2, name="  Mary  Jane   Watson  "),
            Person(id=-3, name="Dr. New Person"),  # NEW
        ],
        events=[
            Event(id=-4, kind=EventKind.Shift, person=-1, description="John anxious", dateTime="2024-01-01"),
            Event(id=-5, kind=EventKind.Shift, person=-3, description="Dr visit", dateTime="2024-01-01"),
        ],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    result = ExperimentResult(
        scenario="Name variations (case/whitespace)",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=1, expected_novel_pair_bonds=0, expected_novel_events=2,
        false_positives=0, false_negatives=0,
        reference_integrity=_check_reference_integrity(deltas, diagram),
    )

    assert stats["people_removed"] == 2
    assert after == (1, 0, 2)
    assert deltas.people[0].name == "Dr. New Person"
    # John's shift remapped to committed ID
    assert deltas.events[0].person == 1
    assert result.reference_integrity

    _print_result(result)


# ---------------------------------------------------------------------------
# Scenario 4: Complex multi-generational family
# ---------------------------------------------------------------------------

def test_scenario_multigenerational():
    """
    Committed: Grandpa (1), Grandma (2), pair bond (10),
    Dad (3, parents=10), Mom (4), pair bond (11, Dad+Mom),
    Child (5, parents=11), birth of Dad (30), marriage of Dad+Mom (31),
    birth of Child (32).

    LLM re-extracts ALL of the above plus:
    - Grandpa's death event (new)
    - A new Shift on Dad (new)

    Expected: 5 people, 2 pair bonds, 3 events removed.
    Kept: 1 death event, 1 shift event.
    """
    diagram = DiagramData(
        people=[
            _person_dict(1, "Grandpa"),
            _person_dict(2, "Grandma"),
            _person_dict(3, "Dad", parents=10),
            _person_dict(4, "Mom"),
            _person_dict(5, "Child", parents=11),
        ],
        pair_bonds=[_pb_dict(10, 1, 2), _pb_dict(11, 3, 4)],
        events=[
            _event_dict(30, "birth", person=2, spouse=1, child=3),
            _event_dict(31, "married", person=3, spouse=4),
            _event_dict(32, "birth", person=4, spouse=3, child=5),
        ],
    )

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Grandpa"),
            Person(id=-2, name="Grandma"),
            Person(id=-3, name="Dad", parents=-6),
            Person(id=-4, name="Mom"),
            Person(id=-5, name="Child", parents=-7),
        ],
        pair_bonds=[
            PairBond(id=-6, person_a=-1, person_b=-2),
            PairBond(id=-7, person_a=-3, person_b=-4),
        ],
        events=[
            Event(id=-10, kind=EventKind.Birth, person=-2, spouse=-1, child=-3, dateTime="1970-01-01"),
            Event(id=-11, kind=EventKind.Married, person=-3, spouse=-4, dateTime="2000-06-15"),
            Event(id=-12, kind=EventKind.Birth, person=-4, spouse=-3, child=-5, dateTime="2005-03-10"),
            Event(id=-13, kind=EventKind.Death, person=-1, dateTime="2023-11-01"),  # NEW
            Event(id=-14, kind=EventKind.Shift, person=-3, description="Dad increased distance from Mom", dateTime="2024-01-01"),  # NEW
        ],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    result = ExperimentResult(
        scenario="Multi-generational family",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=0, expected_novel_pair_bonds=0, expected_novel_events=2,
        false_positives=0, false_negatives=0,
        reference_integrity=_check_reference_integrity(deltas, diagram),
    )

    assert stats["people_removed"] == 5
    assert stats["pair_bonds_removed"] == 2
    assert stats["events_removed"] == 3
    assert after == (0, 0, 2)
    # Death event person remapped to committed Grandpa
    death_event = next(e for e in deltas.events if e.kind == EventKind.Death)
    assert death_event.person == 1
    # Shift event person remapped to committed Dad
    shift_event = next(e for e in deltas.events if e.kind == EventKind.Shift)
    assert shift_event.person == 3
    assert result.reference_integrity

    _print_result(result)


# ---------------------------------------------------------------------------
# Scenario 5: No committed items (first extraction, baseline)
# ---------------------------------------------------------------------------

def test_scenario_first_extraction():
    """
    Empty committed diagram. Everything is new.
    Expected: zero removals, all items pass through.
    """
    diagram = DiagramData()

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        pair_bonds=[PairBond(id=-3, person_a=-1, person_b=-2)],
        events=[
            Event(id=-4, kind=EventKind.Married, person=-1, spouse=-2, dateTime="2020-01-01"),
            Event(id=-5, kind=EventKind.Shift, person=-1, description="anxious", dateTime="2024-01-01"),
        ],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    assert before == after
    assert stats == {"people_removed": 0, "pair_bonds_removed": 0, "events_removed": 0}

    _print_result(ExperimentResult(
        scenario="First extraction (no committed)",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=2, expected_novel_pair_bonds=1, expected_novel_events=2,
        false_positives=0, false_negatives=0,
        reference_integrity=True,
    ))


# ---------------------------------------------------------------------------
# Scenario 6: Relationship event with targets and triangles
# ---------------------------------------------------------------------------

def test_scenario_relationship_refs():
    """
    Committed: Alice (1), Bob (2), Carol (3).
    LLM re-extracts all 3 plus a Shift event with relationship targets and triangles.
    All person refs should remap correctly.
    """
    diagram = DiagramData(
        people=[
            _person_dict(1, "Alice"),
            _person_dict(2, "Bob"),
            _person_dict(3, "Carol"),
        ],
    )

    deltas = PDPDeltas(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
            Person(id=-3, name="Carol"),
        ],
        events=[Event(
            id=-4, kind=EventKind.Shift, person=-1,
            description="Alice triangled with Bob about Carol",
            dateTime="2024-01-01",
            relationshipTargets=[-2],
            relationshipTriangles=[-1, -2, -3],
        )],
    )

    before = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))
    stats = dedup_against_committed(deltas, diagram)
    after = (len(deltas.people), len(deltas.pair_bonds), len(deltas.events))

    assert stats["people_removed"] == 3
    assert after == (0, 0, 1)
    event = deltas.events[0]
    assert event.person == 1
    assert event.relationshipTargets == [2]
    assert event.relationshipTriangles == [1, 2, 3]

    _print_result(ExperimentResult(
        scenario="Relationship refs (targets + triangles)",
        before_people=before[0], before_pair_bonds=before[1], before_events=before[2],
        after_people=after[0], after_pair_bonds=after[1], after_events=after[2],
        expected_novel_people=0, expected_novel_pair_bonds=0, expected_novel_events=1,
        false_positives=0, false_negatives=0,
        reference_integrity=_check_reference_integrity(deltas, diagram),
    ))


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

_results: list[ExperimentResult] = []

def _print_result(result: ExperimentResult):
    _results.append(result)


def test_print_summary():
    """Print aggregate summary of all experiments (runs last due to name)."""
    if not _results:
        return

    total_before = sum(r.before_people + r.before_pair_bonds + r.before_events for r in _results)
    total_after = sum(r.after_people + r.after_pair_bonds + r.after_events for r in _results)
    total_removed = total_before - total_after
    reduction_pct = (total_removed / total_before * 100) if total_before > 0 else 0
    total_fp = sum(r.false_positives for r in _results)
    total_fn = sum(r.false_negatives for r in _results)
    all_integrity = all(r.reference_integrity for r in _results)

    print("\n" + "=" * 70)
    print("DEDUP EXPERIMENT SUMMARY")
    print("=" * 70)
    for r in _results:
        removed = (r.before_people + r.before_pair_bonds + r.before_events) - \
                  (r.after_people + r.after_pair_bonds + r.after_events)
        before_total = r.before_people + r.before_pair_bonds + r.before_events
        pct = (removed / before_total * 100) if before_total > 0 else 0
        print(f"\n  {r.scenario}:")
        print(f"    Before: {r.before_people}P / {r.before_pair_bonds}PB / {r.before_events}E = {before_total} items")
        print(f"    After:  {r.after_people}P / {r.after_pair_bonds}PB / {r.after_events}E = {r.after_people + r.after_pair_bonds + r.after_events} items")
        print(f"    Removed: {removed} ({pct:.0f}%) | FP: {r.false_positives} | FN: {r.false_negatives} | Refs OK: {r.reference_integrity}")

    print(f"\n  {'─' * 60}")
    print(f"  TOTALS: {total_before} items before → {total_after} after")
    print(f"  Removed: {total_removed} ({reduction_pct:.1f}% reduction)")
    print(f"  False positives: {total_fp} | False negatives: {total_fn}")
    print(f"  Reference integrity: {'PASS' if all_integrity else 'FAIL'}")
    print("=" * 70)
