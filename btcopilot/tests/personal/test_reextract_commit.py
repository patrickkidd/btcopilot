"""
Offline e2e test: re-extraction with committed diagram items produces a PDP
containing only new items (negative IDs), and committing that PDP succeeds
without bad person references.

Based on diagram 1882 data structure: 15 committed people, 25 events, 6 pair bonds.
"""

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
)
from btcopilot.pdp import apply_deltas


def _diagram_1882():
    """Fixture: committed data from diagram 1882 (simplified)."""
    dd = DiagramData()
    dd.people = [
        {"id": 1, "name": "User", "gender": "male"},
        {"id": 23, "name": "Elizabeth Belgard", "gender": "female"},
        {"id": 46, "name": "Robert", "last_name": "Stinson", "gender": "male"},
        {"id": 16, "name": "Julie", "gender": "female"},
        {"id": 17, "name": "Jim O'Malley", "gender": "male"},
        {"id": 21, "name": "User's Dad", "gender": "male"},
        {"id": 42, "name": "Sam", "last_name": "Stinson", "gender": "male"},
        {"id": 45, "name": "Elizabeth", "last_name": "Belgard", "gender": "female"},
        {"id": 60, "name": "Person's spouse", "gender": "female"},
    ]
    dd.pair_bonds = [
        {"id": 3, "person_a": 16, "person_b": 21},
        {"id": 39, "person_a": 46, "person_b": 45},
        {"id": 59, "person_a": 1, "person_b": 60},
        {"id": 67, "person_a": 23, "person_b": 17},
        {"id": 68, "person_a": 23, "person_b": 46},
    ]
    dd.events = [
        {"id": 11, "kind": "married", "person": 16, "spouse": 21, "description": "Got married", "dateTime": "1990-01-01"},
        {"id": 61, "kind": "shift", "person": 1, "description": "Left father's house", "dateTime": "2015-01-01"},
        {"id": 62, "kind": "shift", "person": 46, "description": "Stayed out of conflict", "dateTime": "2015-01-01"},
        {"id": 71, "kind": "married", "person": 23, "spouse": 17, "description": "Married", "dateTime": "2010-01-01"},
        {"id": 75, "kind": "birth", "person": 46, "spouse": 23, "child": 46, "description": "Born", "dateTime": "1960-01-01"},
        {"id": 77, "kind": "birth", "person": 1, "spouse": 60, "child": 1, "description": "Born", "dateTime": "1995-01-01"},
    ]
    dd.lastItemId = 77
    dd.pdp = PDP()
    return dd


def _llm_deltas_with_committed_refs():
    """Simulate LLM output that references committed people by positive ID
    and adds new shift events with negative IDs."""
    return PDPDeltas(
        people=[
            # LLM references committed people by positive ID
            Person(id=1, name="User"),
            Person(id=23, name="Elizabeth Belgard"),
            Person(id=46, name="Robert Stinson"),
            Person(id=16, name="Julie"),
            Person(id=42, name="Sam Stinson"),
            # One genuinely new person
            Person(id=-1, name="Aunt Mary", gender="female"),
        ],
        events=[
            # New shift events referencing committed people
            Event(
                id=-10, kind=EventKind.Shift, person=1,
                description="Felt unwelcome at family gathering",
                dateTime="2023-06-01",
            ),
            Event(
                id=-11, kind=EventKind.Shift, person=46,
                description="Started new job",
                dateTime="2022-03-15",
            ),
            Event(
                id=-12, kind=EventKind.Shift, person=-1,
                description="Moved to town",
                dateTime="2021-01-01",
            ),
        ],
        pair_bonds=[
            # LLM references committed pair bond by positive ID
            PairBond(id=68, person_a=23, person_b=46),
        ],
    )


def test_apply_deltas_excludes_committed_people_from_pdp():
    """Positive-ID people in deltas are committed refs, not new PDP items."""
    dd = _diagram_1882()
    deltas = _llm_deltas_with_committed_refs()

    pdp = apply_deltas(dd.pdp, deltas)

    pdp_ids = {p.id for p in pdp.people}
    # Only the genuinely new person should be in PDP
    assert -1 in pdp_ids
    # Committed people (positive IDs) must NOT be in PDP
    for committed_id in [1, 23, 46, 16, 42]:
        assert committed_id not in pdp_ids, (
            f"Committed person {committed_id} should not be in PDP"
        )
    assert len(pdp.people) == 1
    assert pdp.people[0].name == "Aunt Mary"


def test_apply_deltas_excludes_committed_pair_bonds_from_pdp():
    """Positive-ID pair bonds in deltas are committed refs, not new PDP items."""
    dd = _diagram_1882()
    deltas = _llm_deltas_with_committed_refs()

    pdp = apply_deltas(dd.pdp, deltas)

    assert len(pdp.pair_bonds) == 0


def test_apply_deltas_keeps_new_events_in_pdp():
    """Negative-ID events should be added to PDP."""
    dd = _diagram_1882()
    deltas = _llm_deltas_with_committed_refs()

    pdp = apply_deltas(dd.pdp, deltas)

    assert len(pdp.events) == 3
    event_ids = {e.id for e in pdp.events}
    assert event_ids == {-10, -11, -12}


def test_commit_pdp_after_reextraction():
    """Full flow: apply deltas then commit all PDP items without errors."""
    dd = _diagram_1882()
    deltas = _llm_deltas_with_committed_refs()

    dd.pdp = apply_deltas(dd.pdp, deltas)

    # Collect all negative IDs for commit
    all_ids = [p.id for p in dd.pdp.people if p.id is not None and p.id < 0]
    all_ids += [e.id for e in dd.pdp.events if e.id < 0]
    all_ids += [pb.id for pb in dd.pdp.pair_bonds if pb.id is not None and pb.id < 0]

    prev_people = len(dd.people)
    prev_events = len(dd.events)

    id_mapping = dd.commit_pdp_items(all_ids)

    # All PDP items should be committed (PDP now empty)
    assert len(dd.pdp.people) == 0
    assert len(dd.pdp.events) == 0
    assert len(dd.pdp.pair_bonds) == 0

    # New person committed
    assert len(dd.people) == prev_people + 1
    # New events committed
    assert len(dd.events) == prev_events + 3

    # All new IDs are positive
    for new_id in id_mapping.values():
        assert new_id > 0

    # Events referencing committed people should have their positive IDs preserved
    new_event_dicts = [e for e in dd.events if e["id"] in id_mapping.values()]
    for event_dict in new_event_dicts:
        person_ref = event_dict.get("person")
        assert person_ref is not None
        assert person_ref > 0


def test_commit_pdp_events_referencing_committed_people():
    """Events that reference committed people by positive ID should commit
    with those references intact, not broken."""
    dd = _diagram_1882()
    dd.pdp = PDP(
        people=[],
        events=[
            Event(
                id=-5, kind=EventKind.Shift, person=46,
                description="Health issue",
                dateTime="2024-01-01",
            ),
        ],
        pair_bonds=[],
    )

    id_mapping = dd.commit_pdp_items([-5])

    new_event_id = id_mapping[-5]
    committed_event = next(e for e in dd.events if e["id"] == new_event_id)
    # person reference should still point to committed person 46
    assert committed_event["person"] == 46


def test_commit_pdp_mixed_positive_negative_refs():
    """Events referencing both committed (positive) and new (negative) people
    should have all references correctly resolved after commit."""
    dd = _diagram_1882()
    dd.pdp = PDP(
        people=[
            Person(id=-1, name="New Person", gender="female"),
        ],
        events=[
            Event(
                id=-10, kind=EventKind.Married, person=46, spouse=-1,
                description="Married", dateTime="2024-06-01",
            ),
        ],
        pair_bonds=[
            PairBond(id=-20, person_a=46, person_b=-1),
        ],
    )

    id_mapping = dd.commit_pdp_items([-10])

    new_event_id = id_mapping[-10]
    committed_event = next(e for e in dd.events if e["id"] == new_event_id)
    # person=46 stays positive (committed), spouse=-1 remapped to positive
    assert committed_event["person"] == 46
    assert committed_event["spouse"] > 0
    assert committed_event["spouse"] != -1
