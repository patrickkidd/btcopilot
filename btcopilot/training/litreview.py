"""Lit-review AI coder: extraction using literature-grounded SARF definitions.

Produces a cumulative PDP using the same extraction pipeline but with SARF
definitions from doc/sarf-definitions/ instead of the tuned inline summaries.
"""

import logging

from btcopilot.personal.prompts import DATA_EXTRACTION_PASS2_PROMPT
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


def _build_pass2_prompt() -> str:
    base = DATA_EXTRACTION_PASS2_PROMPT
    start_idx = base.find(_SARF_SECTION_START)
    end_idx = base.find(_SARF_SECTION_END)
    return (
        base[:start_idx]
        + _LITREVIEW_SARF_SECTION
        + base[end_idx + len(_SARF_SECTION_END) :]
    )


def _build_sarf_review_prompt() -> str:
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


# The coder rewrites one section of the private second-pass prompt. The
# open-source default has no such section, so the module still imports and the
# route answers with PROMPTS_UNAVAILABLE_ERROR instead.
_HAS_SARF_SECTION = (
    _SARF_SECTION_START in DATA_EXTRACTION_PASS2_PROMPT
    and _SARF_SECTION_END in DATA_EXTRACTION_PASS2_PROMPT
)
LITREVIEW_PASS2_PROMPT = _build_pass2_prompt() if _HAS_SARF_SECTION else None
LITREVIEW_SARF_REVIEW_PROMPT = (
    _build_sarf_review_prompt() if _HAS_SARF_SECTION else None
)
