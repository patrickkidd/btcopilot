import asyncio
import json

from mock import patch, AsyncMock

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
)
from btcopilot.pdp import _committed_state_for_prompt


def test_empty_diagram():
    dd = DiagramData()
    result = _committed_state_for_prompt(dd)
    assert result == {"people": [], "events": [], "pair_bonds": []}


def test_committed_items_returned():
    dd = DiagramData()
    dd.people = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    dd.events = [{"id": 10, "kind": "death", "person": 1}]
    dd.pair_bonds = [{"id": 50, "person_a": 1, "person_b": 2}]

    result = _committed_state_for_prompt(dd)
    assert len(result["people"]) == 2
    assert len(result["events"]) == 1
    assert len(result["pair_bonds"]) == 1
    assert result["people"][0]["name"] == "Alice"


def test_pdp_items_excluded():
    dd = DiagramData()
    dd.people = [{"id": 1, "name": "Alice"}]
    dd.pdp = PDP(
        people=[Person(id=-1, name="Uncommitted")],
        events=[Event(id=-2, kind=EventKind.Shift, person=-1, description="test")],
    )

    result = _committed_state_for_prompt(dd)
    assert len(result["people"]) == 1
    assert result["people"][0]["name"] == "Alice"
    # PDP items should not appear
    assert "events" in result
    assert len(result["events"]) == 0


def test_qdatetime_cleaned():
    """QDateTime objects with toString() are converted to ISO strings."""

    class FakeQDateTime:
        def toString(self, fmt):
            return "2024-06-15"

    dd = DiagramData()
    dd.events = [
        {"id": 10, "kind": "shift", "person": 1, "dateTime": FakeQDateTime()},
    ]
    result = _committed_state_for_prompt(dd)
    assert result["events"][0]["dateTime"] == "2024-06-15"


def test_string_datetime_passthrough():
    dd = DiagramData()
    dd.events = [
        {"id": 10, "kind": "shift", "person": 1, "dateTime": "2024-01-15"},
    ]
    result = _committed_state_for_prompt(dd)
    assert result["events"][0]["dateTime"] == "2024-01-15"


def test_none_datetime_passthrough():
    dd = DiagramData()
    dd.events = [
        {"id": 10, "kind": "shift", "person": 1, "dateTime": None},
    ]
    result = _committed_state_for_prompt(dd)
    assert result["events"][0]["dateTime"] is None


def test_end_datetime_cleaned():
    """endDateTime is also cleaned if it has toString()."""

    class FakeQDateTime:
        def toString(self, fmt):
            return "2025-12-31"

    dd = DiagramData()
    dd.events = [
        {
            "id": 10,
            "kind": "shift",
            "person": 1,
            "dateTime": "2024-01-01",
            "endDateTime": FakeQDateTime(),
        },
    ]
    result = _committed_state_for_prompt(dd)
    assert result["events"][0]["endDateTime"] == "2025-12-31"


def test_original_event_not_mutated():
    """_committed_state_for_prompt should not mutate the original diagram_data."""

    class FakeQDateTime:
        def toString(self, fmt):
            return "2024-06-15"

    qdt = FakeQDateTime()
    dd = DiagramData()
    dd.events = [{"id": 10, "kind": "shift", "person": 1, "dateTime": qdt}]

    _committed_state_for_prompt(dd)
    assert dd.events[0]["dateTime"] is qdt


# --- Prompt integration ---


def test_committed_state_in_pass1_prompt(discussion):
    """Verify committed state JSON flows into the pass1 prompt."""
    dd = DiagramData()
    dd.people = [{"id": 1, "name": "Alice", "gender": "female"}]
    dd.events = [{"id": 10, "kind": "death", "person": 1, "dateTime": "2020-05-01"}]
    dd.pair_bonds = []

    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full

        asyncio.run(extract_full(discussion, dd))

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        # Committed person should appear in prompt
        assert '"Alice"' in pass1_prompt
        # Committed event should appear
        assert '"death"' in pass1_prompt
        assert '"2020-05-01"' in pass1_prompt


def test_committed_state_excludes_ui_fields(discussion):
    """Verify that UI settings and other non-committed fields are NOT in the prompt."""
    dd = DiagramData()
    dd.people = [{"id": 1, "name": "Alice"}]
    # DiagramData may have UI fields like layers, settings, etc.
    # These should NOT appear in the prompt
    dd.layers = [{"id": 1, "name": "Default Layer"}]

    mock_pdp = PDP()
    mock_deltas = PDPDeltas()

    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(mock_pdp, mock_deltas)),
    ) as mock_extract:
        from btcopilot.pdp import extract_full

        asyncio.run(extract_full(discussion, dd))

        pass1_prompt = mock_extract.call_args_list[0][0][0]
        assert '"Alice"' in pass1_prompt
        assert "Default Layer" not in pass1_prompt
