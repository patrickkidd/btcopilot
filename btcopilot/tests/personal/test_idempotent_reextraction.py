"""
Tests for idempotent re-extraction: extracting the same discussion twice
and committing all items both times must not create duplicates or lose data.

Scenario:
1. extract_full() → PDP deltas
2. commit_pdp_items() → accept all
3. Record People / Events / PairBonds counts
4. extract_full() again on same discussion
5. commit_pdp_items() again
6. Assert counts unchanged (no duplicates, no deletions)

Two categories of tests:

A) Ideal LLM behavior (TestIdempotentReextractionInMemory, etc.):
   The LLM correctly returns empty on re-extraction because committed items
   are in the prompt. These test the "happy path."

B) LLM dedup failure (TestIdempotentLLMDedupFailure):
   The LLM ignores the "avoid duplicates with committed items" instruction
   and re-extracts the same people/events with new negative IDs. This is the
   real-world failure mode described in T7-9/T7-11 — tests whether the
   pipeline has rules-based dedup as a safety net (currently it doesn't for
   people/events, only for PairBonds).

   See: doc/analyses/T7-9_idempotent_reextraction.md
"""

import asyncio
import copy

import pytest
from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    DateCertainty,
    VariableShift,
    RelationshipKind,
)
from btcopilot.personal.models import Discussion, Speaker, SpeakerType


# ── Shared test data ────────────────────────────────────────────────────────

FAMILY_PDP = PDP(
    people=[
        Person(id=-1, name="Maria", last_name="Garcia", gender="female"),
        Person(id=-2, name="Carlos", last_name="Garcia", gender="male"),
        Person(id=-3, name="Sofia", last_name="Garcia", gender="female", parents=-6),
    ],
    events=[
        Event(
            id=-4,
            kind=EventKind.Married,
            person=-1,
            spouse=-2,
            description="Married Carlos",
            dateTime="2015-06-20",
            dateCertainty=DateCertainty.Certain,
        ),
        Event(
            id=-5,
            kind=EventKind.Birth,
            person=-1,
            spouse=-2,
            child=-3,
            description="Sofia born",
            dateTime="2018-03-10",
            dateCertainty=DateCertainty.Certain,
        ),
    ],
    pair_bonds=[
        PairBond(id=-6, person_a=-1, person_b=-2),
    ],
)

FAMILY_DELTAS = PDPDeltas(
    people=FAMILY_PDP.people[:],
    events=FAMILY_PDP.events[:],
    pair_bonds=FAMILY_PDP.pair_bonds[:],
)


SIMPLE_PDP = PDP(
    people=[
        Person(id=-1, name="Alice", gender="female"),
        Person(id=-2, name="Bob", gender="male"),
    ],
    events=[
        Event(
            id=-3,
            kind=EventKind.Shift,
            person=-1,
            description="Started new job",
            dateTime="2024-01-15",
            symptom=VariableShift.Up,
            functioning=VariableShift.Up,
        ),
    ],
    pair_bonds=[
        PairBond(id=-4, person_a=-1, person_b=-2),
    ],
)

SIMPLE_DELTAS = PDPDeltas(
    people=SIMPLE_PDP.people[:],
    events=SIMPLE_PDP.events[:],
    pair_bonds=SIMPLE_PDP.pair_bonds[:],
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _extract_and_commit(discussion, diagram_data, mock_pdp, mock_deltas):
    """Run extract_full (mocked) then commit all PDP items.

    Deep-copies mock_pdp/mock_deltas so module-level constants are not mutated
    by commit_pdp_items (which removes items from PDP in place).
    """
    pdp_copy = copy.deepcopy(mock_pdp)
    deltas_copy = copy.deepcopy(mock_deltas)

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(pdp_copy, deltas_copy)),
    ):
        from btcopilot.pdp import extract_full

        new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
        diagram_data.pdp = new_pdp

    # Commit all PDP items
    pdp_ids = (
        [p.id for p in diagram_data.pdp.people]
        + [e.id for e in diagram_data.pdp.events]
        + [pb.id for pb in diagram_data.pdp.pair_bonds]
    )
    if pdp_ids:
        diagram_data.commit_pdp_items(pdp_ids)

    return diagram_data


def _count_items(diagram_data):
    """Return (people_count, events_count, pair_bonds_count)."""
    return (
        len(diagram_data.people),
        len(diagram_data.events),
        len(diagram_data.pair_bonds),
    )


def _extract_commit_persist(diagram, discussion, mock_pdp, mock_deltas):
    """Extract, commit all PDP items, persist to DB, and reload.

    Deep-copies mock_pdp/mock_deltas so module-level constants are not mutated.
    Returns the reloaded DiagramData.
    """
    pdp_copy = copy.deepcopy(mock_pdp)
    deltas_copy = copy.deepcopy(mock_deltas)

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(pdp_copy, deltas_copy)),
    ):
        from btcopilot.pdp import extract_full

        diagram_data = diagram.get_diagram_data()
        new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
        diagram_data.pdp = new_pdp

    pdp_ids = (
        [p.id for p in diagram_data.pdp.people]
        + [e.id for e in diagram_data.pdp.events]
        + [pb.id for pb in diagram_data.pdp.pair_bonds]
    )
    if pdp_ids:
        diagram_data.commit_pdp_items(pdp_ids)

    diagram.set_diagram_data(diagram_data)
    db.session.commit()
    db.session.refresh(diagram)

    return diagram.get_diagram_data()


# ── Tests: In-memory DiagramData (no DB persistence) ───────────────────────


class TestIdempotentReextractionInMemory:
    """Idempotent re-extraction using pure DiagramData (no DB round-trip)."""

    def test_second_extraction_empty_preserves_counts(self, discussion):
        """When re-extraction returns empty PDP (LLM sees existing data), counts
        remain unchanged after second commit."""
        diagram_data = DiagramData()

        # First extraction + commit
        diagram_data = _extract_and_commit(
            discussion, diagram_data, FAMILY_PDP, FAMILY_DELTAS
        )
        counts_after_first = _count_items(diagram_data)

        assert counts_after_first == (3, 2, 1)

        # Second extraction returns empty (correct LLM behavior)
        empty_pdp = PDP()
        empty_deltas = PDPDeltas()
        diagram_data = _extract_and_commit(
            discussion, diagram_data, empty_pdp, empty_deltas
        )
        counts_after_second = _count_items(diagram_data)

        assert counts_after_second == counts_after_first, (
            f"Counts changed after re-extraction with empty result: "
            f"before={counts_after_first}, after={counts_after_second}"
        )

    def test_simple_family_second_empty_extraction(self, discussion):
        """Simple case: two people, one event, one pair bond. Re-extraction
        returns nothing new."""
        diagram_data = DiagramData()

        diagram_data = _extract_and_commit(
            discussion, diagram_data, SIMPLE_PDP, SIMPLE_DELTAS
        )
        counts_after_first = _count_items(diagram_data)

        assert counts_after_first == (2, 1, 1)

        # Second extraction returns empty
        diagram_data = _extract_and_commit(
            discussion, diagram_data, PDP(), PDPDeltas()
        )
        counts_after_second = _count_items(diagram_data)

        assert counts_after_second == counts_after_first

    def test_duplicate_pair_bond_deduplication(self, discussion):
        """When re-extraction returns the same pair bond (referencing already
        committed people by positive IDs), the pair bond should be deduplicated."""
        diagram_data = DiagramData()

        # First extraction + commit
        diagram_data = _extract_and_commit(
            discussion, diagram_data, SIMPLE_PDP, SIMPLE_DELTAS
        )
        counts_after_first = _count_items(diagram_data)

        # Find committed person IDs
        alice_id = next(
            p["id"] for p in diagram_data.people if p["name"] == "Alice"
        )
        bob_id = next(
            p["id"] for p in diagram_data.people if p["name"] == "Bob"
        )

        # Second extraction returns a duplicate pair bond referencing committed people
        dup_pb_pdp = PDP(
            pair_bonds=[PairBond(id=-10, person_a=alice_id, person_b=bob_id)],
        )
        dup_pb_deltas = PDPDeltas(
            pair_bonds=dup_pb_pdp.pair_bonds[:],
        )

        diagram_data = _extract_and_commit(
            discussion, diagram_data, dup_pb_pdp, dup_pb_deltas
        )
        counts_after_second = _count_items(diagram_data)

        # Pair bond should be deduplicated — count unchanged
        assert counts_after_second[2] == counts_after_first[2], (
            f"Pair bond count changed: before={counts_after_first[2]}, "
            f"after={counts_after_second[2]}"
        )

    def test_no_data_loss_after_empty_reextraction(self, discussion):
        """After re-extraction returns empty, verify all original committed
        data (names, event kinds, pair bond links) is intact."""
        diagram_data = DiagramData()

        diagram_data = _extract_and_commit(
            discussion, diagram_data, FAMILY_PDP, FAMILY_DELTAS
        )

        # Capture original data
        original_names = sorted(p["name"] for p in diagram_data.people)
        original_event_kinds = sorted(e["kind"] for e in diagram_data.events)
        original_pb_count = len(diagram_data.pair_bonds)

        # Empty re-extraction
        diagram_data = _extract_and_commit(
            discussion, diagram_data, PDP(), PDPDeltas()
        )

        # Verify data integrity
        reextracted_names = sorted(p["name"] for p in diagram_data.people)
        reextracted_event_kinds = sorted(e["kind"] for e in diagram_data.events)

        assert reextracted_names == original_names
        assert reextracted_event_kinds == original_event_kinds
        assert len(diagram_data.pair_bonds) == original_pb_count

    def test_pdp_staging_empty_after_both_commits(self, discussion):
        """After both extractions and commits, the PDP staging area must be
        empty (all items committed or no new items)."""
        diagram_data = DiagramData()

        # First cycle
        diagram_data = _extract_and_commit(
            discussion, diagram_data, FAMILY_PDP, FAMILY_DELTAS
        )
        assert len(diagram_data.pdp.people) == 0
        assert len(diagram_data.pdp.events) == 0
        assert len(diagram_data.pdp.pair_bonds) == 0

        # Second cycle (empty)
        diagram_data = _extract_and_commit(
            discussion, diagram_data, PDP(), PDPDeltas()
        )
        assert len(diagram_data.pdp.people) == 0
        assert len(diagram_data.pdp.events) == 0
        assert len(diagram_data.pdp.pair_bonds) == 0

    def test_last_item_id_stable_after_empty_reextraction(self, discussion):
        """lastItemId should not increment when re-extraction yields nothing."""
        diagram_data = DiagramData()

        diagram_data = _extract_and_commit(
            discussion, diagram_data, SIMPLE_PDP, SIMPLE_DELTAS
        )
        last_id_after_first = diagram_data.lastItemId

        diagram_data = _extract_and_commit(
            discussion, diagram_data, PDP(), PDPDeltas()
        )
        last_id_after_second = diagram_data.lastItemId

        assert last_id_after_second == last_id_after_first, (
            f"lastItemId changed: {last_id_after_first} -> {last_id_after_second}"
        )


# ── Tests: With DB persistence (diagram round-trip) ────────────────────────


@pytest.fixture
def diagram_with_discussion(test_user):
    """Discussion attached to user's free diagram, ready for extraction."""
    diagram = test_user.free_diagram
    diagram_data = diagram.get_diagram_data()
    diagram_data.ensure_chat_defaults()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=diagram.id,
        summary="Idempotent Reextraction Test",
    )
    db.session.add(discussion)
    db.session.flush()

    user_speaker = Speaker(
        discussion_id=discussion.id,
        name="Client",
        type=SpeakerType.Subject,
        person_id=1,
    )
    ai_speaker = Speaker(
        discussion_id=discussion.id,
        name="Coach",
        type=SpeakerType.Expert,
    )
    db.session.add_all([user_speaker, ai_speaker])
    db.session.flush()

    discussion.chat_user_speaker_id = user_speaker.id
    discussion.chat_ai_speaker_id = ai_speaker.id
    db.session.commit()

    return diagram, discussion


class TestIdempotentReextractionWithDB:
    """Idempotent re-extraction with DB persistence via get/set_diagram_data."""

    def test_full_cycle_persisted(self, diagram_with_discussion):
        """Extract → commit → persist → reload → extract again → commit →
        persist → reload → assert counts match."""
        diagram, discussion = diagram_with_discussion

        # First extraction
        diagram_data = _extract_commit_persist(
            diagram, discussion, FAMILY_PDP, FAMILY_DELTAS
        )
        counts_after_first = _count_items(diagram_data)

        # ensure_chat_defaults adds 2 people (User, Assistant) + 3 from FAMILY_PDP = 5
        assert counts_after_first == (5, 2, 1)

        # Second extraction (empty result)
        diagram_data = _extract_commit_persist(
            diagram, discussion, PDP(), PDPDeltas()
        )
        counts_after_second = _count_items(diagram_data)

        assert counts_after_second == counts_after_first, (
            f"Counts changed after persisted re-extraction: "
            f"before={counts_after_first}, after={counts_after_second}"
        )

    def test_data_survives_db_round_trip(self, diagram_with_discussion):
        """Committed data survives pickle serialization round-trip without
        corruption."""
        diagram, discussion = diagram_with_discussion

        reloaded = _extract_commit_persist(
            diagram, discussion, FAMILY_PDP, FAMILY_DELTAS
        )

        # All committed data intact (2 defaults + 3 FAMILY = 5 people)
        assert len(reloaded.people) == 5
        assert len(reloaded.events) == 2
        assert len(reloaded.pair_bonds) == 1

        # FAMILY names survive pickle round-trip
        reloaded_names = sorted(p["name"] for p in reloaded.people)
        for name in ["Carlos", "Maria", "Sofia"]:
            assert name in reloaded_names

        # PDP staging is empty
        assert len(reloaded.pdp.people) == 0
        assert len(reloaded.pdp.events) == 0
        assert len(reloaded.pdp.pair_bonds) == 0

    def test_three_extractions_stable(self, diagram_with_discussion):
        """Three consecutive extract → commit cycles produce stable counts."""
        diagram, discussion = diagram_with_discussion

        # First extraction with data
        simple_pdp = copy.deepcopy(SIMPLE_PDP)
        simple_deltas = copy.deepcopy(SIMPLE_DELTAS)

        with patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(simple_pdp, simple_deltas)),
        ):
            from btcopilot.pdp import extract_full

            diagram_data = diagram.get_diagram_data()
            new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
            diagram_data.pdp = new_pdp

        pdp_ids = (
            [p.id for p in diagram_data.pdp.people]
            + [e.id for e in diagram_data.pdp.events]
            + [pb.id for pb in diagram_data.pdp.pair_bonds]
        )
        diagram_data.commit_pdp_items(pdp_ids)
        diagram.set_diagram_data(diagram_data)
        db.session.commit()

        db.session.refresh(diagram)
        counts_baseline = _count_items(diagram.get_diagram_data())

        # Second and third extractions (empty)
        for cycle in range(2):
            with patch(
                "btcopilot.pdp._extract_and_validate",
                AsyncMock(return_value=(PDP(), PDPDeltas())),
            ):
                diagram_data = diagram.get_diagram_data()
                new_pdp, _ = asyncio.run(
                    extract_full(discussion, diagram_data)
                )
                diagram_data.pdp = new_pdp

            pdp_ids = (
                [p.id for p in diagram_data.pdp.people]
                + [e.id for e in diagram_data.pdp.events]
                + [pb.id for pb in diagram_data.pdp.pair_bonds]
            )
            if pdp_ids:
                diagram_data.commit_pdp_items(pdp_ids)

            diagram.set_diagram_data(diagram_data)
            db.session.commit()
            db.session.refresh(diagram)

        final_counts = _count_items(diagram.get_diagram_data())
        assert final_counts == counts_baseline, (
            f"Counts drifted after 3 cycles: "
            f"baseline={counts_baseline}, final={final_counts}"
        )


# ── Tests: Relationship-rich scenario ───────────────────────────────────────


class TestIdempotentReextractionRelationships:
    """Verify idempotency with relationship events (Shift with targets/triangles)."""

    def test_relationship_events_stable(self, discussion):
        """Shift events with relationship targets survive re-extraction."""
        relationship_pdp = PDP(
            people=[
                Person(id=-1, name="Alice", gender="female"),
                Person(id=-2, name="Bob", gender="male"),
                Person(id=-3, name="Carol", gender="female"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Increased conflict with Bob",
                    dateTime="2024-03-01",
                    relationship=RelationshipKind.Conflict,
                    relationshipTargets=[-2],
                    symptom=VariableShift.Up,
                    anxiety=VariableShift.Up,
                ),
                Event(
                    id=-5,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Triangled Carol into conflict",
                    dateTime="2024-03-15",
                    relationship=RelationshipKind.Inside,
                    relationshipTargets=[-2],
                    relationshipTriangles=[-3],
                    symptom=VariableShift.Down,
                ),
            ],
            pair_bonds=[
                PairBond(id=-6, person_a=-1, person_b=-2),
            ],
        )
        relationship_deltas = PDPDeltas(
            people=relationship_pdp.people[:],
            events=relationship_pdp.events[:],
            pair_bonds=relationship_pdp.pair_bonds[:],
        )

        diagram_data = DiagramData()
        diagram_data = _extract_and_commit(
            discussion, diagram_data, relationship_pdp, relationship_deltas
        )
        counts_after_first = _count_items(diagram_data)

        # Verify relationship data committed correctly
        conflict_event = next(
            e for e in diagram_data.events
            if e.get("description") == "Increased conflict with Bob"
        )
        assert conflict_event["relationship"] == "conflict"
        assert len(conflict_event["relationshipTargets"]) == 1

        triangle_event = next(
            e for e in diagram_data.events
            if e.get("description") == "Triangled Carol into conflict"
        )
        assert len(triangle_event["relationshipTriangles"]) == 1

        # Empty re-extraction
        diagram_data = _extract_and_commit(
            discussion, diagram_data, PDP(), PDPDeltas()
        )
        counts_after_second = _count_items(diagram_data)

        assert counts_after_second == counts_after_first

        # Verify relationship data still intact
        conflict_event_after = next(
            e for e in diagram_data.events
            if e.get("description") == "Increased conflict with Bob"
        )
        assert conflict_event_after["relationshipTargets"] == conflict_event["relationshipTargets"]

        triangle_event_after = next(
            e for e in diagram_data.events
            if e.get("description") == "Triangled Carol into conflict"
        )
        assert triangle_event_after["relationshipTriangles"] == triangle_event["relationshipTriangles"]


# ── Tests: LLM dedup failure (T7-9 regression) ──────────────────────────────
#
# These tests simulate the real-world failure mode where the LLM ignores
# the "avoid duplicates with committed items" instruction in
# DATA_FULL_EXTRACTION_CONTEXT and re-extracts the same people/events/pair
# bonds with fresh negative IDs.
#
# The pipeline currently has PairBond dedup in commit_pdp_items() (matches
# dyads) but NO rules-based dedup for People or Events. These tests
# characterize the bug: without a post-extraction filter, duplicate people
# and events will be committed.
#
# Related tasks: T7-9 (validate idempotent re-extraction),
#                T7-11 (fix extraction dedup against committed items)
# ─────────────────────────────────────────────────────────────────────────────


def _simulate_reextraction_with_duplicates(discussion, diagram_data):
    """Extract → commit → re-extract with LLM returning duplicate items.

    The second extraction simulates an LLM that returns the SAME people/
    events/pairbonds as the first extraction, but with fresh negative IDs
    (as if it never saw the committed data).

    Returns:
        (counts_after_first, counts_after_second, diagram_data)
    """
    # ── First extraction + commit ──────────────────────────────────────
    diagram_data = _extract_and_commit(
        discussion, diagram_data, SIMPLE_PDP, SIMPLE_DELTAS
    )
    counts_after_first = _count_items(diagram_data)

    # ── Build duplicate PDP with fresh negative IDs ────────────────────
    # Same names/descriptions, different IDs — simulates LLM ignoring
    # the committed items and re-extracting everything.
    dup_pdp = PDP(
        people=[
            Person(id=-101, name="Alice", gender="female"),
            Person(id=-102, name="Bob", gender="male"),
        ],
        events=[
            Event(
                id=-103,
                kind=EventKind.Shift,
                person=-101,
                description="Started new job",
                dateTime="2024-01-15",
                symptom=VariableShift.Up,
                functioning=VariableShift.Up,
            ),
        ],
        pair_bonds=[
            PairBond(id=-104, person_a=-101, person_b=-102),
        ],
    )
    dup_deltas = PDPDeltas(
        people=dup_pdp.people[:],
        events=dup_pdp.events[:],
        pair_bonds=dup_pdp.pair_bonds[:],
    )

    # ── Second extraction with duplicates ──────────────────────────────
    # Simulate endpoint clearing PDP before re-extraction (as the
    # extract endpoint does: diagram_data.pdp = PDP())
    diagram_data.pdp = PDP()
    diagram_data = _extract_and_commit(
        discussion, diagram_data, dup_pdp, dup_deltas
    )
    counts_after_second = _count_items(diagram_data)

    return counts_after_first, counts_after_second, diagram_data


class TestIdempotentLLMDedupFailure:
    """T7-9 regression: verify pipeline behavior when LLM returns duplicates.

    These tests characterize the known bug where extract_full() re-extracts
    people and events that are already committed in diagram_data. The LLM
    prompt says "avoid duplicates with committed items" but this instruction
    is unreliable.

    EXPECTED BEHAVIOR (once T7-11 is fixed):
        Second extraction should produce zero new people/events/pairbonds
        after dedup against committed items.

    CURRENT BEHAVIOR (bug):
        People and events are duplicated because there is no rules-based
        post-extraction dedup — only PairBonds have dyad-based dedup in
        commit_pdp_items(). People and events pass through unfiltered.
    """

    def test_idempotent_reextraction_no_duplicate_people(self, discussion):
        """REGRESSION T7-9: Re-extraction returning same people (same names,
        new negative IDs) should NOT create duplicate committed people.

        BUG CHARACTERIZATION: This test is expected to FAIL until T7-11 adds
        rules-based dedup for People in the extraction pipeline. Currently,
        extract_full() + commit_pdp_items() will create duplicate people
        because the only dedup mechanism is the LLM prompt instruction, which
        is unreliable.

        Fix options (from T7-11):
        - Post-extraction filter in _extract_and_validate() or apply_deltas()
          that strips people matching committed names
        - Rules-based dedup in commit_pdp_items() matching by name + gender
        """
        diagram_data = DiagramData()
        counts_first, counts_second, _ = _simulate_reextraction_with_duplicates(
            discussion, diagram_data
        )

        # After first extraction: 2 people, 1 event, 1 pair bond
        assert counts_first == (2, 1, 1), (
            f"First extraction unexpected counts: {counts_first}"
        )

        # After second extraction with duplicate items: counts should be unchanged
        assert counts_second[0] == counts_first[0], (
            f"DUPLICATE PEOPLE BUG (T7-9/T7-11): People count changed from "
            f"{counts_first[0]} to {counts_second[0]} after re-extraction "
            f"with same names. Pipeline lacks rules-based person dedup — "
            f"only relies on LLM prompt instruction which is unreliable."
        )

    def test_idempotent_reextraction_no_duplicate_events(self, discussion):
        """REGRESSION T7-9: Re-extraction returning same events (same
        description/kind/date, new negative IDs) should NOT create duplicate
        committed events.

        BUG CHARACTERIZATION: Like people, events have no rules-based dedup.
        The LLM re-extracts "Started new job" with a fresh ID and it gets
        committed as a second copy.

        Fix: Post-extraction filter matching events by (kind, person_name,
        description, dateTime) against committed events.
        """
        diagram_data = DiagramData()
        counts_first, counts_second, _ = _simulate_reextraction_with_duplicates(
            discussion, diagram_data
        )

        assert counts_second[1] == counts_first[1], (
            f"DUPLICATE EVENTS BUG (T7-9/T7-11): Event count changed from "
            f"{counts_first[1]} to {counts_second[1]} after re-extraction "
            f"with same descriptions. Pipeline lacks rules-based event dedup."
        )

    def test_idempotent_reextraction_pairbond_dedup_works(self, discussion):
        """REGRESSION T7-9: PairBond dedup DOES work — commit_pdp_items()
        has dyad-based dedup that catches duplicate pair bonds referencing
        the same two people.

        This test verifies the existing PairBond dedup continues to work
        as a baseline for the people/event dedup that needs to be added.
        """
        diagram_data = DiagramData()
        counts_first, counts_second, _ = _simulate_reextraction_with_duplicates(
            discussion, diagram_data
        )

        # PairBond dedup should work because commit_pdp_items() checks dyads
        assert counts_second[2] == counts_first[2], (
            f"PairBond dedup regression: count changed from "
            f"{counts_first[2]} to {counts_second[2]} after re-extraction "
            f"with same dyad. This dedup used to work via "
            f"commit_pdp_items() dyad matching."
        )

    def test_idempotent_reextraction_total_counts_stable(self, discussion):
        """REGRESSION T7-9: Full end-to-end check — extract, accept all,
        extract same items again, accept all again. Total committed item
        counts must remain unchanged.

        This is the top-level assertion from the T7-9 task description:
        'extract → accept all → extract again → verify no duplicate
        people/events vs committed items.'
        """
        diagram_data = DiagramData()
        counts_first, counts_second, _ = _simulate_reextraction_with_duplicates(
            discussion, diagram_data
        )

        assert counts_second == counts_first, (
            f"IDEMPOTENCY VIOLATION (T7-9): Counts changed after "
            f"re-extraction with duplicate items. "
            f"Before: people={counts_first[0]}, events={counts_first[1]}, "
            f"pairbonds={counts_first[2]}. "
            f"After: people={counts_second[0]}, events={counts_second[1]}, "
            f"pairbonds={counts_second[2]}. "
            f"See T7-11 for fix strategy."
        )

    def test_idempotent_reextraction_family_scenario(self, discussion):
        """REGRESSION T7-9: Family scenario — Maria/Carlos married, Sofia
        born. Re-extraction returns same family with new IDs.

        Tests a more complex case with structural events (Married, Birth)
        that trigger commit invariants (inferred PairBonds, birth items).
        """
        diagram_data = DiagramData()

        # First extraction with family data
        diagram_data = _extract_and_commit(
            discussion, diagram_data, FAMILY_PDP, FAMILY_DELTAS
        )
        counts_after_first = _count_items(diagram_data)

        # Build duplicate family with fresh IDs
        dup_family_pdp = PDP(
            people=[
                Person(id=-201, name="Maria", last_name="Garcia", gender="female"),
                Person(id=-202, name="Carlos", last_name="Garcia", gender="male"),
                Person(
                    id=-203,
                    name="Sofia",
                    last_name="Garcia",
                    gender="female",
                    parents=-206,
                ),
            ],
            events=[
                Event(
                    id=-204,
                    kind=EventKind.Married,
                    person=-201,
                    spouse=-202,
                    description="Married Carlos",
                    dateTime="2015-06-20",
                    dateCertainty=DateCertainty.Certain,
                ),
                Event(
                    id=-205,
                    kind=EventKind.Birth,
                    person=-201,
                    spouse=-202,
                    child=-203,
                    description="Sofia born",
                    dateTime="2018-03-10",
                    dateCertainty=DateCertainty.Certain,
                ),
            ],
            pair_bonds=[
                PairBond(id=-206, person_a=-201, person_b=-202),
            ],
        )
        dup_family_deltas = PDPDeltas(
            people=dup_family_pdp.people[:],
            events=dup_family_pdp.events[:],
            pair_bonds=dup_family_pdp.pair_bonds[:],
        )

        # Clear PDP (as extract endpoint does) and re-extract
        diagram_data.pdp = PDP()
        diagram_data = _extract_and_commit(
            discussion, diagram_data, dup_family_pdp, dup_family_deltas
        )
        counts_after_second = _count_items(diagram_data)

        # Count unique person names to verify duplication
        person_names = [p["name"] for p in diagram_data.people]
        unique_names = set(person_names)

        assert counts_after_second == counts_after_first, (
            f"IDEMPOTENCY VIOLATION (T7-9) family scenario: "
            f"Before: {counts_after_first}, After: {counts_after_second}. "
            f"Person names: {person_names} "
            f"(unique: {unique_names}, duplicates: "
            f"{[n for n in person_names if person_names.count(n) > 1]})"
        )

    def test_pdp_items_after_reextraction_with_duplicates(self, discussion):
        """REGRESSION T7-9: After re-extraction with duplicates, verify
        PDP staging state. If dedup works, PDP should be empty (all items
        filtered as duplicates). If dedup is broken, PDP will contain
        the duplicate items before commit."""
        diagram_data = DiagramData()

        # First extraction + commit
        diagram_data = _extract_and_commit(
            discussion, diagram_data, SIMPLE_PDP, SIMPLE_DELTAS
        )

        # Build duplicate PDP
        dup_pdp = PDP(
            people=[
                Person(id=-101, name="Alice", gender="female"),
                Person(id=-102, name="Bob", gender="male"),
            ],
            events=[
                Event(
                    id=-103,
                    kind=EventKind.Shift,
                    person=-101,
                    description="Started new job",
                    dateTime="2024-01-15",
                    symptom=VariableShift.Up,
                    functioning=VariableShift.Up,
                ),
            ],
            pair_bonds=[
                PairBond(id=-104, person_a=-101, person_b=-102),
            ],
        )
        dup_deltas = PDPDeltas(
            people=dup_pdp.people[:],
            events=dup_pdp.events[:],
            pair_bonds=dup_pdp.pair_bonds[:],
        )

        # Re-extract (simulating endpoint PDP clear)
        diagram_data.pdp = PDP()
        pdp_copy = copy.deepcopy(dup_pdp)
        deltas_copy = copy.deepcopy(dup_deltas)
        with patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(pdp_copy, deltas_copy)),
        ):
            from btcopilot.pdp import extract_full

            new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
            diagram_data.pdp = new_pdp

        # Check PDP state BEFORE commit — this is where dedup should
        # have filtered out duplicates
        pdp_people_names = [p.name for p in diagram_data.pdp.people]
        pdp_event_descs = [e.description for e in diagram_data.pdp.events]

        # If dedup worked, PDP should have zero items (all filtered)
        # If dedup is broken, PDP will have the duplicate items
        assert len(diagram_data.pdp.people) == 0, (
            f"DEDUP GAP (T7-9): PDP contains {len(diagram_data.pdp.people)} "
            f"people after re-extraction: {pdp_people_names}. "
            f"These are duplicates of committed items and should have been "
            f"filtered by a post-extraction dedup step. "
            f"Currently no such filter exists — see T7-11."
        )
        assert len(diagram_data.pdp.events) == 0, (
            f"DEDUP GAP (T7-9): PDP contains {len(diagram_data.pdp.events)} "
            f"events after re-extraction: {pdp_event_descs}. "
            f"These are duplicates of committed events and should have been "
            f"filtered. See T7-11."
        )
