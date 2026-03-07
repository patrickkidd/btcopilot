"""Family insights generation using Bowen family systems theory."""

import json
import logging

from btcopilot.schema import EventKind, from_dict, Event, Person, PairBond

_log = logging.getLogger(__name__)


INSIGHTS_PROMPT_TEMPLATE = """\
You are a family systems pattern analyst grounded in Bowen family systems theory.

Given the following family diagram data, identify 3 observations about patterns in this family system. \
Focus on:
- Reciprocal relationships (overfunctioning/underfunctioning, pursuit/distance)
- Multigenerational transmission of anxiety and functioning patterns
- Triangle patterns (when two people manage tension by involving a third)
- Correlations between life events and symptom/anxiety/functioning shifts

IMPORTANT: Each observation must reference specific events by their ID numbers. \
Keep language accessible and conversational — avoid clinical jargon. \
Do NOT provide clinical advice or diagnoses.

## People

{people_section}

## Relationships (Pair Bonds)

{pair_bonds_section}

## Events (with SARF values where present)

{events_section}

Respond with ONLY a JSON array of exactly 3 objects, each with:
- "title": a short descriptive title (under 10 words)
- "description": 2-4 sentences explaining the pattern observation
- "supporting_events": an array of event ID integers that support this observation

Example format:
[
  {{"title": "...", "description": "...", "supporting_events": [1, 3, 7]}},
  {{"title": "...", "description": "...", "supporting_events": [2, 5]}},
  {{"title": "...", "description": "...", "supporting_events": [4, 6]}}
]

DISCLAIMER TO INCLUDE IN EACH DESCRIPTION: End each description with: \
'(These observations are AI-generated pattern summaries, not clinical advice.)'
"""


def _build_people_section(people):
    """Build a text summary of people for the prompt."""
    if not people:
        return "No people in diagram."
    lines = []
    for p in people:
        name = p.get("name") or "Unknown"
        last_name = p.get("last_name", "")
        gender = p.get("gender", "unknown")
        pid = p.get("id", "?")
        full_name = f"{name} {last_name}".strip() if last_name else name
        lines.append(f"- ID {pid}: {full_name} ({gender})")
    return "\n".join(lines)


def _build_pair_bonds_section(pair_bonds, people_by_id):
    """Build a text summary of pair bonds for the prompt."""
    if not pair_bonds:
        return "No pair bonds in diagram."
    lines = []
    for pb in pair_bonds:
        a_name = people_by_id.get(pb.get("person_a"), {}).get("name", "Unknown")
        b_name = people_by_id.get(pb.get("person_b"), {}).get("name", "Unknown")
        lines.append(f"- {a_name} <-> {b_name}")
    return "\n".join(lines)


def _build_events_section(events):
    """Build a text summary of events for the prompt."""
    if not events:
        return "No events in diagram."
    lines = []
    for e in events:
        eid = e.get("id", "?")
        kind = e.get("kind", "unknown")
        desc = e.get("description", "")
        date = e.get("dateTime", "")
        person = e.get("person")
        sarf_parts = []
        if e.get("symptom"):
            sarf_parts.append(f"symptom={e['symptom']}")
        if e.get("anxiety"):
            sarf_parts.append(f"anxiety={e['anxiety']}")
        if e.get("functioning"):
            sarf_parts.append(f"functioning={e['functioning']}")
        if e.get("relationship"):
            sarf_parts.append(f"relationship={e['relationship']}")
        sarf_str = f" [{', '.join(sarf_parts)}]" if sarf_parts else ""
        person_str = f" person={person}" if person is not None else ""
        date_str = f" date={date}" if date else ""
        desc_str = f" - {desc}" if desc else ""
        lines.append(f"- Event {eid}: {kind}{desc_str}{person_str}{date_str}{sarf_str}")
    return "\n".join(lines)


def generate_insights(diagram_data):
    """Generate family system insights from diagram data using Gemini.

    Args:
        diagram_data: A DiagramData instance with people, events, pair_bonds.

    Returns:
        List of insight dicts with keys: title, description, supporting_events.
        Returns empty list if diagram has no events.
    """
    from btcopilot.llmutil import gemini_text_sync

    people = diagram_data.people or []
    events = diagram_data.events or []
    pair_bonds = diagram_data.pair_bonds or []

    if not events:
        return []

    people_by_id = {p.get("id"): p for p in people if p.get("id") is not None}

    prompt = INSIGHTS_PROMPT_TEMPLATE.format(
        people_section=_build_people_section(people),
        pair_bonds_section=_build_pair_bonds_section(pair_bonds, people_by_id),
        events_section=_build_events_section(events),
    )

    _log.info(f"Generating insights for diagram with {len(events)} events")

    response_text = gemini_text_sync(prompt=prompt, temperature=0.3)

    return _parse_insights_response(response_text)


def _parse_insights_response(response_text):
    """Parse the LLM response into structured insights.

    Returns:
        List of insight dicts, or empty list on parse failure.
    """
    try:
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language tag)
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

        insights = json.loads(text)

        if not isinstance(insights, list):
            _log.warning("Insights response is not a list")
            return []

        validated = []
        for item in insights:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            description = item.get("description", "")
            supporting_events = item.get("supporting_events", [])
            if not isinstance(supporting_events, list):
                supporting_events = []
            supporting_events = [
                e for e in supporting_events if isinstance(e, (int, float))
            ]
            validated.append(
                {
                    "title": str(title),
                    "description": str(description),
                    "supporting_events": [int(e) for e in supporting_events],
                }
            )
        return validated

    except (json.JSONDecodeError, ValueError) as e:
        _log.error(f"Failed to parse insights response: {e}")
        return []
