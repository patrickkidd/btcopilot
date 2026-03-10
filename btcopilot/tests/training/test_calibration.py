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
from btcopilot.training.routes.calibration import _parse_triage, _meeting_order_sort


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


def test_batch_llm_calls_small_prompts_single_batch():
    """Small prompts fitting in one token budget = 1 batch, no sleep."""
    from btcopilot.training.routes.calibration import batch_llm_calls

    async def fake_calibration(prompt, system_instruction=None):
        return "ok"

    prompts = ["short prompt"] * 20
    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls(prompts, "sys"))
    assert len(results) == 20
    sleep_mock.assert_not_called()


def test_batch_llm_calls_large_prompts_split():
    """Large prompts exceeding token budget get split across batches."""
    from btcopilot.training.routes.calibration import batch_llm_calls, TOKEN_BUDGET, CHARS_PER_TOKEN

    async def fake_calibration(prompt, system_instruction=None):
        return "ok"

    # Each prompt uses ~half the budget so 2 fit per batch, 5 prompts = 3 batches
    chars_per_prompt = (TOKEN_BUDGET * CHARS_PER_TOKEN) // 2 - 1000
    prompts = ["x" * chars_per_prompt for _ in range(5)]

    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls(prompts, "sys"))
    assert len(results) == 5
    assert sleep_mock.call_count == 2


def test_batch_llm_calls_single_huge_prompt():
    """A single prompt exceeding the budget still gets processed."""
    from btcopilot.training.routes.calibration import batch_llm_calls, TOKEN_BUDGET, CHARS_PER_TOKEN

    async def fake_calibration(prompt, system_instruction=None):
        return "ok"

    huge = "x" * (TOKEN_BUDGET * CHARS_PER_TOKEN * 2)
    with patch("btcopilot.training.routes.calibration.gemini_calibration", fake_calibration), \
         patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        results = asyncio.run(batch_llm_calls([huge, "small"], "sys"))
    assert len(results) == 2
    assert sleep_mock.call_count == 1


# --- _parse_triage ---


def test_parse_triage_clear():
    assert _parse_triage("**Triage:** CLEAR\n**Verdict:** ...") == "clear"


def test_parse_triage_discuss():
    assert _parse_triage("**Triage:** DISCUSS\n**Verdict:** ...") == "discuss"


def test_parse_triage_fallback():
    assert _parse_triage("Some unexpected output\nwithout triage") == "discuss"


def test_parse_triage_case_insensitive():
    assert _parse_triage("**Triage:** Clear\n**Verdict:** ...") == "clear"


# --- _meeting_order_sort ---


def test_meeting_order_sort():
    items = [
        {"triage": "discuss", "impact": "high"},
        {"triage": "clear", "impact": "low"},
        {"triage": "discuss", "impact": "low"},
        {"triage": "clear", "impact": "high"},
    ]
    sorted_items = _meeting_order_sort(items)
    assert sorted_items[0] == {"triage": "clear", "impact": "high"}
    assert sorted_items[1] == {"triage": "clear", "impact": "low"}
    assert sorted_items[2] == {"triage": "discuss", "impact": "high"}
    assert sorted_items[3] == {"triage": "discuss", "impact": "low"}
