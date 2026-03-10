"""Lit-review AI coder: extraction using literature-grounded SARF definitions.

Produces a cumulative PDP using the same extraction pipeline but with SARF
definitions from doc/sarf-definitions/ instead of the tuned inline summaries.
"""

import importlib.util
import logging
import os
from pathlib import Path

from btcopilot.training.sarfdefinitions import all_condensed_definitions

_log = logging.getLogger(__name__)

# Load production prompts. In production FDSERVER_PROMPTS_PATH is set and
# personal.prompts already has the full versions. In dev that env var is
# unset so we fall back to the co-located fdserver repo.
_fdserver_path = os.environ.get("FDSERVER_PROMPTS_PATH") or str(
    Path(__file__).parent.parent.parent.parent
    / "fdserver"
    / "prompts"
    / "private_prompts.py"
)

PROMPTS_UNAVAILABLE_ERROR = (
    "Litreview AI coder is unavailable: production prompts were not found. "
    "Set FDSERVER_PROMPTS_PATH or ensure fdserver repo is co-located."
)

_BASE_PASS2_PROMPT = None

if os.path.exists(_fdserver_path):
    _spec = importlib.util.spec_from_file_location("_private_prompts", _fdserver_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _BASE_PASS2_PROMPT = _mod.DATA_EXTRACTION_PASS2_PROMPT
else:
    _log.warning(
        "Production prompts not found at %s. "
        "Litreview AI coder features will be unavailable. "
        "Set FDSERVER_PROMPTS_PATH or ensure fdserver repo is co-located.",
        _fdserver_path,
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
    if _BASE_PASS2_PROMPT is None:
        raise RuntimeError(PROMPTS_UNAVAILABLE_ERROR)
    base = _BASE_PASS2_PROMPT
    start_idx = base.find(_SARF_SECTION_START)
    end_idx = base.find(_SARF_SECTION_END)
    if start_idx == -1 or end_idx == -1:
        raise ValueError(
            "Could not find SARF VARIABLE CODING section boundaries in Pass 2 prompt. "
            "The prompt format may have changed."
        )
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


# Build prompts only if production prompts are available; otherwise set to
# None so the module can still be imported (e.g. in Docker CI).
LITREVIEW_PASS2_PROMPT = _build_pass2_prompt() if _BASE_PASS2_PROMPT else None
LITREVIEW_SARF_REVIEW_PROMPT = _build_sarf_review_prompt() if _BASE_PASS2_PROMPT else None
