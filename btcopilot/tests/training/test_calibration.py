import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from btcopilot.schema import (
    Event,
    EventKind,
    PDP,
    Person,
    PersonKind,
    RelationshipKind,
    VariableShift,
)
from btcopilot.training.sarfdefinitions import DEFINITIONS, definitions_for_event
from btcopilot.training.calibrationutils import (
    CumulativeComparison,
    Impact,
    compare_cumulative_pdps,
    prioritize_disagreements,
)


# --- sarfdefinitions ---


def test_definitions_loaded():
    expected_keys = {
        "functioning", "anxiety", "symptom",
        "conflict", "distance", "cutoff",
        "overfunctioning", "underfunctioning", "projection",
        "inside", "outside", "defined-self",
    }
    assert set(DEFINITIONS.keys()) == expected_keys
    for key, text in DEFINITIONS.items():
        assert len(text) > 100, f"Definition '{key}' suspiciously short"


def test_definitions_for_event_symptom_only():
    event = {"symptom": "up", "anxiety": None, "relationship": None, "functioning": None}
    defs = definitions_for_event(event)
    assert "symptom" in defs
    assert len(defs) == 1


def test_definitions_for_event_relationship():
    event = {"symptom": None, "anxiety": None, "relationship": "conflict", "functioning": None}
    defs = definitions_for_event(event)
    assert "relationship:conflict" in defs
    assert len(defs) == 1


def test_definitions_for_event_relationship_enum():
    event = {"symptom": None, "anxiety": None, "relationship": RelationshipKind.Overfunctioning, "functioning": None}
    defs = definitions_for_event(event)
    assert "relationship:overfunctioning" in defs


def test_definitions_for_event_multiple():
    event = {"symptom": "up", "anxiety": "up", "relationship": "distance", "functioning": "down"}
    defs = definitions_for_event(event)
    assert "symptom" in defs
    assert "anxiety" in defs
    assert "functioning" in defs
    assert "relationship:distance" in defs
    assert len(defs) == 4


def test_definitions_for_event_empty():
    event = {"symptom": None, "anxiety": None, "relationship": None, "functioning": None}
    defs = definitions_for_event(event)
    assert len(defs) == 0


# --- calibrationutils ---


def _make_pdp(people, events):
    return PDP(people=people, events=events, pair_bonds=[])


def test_compare_cumulative_pdps_perfect_agreement():
    people = [Person(id=-1, name="Alice", gender=PersonKind.Female)]
    events = [Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Up)]
    pdp_a = _make_pdp(people, events)
    pdp_b = _make_pdp(people, events)

    result = compare_cumulative_pdps(pdp_a, pdp_b, "coder_a", "coder_b")
    assert len(result.disagreements) == 0


def test_compare_cumulative_pdps_sarf_disagreement():
    people = [Person(id=-1, name="Alice", gender=PersonKind.Female)]
    events_a = [Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Up)]
    events_b = [Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Down)]
    pdp_a = _make_pdp(people, events_a)
    pdp_b = _make_pdp(people, events_b)

    result = compare_cumulative_pdps(pdp_a, pdp_b, "coder_a", "coder_b")
    assert len(result.disagreements) == 1
    assert result.disagreements[0].field_disagreements[0].field == "symptom"
    assert result.disagreements[0].max_impact == Impact.High


def test_compare_cumulative_pdps_unmatched_event():
    people_a = [Person(id=-1, name="Alice", gender=PersonKind.Female)]
    people_b = [Person(id=-1, name="Alice", gender=PersonKind.Female)]
    events_a = [Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Up)]
    events_b = []

    pdp_a = _make_pdp(people_a, events_a)
    pdp_b = _make_pdp(people_b, events_b)

    result = compare_cumulative_pdps(pdp_a, pdp_b, "coder_a", "coder_b")
    assert len(result.disagreements) == 1
    assert result.disagreements[0].max_impact == Impact.Medium


def test_compare_cumulative_pdps_relationship_disagreement():
    people = [Person(id=-1, name="Bob", gender=PersonKind.Male)]
    events_a = [Event(id=-1, kind=EventKind.Shift, person=-1, relationship=RelationshipKind.Overfunctioning)]
    events_b = [Event(id=-1, kind=EventKind.Shift, person=-1, relationship=RelationshipKind.Distance)]
    pdp_a = _make_pdp(people, events_a)
    pdp_b = _make_pdp(people, events_b)

    result = compare_cumulative_pdps(pdp_a, pdp_b, "coder_a", "coder_b")
    assert len(result.disagreements) == 1
    assert result.disagreements[0].max_impact == Impact.High


def test_prioritize_disagreements_ordering():
    people = [Person(id=-1, name="Alice", gender=PersonKind.Female)]

    # Create PDP with multiple events generating different impact levels
    events_a = [
        Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Up),
        Event(id=-2, kind=EventKind.Shift, person=-1, anxiety=VariableShift.Up),
    ]
    events_b = [
        Event(id=-1, kind=EventKind.Shift, person=-1, symptom=VariableShift.Down),  # opposite = high
        Event(id=-2, kind=EventKind.Shift, person=-1, anxiety=VariableShift.Same),  # same direction but diff = low
    ]
    pdp_a = _make_pdp(people, events_a)
    pdp_b = _make_pdp(people, events_b)

    result = compare_cumulative_pdps(pdp_a, pdp_b, "coder_a", "coder_b")
    prioritized = prioritize_disagreements(result)

    assert len(prioritized) == 2
    assert prioritized[0].max_impact == Impact.High
    assert prioritized[1].max_impact == Impact.Low


# --- batch_llm_calls rate limiting ---


def test_batch_llm_calls_single_batch():
    """<=24 prompts should fire in one batch with no sleep."""
    from btcopilot.training.routes.calibration import batch_llm_calls

    call_count = 0
    async def fake_calibration(prompt, system_instruction=None):
        nonlocal call_count
        call_count += 1
        return f"result-{call_count}"

    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls([f"p{i}" for i in range(20)], "sys"))
    assert len(results) == 20
    sleep_mock.assert_not_called()


def test_batch_llm_calls_multiple_batches():
    """50 prompts should fire in 3 batches (24+24+2) with 2 sleeps."""
    from btcopilot.training.routes.calibration import batch_llm_calls

    call_count = 0
    async def fake_calibration(prompt, system_instruction=None):
        nonlocal call_count
        call_count += 1
        return f"result-{call_count}"

    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls([f"p{i}" for i in range(50)], "sys"))
    assert len(results) == 50
    assert sleep_mock.call_count == 2
    sleep_mock.assert_called_with(60)


def test_batch_llm_calls_exactly_24():
    """Exactly 24 prompts = 1 batch, no sleep."""
    from btcopilot.training.routes.calibration import batch_llm_calls

    async def fake_calibration(prompt, system_instruction=None):
        return "ok"

    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls([f"p{i}" for i in range(24)], "sys"))
    assert len(results) == 24
    sleep_mock.assert_not_called()


def test_batch_llm_calls_75_prompts():
    """75 prompts (the failing case): 4 batches (24+24+24+3), 3 sleeps."""
    from btcopilot.training.routes.calibration import batch_llm_calls

    async def fake_calibration(prompt, system_instruction=None):
        return "ok"

    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls([f"p{i}" for i in range(75)], "sys"))
    assert len(results) == 75
    assert sleep_mock.call_count == 3
