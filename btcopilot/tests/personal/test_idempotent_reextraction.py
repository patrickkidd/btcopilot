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
    asdict,
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

        assert counts_after_first[0] >= 3  # At least Maria, Carlos, Sofia
        assert counts_after_first[1] >= 2  # Married + Birth
        assert counts_after_first[2] >= 1  # PairBond

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

        # ── First extraction ────────────────────────────────────────────
        family_pdp = copy.deepcopy(FAMILY_PDP)
        family_deltas = copy.deepcopy(FAMILY_DELTAS)

        with patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(family_pdp, family_deltas)),
        ):
            from btcopilot.pdp import extract_full

            diagram_data = diagram.get_diagram_data()
            new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
            diagram_data.pdp = new_pdp

        # Commit all PDP items
        pdp_ids = (
            [p.id for p in diagram_data.pdp.people]
            + [e.id for e in diagram_data.pdp.events]
            + [pb.id for pb in diagram_data.pdp.pair_bonds]
        )
        diagram_data.commit_pdp_items(pdp_ids)

        # Persist to DB
        diagram.set_diagram_data(diagram_data)
        db.session.commit()

        # Reload from DB and record counts
        db.session.refresh(diagram)
        diagram_data = diagram.get_diagram_data()
        counts_after_first = _count_items(diagram_data)

        # ensure_chat_defaults adds 2 people (User, Assistant) + 3 from PDP
        assert counts_after_first[0] >= 3  # At least Maria, Carlos, Sofia
        assert counts_after_first[1] >= 2  # Married + Birth
        assert counts_after_first[2] >= 1  # PairBond

        # ── Second extraction (empty result) ────────────────────────────
        with patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(PDP(), PDPDeltas())),
        ):
            diagram_data = diagram.get_diagram_data()
            new_pdp, _ = asyncio.run(extract_full(discussion, diagram_data))
            diagram_data.pdp = new_pdp

        # Nothing to commit
        pdp_ids = (
            [p.id for p in diagram_data.pdp.people]
            + [e.id for e in diagram_data.pdp.events]
            + [pb.id for pb in diagram_data.pdp.pair_bonds]
        )
        if pdp_ids:
            diagram_data.commit_pdp_items(pdp_ids)

        # Persist to DB
        diagram.set_diagram_data(diagram_data)
        db.session.commit()

        # Reload and verify
        db.session.refresh(diagram)
        diagram_data = diagram.get_diagram_data()
        counts_after_second = _count_items(diagram_data)

        assert counts_after_second == counts_after_first, (
            f"Counts changed after persisted re-extraction: "
            f"before={counts_after_first}, after={counts_after_second}"
        )

    def test_data_survives_db_round_trip(self, diagram_with_discussion):
        """Committed data survives pickle serialization round-trip without
        corruption."""
        diagram, discussion = diagram_with_discussion

        family_pdp = copy.deepcopy(FAMILY_PDP)
        family_deltas = copy.deepcopy(FAMILY_DELTAS)

        with patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(family_pdp, family_deltas)),
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

        # Save
        diagram.set_diagram_data(diagram_data)
        db.session.commit()

        # Reload
        db.session.refresh(diagram)
        reloaded = diagram.get_diagram_data()

        # All committed data intact
        assert len(reloaded.people) == len(diagram_data.people)
        assert len(reloaded.events) == len(diagram_data.events)
        assert len(reloaded.pair_bonds) == len(diagram_data.pair_bonds)

        # Names survive
        original_names = sorted(p["name"] for p in diagram_data.people)
        reloaded_names = sorted(p["name"] for p in reloaded.people)
        assert reloaded_names == original_names

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
