import pytest
from mock import patch, AsyncMock

from btcopilot.schema import PDP, PDPDeltas, Person, Event, EventKind, PairBond, DiagramData


def test_extract_full_returns_pdp(discussion):
    mock_pdp = PDP(
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
    mock_deltas = PDPDeltas(
        people=mock_pdp.people,
        events=mock_pdp.events,
    )

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full
        from btcopilot.async_utils import one_result

        diagram_data = DiagramData()
        result_pdp, result_deltas = one_result(
            extract_full(discussion, diagram_data)
        )

        assert len(result_pdp.people) == 1
        assert result_pdp.people[0].name == "Mom"
        assert len(result_pdp.events) == 1

        mock_extract.assert_called_once()
        call_kwargs = mock_extract.call_args
        assert call_kwargs[1]["large"] is True
        assert "extract_full" in call_kwargs[0]


def test_extract_full_prompt_contains_full_history(discussion):
    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full
        from btcopilot.async_utils import one_result

        diagram_data = DiagramData()
        one_result(extract_full(discussion, diagram_data))

        prompt = mock_extract.call_args[0][0]
        assert "FULL DISCUSSION EXTRACTION MODE" in prompt
        assert "Hello" in prompt
        assert "Hi there" in prompt


def test_extract_full_uses_discussion_date(discussion):
    from datetime import date
    from btcopilot.extensions import db

    discussion.discussion_date = date(2025, 6, 15)
    db.session.commit()

    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full
        from btcopilot.async_utils import one_result

        diagram_data = DiagramData()
        one_result(extract_full(discussion, diagram_data))

        prompt = mock_extract.call_args[0][0]
        assert "2025-06-15" in prompt
