"""Tests for the Pattern Intelligence (insights) feature."""

import pytest
from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal.insights import generate_insights, _parse_insights
from btcopilot.schema import (
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    asdict,
)


# --- Unit tests for _parse_insights ---


def test_parse_numbered_list():
    text = "1. Mom and Dad show a pattern of conflict.\n2. Anxiety rises across generations.\n3. Cutoff repeats in siblings."
    result = _parse_insights(text)
    assert len(result) == 3
    assert "Mom and Dad" in result[0]
    assert "Anxiety" in result[1]
    assert "Cutoff" in result[2]


def test_parse_double_newline():
    text = "Mom and Dad show a pattern of conflict.\n\nAnxiety rises across generations.\n\nCutoff repeats in siblings."
    result = _parse_insights(text)
    assert len(result) == 3


def test_parse_single_paragraph():
    text = "This is a single insight about the family."
    result = _parse_insights(text)
    assert len(result) == 1
    assert result[0] == text


def test_parse_numbered_with_preamble():
    text = "Here are the patterns:\n1. First pattern about Mom.\n2. Second pattern about Dad."
    result = _parse_insights(text)
    assert len(result) >= 2
    assert "First pattern" in result[0] or "First pattern" in result[1]


def test_parse_empty_string():
    result = _parse_insights("")
    assert result == [""]


# --- Unit tests for generate_insights ---


@pytest.mark.usefixtures("flask_app")
class TestGenerateInsights:

    def test_empty_pdp_returns_empty(self):
        from btcopilot.async_utils import one_result

        pdp = PDP()
        result = one_result(generate_insights(pdp, "Some conversation"))
        assert result == []

    def test_returns_insights_on_success(self):
        from btcopilot.async_utils import one_result

        pdp = PDP(
            people=[
                Person(id=-1, name="Mom", gender="female"),
                Person(id=-2, name="Dad", gender="male"),
                Person(id=-3, name="Grandma", gender="female"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Increased anxiety",
                    dateTime="2024-01-01",
                ),
                Event(
                    id=-5,
                    kind=EventKind.Shift,
                    person=-3,
                    description="Chronic worry",
                    dateTime="1995-06-01",
                ),
            ],
            pair_bonds=[PairBond(id=-6, person_a=-1, person_b=-2)],
        )
        conversation = "Client: My mom worries a lot, just like my grandma did."

        mock_response = (
            "1. Anxiety transmission from Grandma to Mom: Both Grandma and Mom "
            "show elevated anxiety patterns, suggesting intergenerational transmission.\n"
            "2. Mom and Dad's relationship shows signs of emotional fusion, "
            "which often correlates with increased anxiety in the system."
        )

        with patch(
            "btcopilot.personal.insights.gemini_text_sync",
            return_value=mock_response,
        ):
            result = one_result(generate_insights(pdp, conversation))

        assert len(result) == 2
        assert "Grandma" in result[0]
        assert "Mom" in result[0]

    def test_returns_empty_on_llm_error(self):
        from btcopilot.async_utils import one_result

        pdp = PDP(
            people=[Person(id=-1, name="Mom")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Anxiety",
                    dateTime="2024-01-01",
                )
            ],
        )

        with patch(
            "btcopilot.personal.insights.gemini_text_sync",
            side_effect=Exception("LLM unavailable"),
        ):
            result = one_result(generate_insights(pdp, "conversation"))

        assert result == []

    def test_returns_empty_on_empty_response(self):
        from btcopilot.async_utils import one_result

        pdp = PDP(
            people=[Person(id=-1, name="Mom")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    person=-1,
                    description="Anxiety",
                    dateTime="2024-01-01",
                )
            ],
        )

        with patch(
            "btcopilot.personal.insights.gemini_text_sync",
            return_value="",
        ):
            result = one_result(generate_insights(pdp, "conversation"))

        assert result == []


# --- Integration test for extract endpoint with insights ---


def test_extract_endpoint_returns_insights(subscriber, discussion):
    """Extract endpoint should include insights field in response."""
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
    )
    mock_deltas = PDPDeltas(people=mock_pdp.people, events=mock_pdp.events)
    mock_insights = [
        "Mom's birth event marks the beginning of a pattern.",
        "Cross-generational anxiety is evident.",
    ]

    with patch(
        "btcopilot.pdp.extract_full",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ), patch(
        "btcopilot.personal.routes.discussions.generate_insights",
        AsyncMock(return_value=mock_insights),
    ):
        response = subscriber.post(
            f"/personal/discussions/{discussion.id}/extract",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "insights" in data
    assert len(data["insights"]) == 2
    assert "Mom" in data["insights"][0]


def test_extract_endpoint_insights_failure_doesnt_block(subscriber, discussion):
    """If insight generation fails, extraction should still succeed."""
    mock_pdp = PDP(
        people=[Person(id=-1, name="Mom", confidence=0.8)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                description="Anxiety",
                dateTime="2024-01-01",
                confidence=0.8,
            )
        ],
    )
    mock_deltas = PDPDeltas(people=mock_pdp.people, events=mock_pdp.events)

    with patch(
        "btcopilot.pdp.extract_full",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ), patch(
        "btcopilot.personal.routes.discussions.generate_insights",
        AsyncMock(return_value=[]),  # Failure returns empty list
    ):
        response = subscriber.post(
            f"/personal/discussions/{discussion.id}/extract",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["insights"] == []
    assert data["people_count"] == 1
