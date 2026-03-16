# ═══════════════════════════════════════════════════════════════════════════════
# Prompt stubs — architecture only
#
# Production prompts live in fdserver/prompts/private_prompts.py (private IP).
# These stubs define the variable names and assembly logic so the framework
# works without fdserver during development and testing. The real content is
# loaded at runtime via FDSERVER_PROMPTS_PATH.
#
# RULES:
# - Do NOT put real prompt content here. It belongs in fdserver.
# - String constants must appear in the override loop below.
# - Callables (get_conversation_flow_prompt) are overridden separately.
# - Stubs must be syntactically valid so unit tests pass without fdserver.
# ═══════════════════════════════════════════════════════════════════════════════


# ── Conversation summarization ───────────────────────────────────────────────
# Production version: condenses multi-turn conversation history for context
# window management, preserving family structure and emotional themes.

SUMMARIZE_MESSAGES_PROMPT = """
Summarize the following discussion.

{conversation_history}
"""


# ── Conversation flow ─────────────────────────────────────────────────────────
#
# fdserver overrides get_conversation_flow_prompt() with a production
# implementation that has full per-model assembly control.


def get_conversation_flow_prompt(model: str | None = None) -> str:
    """Return the conversation flow system prompt for the given model.

    Stub — returns a minimal generic prompt. Production deployments override
    this callable via FDSERVER_PROMPTS_PATH with full Bowen interview protocol
    and model-specific response style tuning.
    """
    return "You are a family systems consultant. Help the user tell their family's story across three generations."


# ── Data extraction — 2-pass (structure then SARF shifts) ────────────────────
#
# Production pass 1: extracts people, pair bonds, parent-child relationships,
# and structural events (birth, death, marriage, etc.) from conversation text.
# Includes JSON schema definitions and detailed field-level instructions.
#
# Production pass 2: extracts shift events with full SARF variable coding
# (stress, anxiety, reactivity, functioning) from the same conversation,
# using pass 1 output as context to avoid duplicating structural data.
#
# Production correction: re-extracts failed deltas using error feedback,
# with specific guidance on common schema validation failures.
#
# Production SARF review: audits SARF variable coding against Bowen theory
# definitions, checking for miscoded anxiety/reactivity/functioning levels.

DATA_EXTRACTION_PASS1_PROMPT = """Extract people, pair bonds, and structural
events. Today's date is {{current_date}}."""

DATA_EXTRACTION_PASS1_CONTEXT = """
{diagram_data}
{conversation_history}
"""

DATA_EXTRACTION_PASS2_PROMPT = """Extract shift events with SARF variables.
Today's date is {{current_date}}."""

DATA_EXTRACTION_PASS2_CONTEXT = """
{pass1_data}
{committed_shift_events}
{conversation_history}
"""

DATA_EXTRACTION_CORRECTION = """
Fix errors in these deltas:
{failed_deltas}
{error_history}
"""

SARF_REVIEW_PROMPT = """Review SARF variable coding on these events.
{events_json}
{people_json}
{conversation_history}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT OVERRIDE MECHANISM
# ═══════════════════════════════════════════════════════════════════════════════
#
# Production deployments override these stubs by setting FDSERVER_PROMPTS_PATH
# to a Python file that defines the real prompt variables.
#
# Example: FDSERVER_PROMPTS_PATH=/app/prompts/private_prompts.py
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os
import importlib.util as _importlib_util
import logging as _logging

_log = _logging.getLogger(__name__)
_prompts_path = _os.environ.get("FDSERVER_PROMPTS_PATH")

if _prompts_path:
    if _os.path.exists(_prompts_path):
        try:
            _spec = _importlib_util.spec_from_file_location(
                "_private_prompts", _prompts_path
            )
            _private = _importlib_util.module_from_spec(_spec)
            _spec.loader.exec_module(_private)

            # Override prompt constants from private file.
            for _var in (
                "SUMMARIZE_MESSAGES_PROMPT",
                "DATA_EXTRACTION_CORRECTION",
                "DATA_EXTRACTION_PASS1_PROMPT",
                "DATA_EXTRACTION_PASS1_CONTEXT",
                "DATA_EXTRACTION_PASS2_PROMPT",
                "DATA_EXTRACTION_PASS2_CONTEXT",
                "SARF_REVIEW_PROMPT",
            ):
                if hasattr(_private, _var):
                    globals()[_var] = getattr(_private, _var)

            # Override callable — fdserver provides full assembly logic.
            if hasattr(_private, "get_conversation_flow_prompt"):
                globals()[
                    "get_conversation_flow_prompt"
                ] = _private.get_conversation_flow_prompt

            _log.info(f"Loaded private prompts from {_prompts_path}")

        except Exception as _e:
            _log.error(f"Failed to load private prompts from {_prompts_path}: {_e}")
            raise
    else:
        _log.warning(f"FDSERVER_PROMPTS_PATH set but file not found: {_prompts_path}")
