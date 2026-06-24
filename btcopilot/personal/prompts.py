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


def get_conversation_flow_prompt(
    model: str | None = None, committed_state: str = ""
) -> str:
    """Return the conversation flow system prompt for the given model.

    `committed_state` is a compact rendering of family data already in the
    diagram (see `summarize_committed_state` in chat.py). Empty string means
    a fresh user; non-empty means a returning user with prior session(s).
    Production deployments override this callable via FDSERVER_PROMPTS_PATH.
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

Valid committed person IDs (use ONLY these as positive person IDs — do NOT invent others): {committed_person_ids}
"""

SARF_REVIEW_PROMPT = """Review SARF variable coding on these events.
{events_json}
{people_json}
{conversation_history}
"""

# {nonce} is a random per-extraction token so user/transcript text cannot
# forge the boundary line.
CURSOR_MARKER_TEMPLATE = (
    "\n⟪CURSOR {nonce} — everything above this line is already in the "
    "committed diagram. Use it only as context for disambiguation. Do NOT "
    "emit new items for it. Emit items only for content BELOW this line.⟫\n"
)

CURSOR_EXTRACTION_RULE_TEMPLATE = (
    "\n\nCURSOR RULE: The conversation contains exactly one marker line "
    "'⟪CURSOR {nonce} ...⟫'. Content ABOVE that exact line is already "
    "committed — treat it as context only; do NOT emit new (negative-id) "
    "people, pair_bonds, or events for it. Emit items only for content BELOW "
    "it. You may still reference committed items above by their positive id.\n"
)


# ── Deep re-extraction dock ──────────────────────────────────────────────────
#
# Directed repair after merge_runs: one call connecting floating components to
# the main tree. Exception to the stub rule above: the measured probe wording
# (FD-338, 5/5 runs, zero false attaches) IS the default; fdserver may
# override it but must re-prove the wording.

DOCK_PROMPT = """You are reviewing a family-history conversation transcript. A diagram was
extracted from it, but some extracted family members ended up disconnected from
the main family tree. Your single job: find the stated family connection (if
any) between each floating group and the main tree.

CRITICAL INSTRUCTIONS:
- The connecting evidence is often a third-person pronoun or kinship reference
  (e.g. "that was her sister..."). You MUST resolve such references to their
  antecedent across conversation turns: work out who "her"/"his"/"their"
  refers to from the surrounding dialogue, then emit the edge to THAT person.
- One transcript speaker is the diagram owner describing THEIR OWN family.
  That speaker IS in the main tree: the proband node (named "User" when
  present, otherwise the person whose partners and children match what the
  speaker describes). First-person evidence ("I", "my", "me") from that
  speaker anchors to the proband's id — e.g. "I dated her in college" emits
  the floating ex-partner partner_of the proband.
- Emit edges ONLY for floating-group members, anchored ONLY to main-tree ids.
- relation meanings: member is partner_of anchor; member is child_of anchor;
  member is parent_of anchor; member is sibling_of anchor.
- partner_of covers ALL romantic pair-bonds, past or present: spouses,
  ex-spouses, ex-girlfriends/boyfriends, dating relationships. A past romance
  that ended without marriage still attaches: partner_of with married=false.
  On partner_of edges set married=true if the couple is or was married,
  married=false if the relationship is or was romantic but never a marriage
  (dating, girlfriend/boyfriend, ex-partner); leave married unset when not
  stated.
- Every edge MUST include a VERBATIM quote: ONE contiguous span copied exactly
  from the transcript. NEVER stitch separate sentences together with "..." and
  never paraphrase — a stitched or edited quote is rejected and the edge is
  lost. The quote must evidence the RELATION TYPE you assert — romantic
  involvement for partner_of, a parent/child statement for child_of/parent_of.
  If the person's name and the relation evidence sit in different turns, quote
  the contiguous span carrying the relation evidence and explain the name
  resolution in `reasoning`. For child_of/parent_of edges restate in
  `reasoning` which side is the parent generation.
- If the transcript never states how a group connects, verdict "none" with no
  edges. Do NOT guess or invent. A friend, colleague, or acquaintance with no
  stated romantic involvement is not family: verdict "none".

MAIN TREE (id, name):
{roster}

{floats}

TRANSCRIPT:
{transcript}"""


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
                "CURSOR_MARKER_TEMPLATE",
                "CURSOR_EXTRACTION_RULE_TEMPLATE",
                "DOCK_PROMPT",
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
