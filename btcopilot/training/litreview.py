"""Lit-review AI coder: extraction using literature-grounded SARF definitions.

Produces a cumulative PDP using the same extraction pipeline but with SARF
definitions from doc/sarf-definitions/ instead of the tuned inline summaries.
"""

import importlib.util
import os
from pathlib import Path

from btcopilot.training.sarfdefinitions import all_condensed_definitions

# Load production prompts. In production FDSERVER_PROMPTS_PATH is set and
# personal.prompts already has the full versions. In dev that env var is
# unset so we fall back to the co-located fdserver repo.
_fdserver_path = os.environ.get("FDSERVER_PROMPTS_PATH") or str(
    Path(__file__).parent.parent.parent.parent
    / "fdserver"
    / "prompts"
    / "private_prompts.py"
)

if os.path.exists(_fdserver_path):
    _spec = importlib.util.spec_from_file_location("_private_prompts", _fdserver_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _BASE_PASS2_PROMPT = _mod.DATA_EXTRACTION_PASS2_PROMPT
    _BASE_SARF_REVIEW = _mod.SARF_REVIEW_PROMPT
else:
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "Cannot find production prompts at %s. "
        "Litreview functionality will be unavailable. "
        "Set FDSERVER_PROMPTS_PATH or ensure fdserver repo is co-located.",
        _fdserver_path,
    )
    _BASE_PASS2_PROMPT = None
    _BASE_SARF_REVIEW = None

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
        raise FileNotFoundError(
            f"Cannot find production prompts at {_fdserver_path}. "
            "Set FDSERVER_PROMPTS_PATH or ensure fdserver repo is co-located."
        )
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
    if _BASE_SARF_REVIEW is None:
        raise FileNotFoundError(
            f"Cannot find production prompts at {_fdserver_path}. "
            "Set FDSERVER_PROMPTS_PATH or ensure fdserver repo is co-located."
        )
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


# Lazy module-level attributes — only built when accessed, so the module can be
# imported without fdserver prompts being available (e.g. Docker CI).
def __getattr__(name):
    if name == "LITREVIEW_PASS2_PROMPT":
        val = _build_pass2_prompt()
        globals()["LITREVIEW_PASS2_PROMPT"] = val
        return val
    if name == "LITREVIEW_SARF_REVIEW_PROMPT":
        val = _build_sarf_review_prompt()
        globals()["LITREVIEW_SARF_REVIEW_PROMPT"] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
