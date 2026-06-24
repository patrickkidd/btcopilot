import asyncio
from datetime import date

import pytest
from mock import patch, AsyncMock, call

from btcopilot.schema import (
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    DiagramData,
    RelationshipKind,
)


def test_extract_full_returns_merged_pdp(discussion):
    pass1_pdp = PDP(
        people=[Person(id=-1, name="Mom", gender="female", confidence=0.8)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Birth,
                person=-1,
                child=-1,
                description="Born",
                dateTime="1953-01-01",
                confidence=0.8,
            )
        ],
        pair_bonds=[],
    )
    pass1_deltas = PDPDeltas(
        people=pass1_pdp.people,
        events=pass1_pdp.events,
    )

    pass2_pdp = PDP(
        people=pass1_pdp.people,
        events=pass1_pdp.events
        + [
            Event(
                id=-3,
                kind=EventKind.Shift,
                person=-1,
                description="Anxiety increased",
                dateTime="2020-01-01",
                confidence=0.8,
            )
        ],
        pair_bonds=[],
    )
    pass2_deltas = PDPDeltas(
        events=[pass2_pdp.events[1]],
    )

    review_deltas = PDPDeltas(events=[])

    with (
        patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(
                side_effect=[(pass1_pdp, pass1_deltas), (pass2_pdp, pass2_deltas)]
            ),
        ) as mock_extract,
        patch(
            "btcopilot.pdp.gemini_structured",
            AsyncMock(return_value=review_deltas),
        ),
    ):
        from btcopilot.pdp import extract_full

        diagram_data = DiagramData()
        result_pdp, result_deltas = asyncio.run(extract_full(discussion, diagram_data))

        assert len(result_pdp.people) == 1
        assert result_pdp.people[0].name == "Mom"
        assert len(result_pdp.events) == 2

        assert mock_extract.call_count == 2
        assert "extract_full_pass1" in mock_extract.call_args_list[0][0]
        assert "extract_full_pass2" in mock_extract.call_args_list[1][0]
        assert mock_extract.call_args_list[1][1]["base_pdp"] is pass1_pdp

        # Merged deltas contain both passes
        assert len(result_deltas.people) == 1
        assert len(result_deltas.events) == 2


def test_extract_full_calls_both_passes(discussion):
    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full

        diagram_data = DiagramData()
        asyncio.run(extract_full(discussion, diagram_data))

        assert mock_extract.call_count == 2
        assert "extract_full_pass1" in mock_extract.call_args_list[0][0]
        assert "extract_full_pass2" in mock_extract.call_args_list[1][0]


def test_extract_full_uses_discussion_date(discussion):
    from datetime import date
    from btcopilot.extensions import db

    discussion.discussion_date = date(2025, 6, 15)
    db.session.commit()

    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    # Use a prompt template that includes {current_date} to verify it flows through
    with (
        patch(
            "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
            "date={current_date}",
        ),
        patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(mock_pdp, mock_deltas)),
        ) as mock_extract,
    ):
        from btcopilot.pdp import extract_full

        diagram_data = DiagramData()
        asyncio.run(extract_full(discussion, diagram_data))

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        assert "2025-06-15" in pass1_prompt


def test_import_text_calls_two_pass():
    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import import_text

        diagram_data = DiagramData()
        asyncio.run(import_text(diagram_data, "My mom Barbara is 72."))

        assert mock_extract.call_count == 2
        assert "import_text_pass1" in mock_extract.call_args_list[0][0]
        assert "import_text_pass2" in mock_extract.call_args_list[1][0]


def test_import_text_uses_reference_date():
    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with (
        patch(
            "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
            "date={current_date}",
        ),
        patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(mock_pdp, mock_deltas)),
        ) as mock_extract,
    ):
        from btcopilot.pdp import import_text

        diagram_data = DiagramData()
        asyncio.run(
            import_text(diagram_data, "test text", reference_date=date(2025, 3, 1))
        )

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        assert "2025-03-01" in pass1_prompt


def test_import_text_passes_text_as_conversation_history():
    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with (
        patch(
            "btcopilot.pdp.DATA_EXTRACTION_PASS1_CONTEXT",
            "{conversation_history}",
        ),
        patch(
            "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
            "{current_date}",
        ),
        patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(return_value=(mock_pdp, mock_deltas)),
        ) as mock_extract,
    ):
        from btcopilot.pdp import import_text

        diagram_data = DiagramData()
        text = "My family has three generations of doctors."
        asyncio.run(import_text(diagram_data, text))

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        assert text in pass1_prompt


def test_gemini_structured_accepts_model_override():
    # FD-337 regression: Pass-3 SARF review passes model=; the callee must accept it.
    import inspect
    from btcopilot.llmutil import gemini_structured

    assert "model" in inspect.signature(gemini_structured).parameters


def _sarf_review_passes():
    pass1_pdp = PDP(people=[Person(id=-1, name="Mom", confidence=0.8)])
    pass1_deltas = PDPDeltas(people=pass1_pdp.people)
    shift = Event(
        id=-2,
        kind=EventKind.Shift,
        person=-1,
        relationship=RelationshipKind.Conflict,
        relationshipTargets=[-1],
        description="Argued",
        dateTime="2020-01-01",
        confidence=0.8,
    )
    pass2_pdp = PDP(people=pass1_pdp.people, events=[shift])
    pass2_deltas = PDPDeltas(events=[shift])
    return pass1_pdp, pass1_deltas, pass2_pdp, pass2_deltas


def _run_sarf_review(discussion, review):
    pass1_pdp, pass1_deltas, pass2_pdp, pass2_deltas = _sarf_review_passes()
    with (
        patch(
            "btcopilot.pdp._extract_and_validate",
            AsyncMock(
                side_effect=[(pass1_pdp, pass1_deltas), (pass2_pdp, pass2_deltas)]
            ),
        ),
        patch(
            "btcopilot.pdp.gemini_structured",
            AsyncMock(return_value=review),
        ),
    ):
        from btcopilot.pdp import extract_full

        result_pdp, _ = asyncio.run(extract_full(discussion, DiagramData()))
    return next(e for e in result_pdp.events if e.id == -2), result_pdp


def test_sarf_review_rejects_out_of_roster_targets(discussion):
    review = PDPDeltas(
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                relationship=RelationshipKind.Distance,
                relationshipTargets=[-99],
                description="Argued",
                dateTime="2020-01-01",
            )
        ]
    )
    event, result_pdp = _run_sarf_review(discussion, review)

    assert event.relationship == RelationshipKind.Conflict
    assert event.relationshipTargets == [-1]

    diagram_data = DiagramData()
    diagram_data.pdp = result_pdp
    diagram_data.commit_pdp_items([-1, -2])


def test_sarf_review_splices_in_roster_targets(discussion):
    review = PDPDeltas(
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                relationship=RelationshipKind.Distance,
                relationshipTargets=[-1],
                description="Argued",
                dateTime="2020-01-01",
            )
        ]
    )
    event, _ = _run_sarf_review(discussion, review)

    assert event.relationship == RelationshipKind.Distance
    assert event.relationshipTargets == [-1]


def test_extract_full_windows_long_discussion_and_preserves_committed(discussion):
    # FD-337: with WINDOW_SIZE forced below the statement count, extract_full runs one
    # extraction per window on a clone and re-stages the union as negative-id deltas,
    # without committing into the caller's diagram.
    from btcopilot.pdp import extract_full

    w1 = PDP(people=[Person(id=-1, name="Mom", gender="female", confidence=0.8)])
    w2 = PDP(people=[Person(id=-1, name="Dad", gender="male", confidence=0.8)])

    with (
        patch("btcopilot.pdp.WINDOW_SIZE", 1),
        patch(
            "btcopilot.pdp._two_pass_extract",
            AsyncMock(side_effect=[(w1, PDPDeltas()), (w2, PDPDeltas())]),
        ) as mock_two_pass,
    ):
        diagram_data = DiagramData()
        staged, _ = asyncio.run(extract_full(discussion, diagram_data))

    assert mock_two_pass.call_count == 2
    assert {p.name for p in staged.people} == {"Mom", "Dad"}
    assert all(p.id < 0 for p in staged.people)
    assert diagram_data.people == []


def test_extract_full_stages_positive_id_parent_edits(discussion):
    # FD-338 bug B: a positive-id Person(parents=...) edit emitted on a committed
    # person mid-window must survive to the staged delta instead of being wiped
    # with working.pdp between windows.
    from btcopilot.pdp import extract_full

    original = DiagramData(
        pdp=PDP(
            people=[
                Person(id=-1, name="Kid"),
                Person(id=-2, name="Mom"),
                Person(id=-3, name="Dad"),
            ],
            pair_bonds=[PairBond(id=-4, person_a=-2, person_b=-3)],
        )
    )
    mapping = original.commit_pdp_items([-1, -2, -3, -4])
    kid_id, bond_id = mapping[-1], mapping[-4]

    w1 = PDP(people=[Person(id=-1, name="Aunt", confidence=0.8)])
    w2 = PDP(people=[Person(id=kid_id, parents=bond_id)])

    with (
        patch("btcopilot.pdp.WINDOW_SIZE", 1),
        patch(
            "btcopilot.pdp._two_pass_extract",
            AsyncMock(side_effect=[(w1, PDPDeltas()), (w2, PDPDeltas())]),
        ),
    ):
        staged, _ = asyncio.run(extract_full(discussion, original))

    edits = [p for p in staged.people if p.id == kid_id]
    assert len(edits) == 1
    assert edits[0].parents == bond_id
    assert {p.name for p in staged.people if p.id is not None and p.id < 0} == {"Aunt"}
    kid = next(p for p in original.people if p["id"] == kid_id)
    assert kid["parents"] is None


def test_restage_new_items_keeps_committed_refs_positive():
    # FD-337: re-staged new items get fresh negative ids; references into the original
    # committed diagram stay positive, references among new items become negative.
    import copy
    from btcopilot.pdp import _restage_new_items

    original = DiagramData(pdp=PDP(people=[Person(id=-1, name="User")]))
    original.commit_pdp_items([-1])
    user_id = original.people[0]["id"]

    working = DiagramData(
        people=copy.deepcopy(original.people),
        lastItemId=original.lastItemId,
    )
    working.pdp = PDP(
        people=[Person(id=-1, name="Spouse"), Person(id=-3, name="Kid", parents=-2)],
        pair_bonds=[PairBond(id=-2, person_a=user_id, person_b=-1)],
    )
    working.commit_pdp_items([-1, -2, -3])

    staged = _restage_new_items(working, original)

    assert {p.name for p in staged.people} == {"Spouse", "Kid"}
    assert all(p.id < 0 for p in staged.people)
    assert len(staged.pair_bonds) == 1
    bond = staged.pair_bonds[0]
    assert bond.id < 0
    assert user_id in (bond.person_a, bond.person_b)
    assert any(x < 0 for x in (bond.person_a, bond.person_b))
    kid = next(p for p in staged.people if p.name == "Kid")
    assert kid.parents == bond.id
