"""Lit-review AI coder: extraction using literature-grounded SARF definitions.

Produces a cumulative PDP using the same extraction pipeline but with SARF
definitions from doc/sarf-definitions/ instead of the tuned inline summaries.
"""

import functools
import logging

from btcopilot.personal import prompts
from btcopilot.training.sarfdefinitions import all_condensed_definitions

_log = logging.getLogger(__name__)

PROMPTS_UNAVAILABLE_ERROR = (
    "Litreview AI coder is unavailable: it rewrites one section of the private "
    "second-pass extraction prompt, and only the open-source default is installed."
)

AUDITOR_ID = "litreview-ai"

_LITREVIEW_DEFS = all_condensed_definitions()

# ── Pass 2 prompt: replace SARF VARIABLE CODING section ──────────────────────

_SARF_SECTION_START = "═══════════════════════════════════════════════════════════════════════════════\nSARF VARIABLE CODING\n═══════════════════════════════════════════════════════════════════════════════"
_SARF_SECTION_END = "═══════════════════════════════════════════════════════════════════════════════\nEVENT FIELD RULES\n═══════════════════════════════════════════════════════════════════════════════"

_LITREVIEW_SARF_SECTION = f"""\
═══════════════════════════════════════════════════════════════════════════════
SARF VARIABLE CODING (Literature-Grounded Operational Definitions)
═══════════════════════════════════════════════════════════════════════════════

Each shift event should have at least one SARF variable coded. Use the
operational definitions below to classify each event.

**Variable values:**
- **symptom**: "up" / "down" / "same" / null
- **anxiety**: "up" / "down" / "same" / null
- **functioning**: "up" / "down" / "same" / null
- **relationship**: distance / cutoff / conflict / overfunctioning / underfunctioning / projection / toward / away / defined-self / fusion / inside / outside / null

  REQUIRED fields for relationship events:
  - `relationshipTargets`: WHO the person interacted with (REQUIRED, NEVER empty)
  - `relationshipTriangles`: REQUIRED when relationship is "inside" or "outside"

{_LITREVIEW_DEFS}

═══════════════════════════════════════════════════════════════════════════════
EVENT FIELD RULES
═══════════════════════════════════════════════════════════════════════════════"""


# The coder rewrites one section of the private second-pass prompt. The
# open-source default has no such section, so both prompts read as None and the
# route answers with PROMPTS_UNAVAILABLE_ERROR instead. Read on first use, never
# at import: the private prompts are encrypted and a test run holds no key.
@functools.cache
def pass2_prompt() -> str | None:
    base = prompts.DATA_EXTRACTION_PASS2_PROMPT
    start_idx = base.find(_SARF_SECTION_START)
    end_idx = base.find(_SARF_SECTION_END)
    if start_idx < 0 or end_idx < 0:
        return None
    return (
        base[:start_idx]
        + _LITREVIEW_SARF_SECTION
        + base[end_idx + len(_SARF_SECTION_END) :]
    )


@functools.cache
def sarf_review_prompt() -> str | None:
    if pass2_prompt() is None:
        return None
    return f"""\
You are reviewing clinical shift events extracted from a family therapy discussion.

For each event below, verify and correct the SARF variable coding using the
literature-grounded operational definitions provided.

{_LITREVIEW_DEFS}

**REVIEW EACH EVENT and return the corrected version. Keep all fields unchanged except SARF variables.**

Events to review:
{{events_json}}

People context:
{{people_json}}

Original conversation:
{{conversation_history}}
"""
