"""Tests for the family insights generation endpoint."""

import json
import pickle

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.schema import DiagramData, PDP, asdict


MOCK_LLM_RESPONSE = json.dumps(
    [
        {
            "title": "Anxiety mirrors across generations",
            "description": "When Person A experiences rising anxiety, Person B shows increased symptoms shortly after. This suggests a multigenerational transmission process. (These observations are AI-generated pattern summaries, not clinical advice.)",
            "supporting_events": [1, 2],
        },
        {
            "title": "Distance pattern under stress",
            "description": "During stressful life events, the couple tends toward emotional distance rather than conflict. This is a common reciprocal pattern. (These observations are AI-generated pattern summaries, not clinical advice.)",
            "supporting_events": [1, 3],
        },
        {
            "title": "Functioning shifts tied to moves",
            "description": "Relocations correlate with functioning changes across multiple family members, suggesting the family system absorbs geographic transitions collectively. (These observations are AI-generated pattern summaries, not clinical advice.)",
            "supporting_events": [2, 3],
        },
    ]
)


def _make_diagram_data_with_events():
    """Create a DiagramData with people and events (as dicts, matching DiagramData schema)."""
    return DiagramData(
        people=[
            {"id": 1, "name": "Alice", "last_name": "Smith", "gender": "female"},
            {"id": 2, "name": "Bob", "last_name": "Smith", "gender": "male"},
        ],
        pair_bonds=[
            {"id": 1, "person_a": 1, "person_b": 2},
        ],
        events=[
            {
                "id": 1,
                "kind": "shift",
                "person": 1,
                "description": "Increased worry about finances",
                "dateTime": "2025-01-15",
                "anxiety": "up",
                "symptom": "up",
            },
            {
                "id": 2,
                "kind": "shift",
                "person": 2,
                "description": "Withdrew from family activities",
                "dateTime": "2025-02-01",
                "functioning": "down",
            },
            {
                "id": 3,
                "kind": "moved",
                "person": 1,
                "description": "Relocated for work",
                "dateTime": "2025-03-01",
            },
        ],
    )


def _make_empty_diagram_data():
    """Create a DiagramData with no events."""
    return DiagramData()


@patch("btcopilot.llmutil.gemini_text_sync", return_value=MOCK_LLM_RESPONSE)
def test_insights_returns_valid_structure(mock_gemini, subscriber):
    """Endpoint returns 200 with 3 insights for a diagram with events."""
    diagram = subscriber.user.free_diagram
    diagram_data = _make_diagram_data_with_events()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    response = subscriber.post(f"/personal/diagrams/{diagram.id}/insights")
    assert response.status_code == 200

    data = response.get_json()
    assert "insights" in data
    assert len(data["insights"]) == 3

    for insight in data["insights"]:
        assert "title" in insight
        assert "description" in insight
        assert "supporting_events" in insight
        assert isinstance(insight["title"], str)
        assert isinstance(insight["description"], str)
        assert isinstance(insight["supporting_events"], list)
        for event_id in insight["supporting_events"]:
            assert isinstance(event_id, int)


@patch("btcopilot.llmutil.gemini_text_sync", return_value=MOCK_LLM_RESPONSE)
def test_insights_calls_gemini_with_correct_temperature(mock_gemini, subscriber):
    """Verify gemini_text_sync is called with temperature=0.3."""
    diagram = subscriber.user.free_diagram
    diagram_data = _make_diagram_data_with_events()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    subscriber.post(f"/personal/diagrams/{diagram.id}/insights")

    mock_gemini.assert_called_once()
    call_kwargs = mock_gemini.call_args
    assert call_kwargs.kwargs.get("temperature") == 0.3


def test_insights_empty_diagram(subscriber):
    """Empty diagram returns empty insights list without calling LLM."""
    diagram = subscriber.user.free_diagram
    diagram_data = _make_empty_diagram_data()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    with patch("btcopilot.llmutil.gemini_text_sync") as mock_gemini:
        response = subscriber.post(f"/personal/diagrams/{diagram.id}/insights")

    assert response.status_code == 200
    data = response.get_json()
    assert data["insights"] == []
    mock_gemini.assert_not_called()


def test_insights_nonexistent_diagram(subscriber):
    """Returns 404 for nonexistent diagram."""
    response = subscriber.post("/personal/diagrams/99999/insights")
    assert response.status_code == 404


@patch("btcopilot.llmutil.gemini_text_sync", return_value="not valid json")
def test_insights_malformed_llm_response(mock_gemini, subscriber):
    """Returns empty insights list when LLM returns unparseable response."""
    diagram = subscriber.user.free_diagram
    diagram_data = _make_diagram_data_with_events()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    response = subscriber.post(f"/personal/diagrams/{diagram.id}/insights")
    assert response.status_code == 200
    data = response.get_json()
    assert data["insights"] == []
