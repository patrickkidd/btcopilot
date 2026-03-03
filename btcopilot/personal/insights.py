"""
Pattern Intelligence: generates natural-language insights about cross-generational
family patterns from extracted PDP data.
"""

import logging
import re

from btcopilot.llmutil import gemini_text_sync
from btcopilot.schema import PDP, asdict

_log = logging.getLogger(__name__)

INSIGHTS_PROMPT = """\
You are a family systems analyst trained in Bowen theory. Given this family data, \
identify 2-3 cross-generational patterns. Focus on:
- Anxiety transmission across generations
- Relationship pattern repetition (triangles, cutoffs, fusion)
- Functioning shifts that correlate across family members

Be specific — name the people and events involved. Write in plain language a \
non-clinician would understand. Return each pattern as a numbered item (1., 2., 3.).\
"""


async def generate_insights(pdp: PDP, conversation_history: str) -> list[str]:
    """
    Analyze extracted PDP for cross-generational patterns.

    Takes the complete PDP (people, events, pair_bonds) and the conversation text.
    Builds a prompt and calls the LLM to identify 2-3 patterns.

    Returns a list of insight strings, or an empty list on error.
    Never blocks extraction — errors are caught and logged.
    """
    try:
        if not pdp.people and not pdp.events:
            _log.info("No PDP data to analyze for insights")
            return []

        pdp_context = asdict(pdp)

        prompt = (
            f"{INSIGHTS_PROMPT}\n\n"
            f"## Family Data (extracted)\n"
            f"{pdp_context}\n\n"
            f"## Conversation\n"
            f"{conversation_history}\n"
        )

        response = gemini_text_sync(
            prompt,
            temperature=0.3,
            max_output_tokens=1024,
        )

        if not response or not response.strip():
            _log.warning("Empty response from LLM for insights")
            return []

        return _parse_insights(response.strip())

    except Exception:
        _log.exception("Failed to generate insights — returning empty list")
        return []


def _parse_insights(text: str) -> list[str]:
    """
    Parse LLM response into a list of insight strings.

    Handles numbered lists (1. ..., 2. ...) and double-newline separated paragraphs.
    """
    # Try numbered list first: "1.", "2.", "3." etc.
    numbered = re.split(r"\n\s*\d+\.\s+", text)
    # The first element before "1." is usually empty or a preamble
    if len(numbered) > 1:
        insights = [s.strip() for s in numbered if s.strip()]
        if insights:
            return insights

    # Fall back to double-newline separation
    paragraphs = re.split(r"\n\s*\n", text)
    insights = [p.strip() for p in paragraphs if p.strip()]
    return insights if insights else [text.strip()]
