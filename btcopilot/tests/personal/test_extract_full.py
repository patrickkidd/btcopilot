import asyncio
from datetime import date

import pytest
from mock import patch, AsyncMock, call

from btcopilot.schema import PDP, PDPDeltas, Person, Event, EventKind, PairBond, DiagramData


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
        events=pass1_pdp.events + [
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

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(side_effect=[(pass1_pdp, pass1_deltas), (pass2_pdp, pass2_deltas)]),
    ) as mock_extract:
        from btcopilot.pdp import extract_full

        diagram_data = DiagramData()
        result_pdp, result_deltas = asyncio.run(
            extract_full(discussion, diagram_data)
        )

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
    with patch(
        "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
        "date={current_date}",
    ), patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
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

    with patch(
        "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
        "date={current_date}",
    ), patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
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

    with patch(
        "btcopilot.pdp.DATA_EXTRACTION_PASS1_CONTEXT",
        "{conversation_history}",
    ), patch(
        "btcopilot.pdp.DATA_EXTRACTION_PASS1_PROMPT",
        "{current_date}",
    ), patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import import_text

        diagram_data = DiagramData()
        text = "My family has three generations of doctors."
        asyncio.run(import_text(diagram_data, text))

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        assert text in pass1_prompt
