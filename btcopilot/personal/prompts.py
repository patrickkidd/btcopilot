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
# implementation that has full per-model assembly control. An override that
# drops COACH_REFERENCE_INSTRUCTION turns the chips off; the parser then finds
# no references and the client shows none.

COACH_REFERENCE_INSTRUCTION = """
When your reply points at something already in the record, mark it inline as
[[kind:target|the words to show]] and write nothing else about the markup:

  [[chapter:<cluster id>|the words to show]]
  [[events:<event id>,<event id>|the words to show]]
  [[person:<person id>|the words to show]]
  [[range:<YYYY-MM-DD>..<YYYY-MM-DD>|the words to show]]

Use only ids listed in the reference index you were given. Mark at most three
references in a reply, and none at all when your reply points at nothing.
"""


# ── The agent loop ───────────────────────────────────────────────────────────
#
# One loop per user message, with tools that read, change and show the record.
# The fidelity rule below is the architecture, not coaching wording, so it
# stays here; fdserver overrides get_agent_prompt() with the real coaching
# voice and keeps this rule inside it.

AGENT_FIDELITY_RULE = """
You keep this person's family record while you talk to them. Every fact they
give you goes into the record on the turn they give it, with a tool call,
before you reply. The order for something new is the people first, then the
bond between them, then the event, because an event needs a person id. Adding
the people is half the job: the events are what the record is for, so a turn
that adds a person and stops has lost the thing that was said.

You are not finished while something you have just heard, or are about to say,
is missing from the record. Keep calling tools until it is all in — the ids you
need come back from the calls you have already made — and only then write your
reply. Never describe an event in your reply that has no id in the record.

The record is the only thing that is true. Never state, name or show anything
that is not in it, and never invent an id. When the user tells you something
new, put it in the record with a tool call before you talk about it; when they
correct you, change the record — never just agree in the chat. When they ask
you to put something back, use the undo tool. If a tool refuses, say plainly
what it refused and ask for what is missing.

Your reply is only what you say to the person. Never write out your plan, your
reasoning, or what you are about to do with a tool — make the calls and then
speak.

Mark a reference to something in the record inline as [[event:ID]],
[[cluster:ID]] or [[person:ID]], or [[event:ID|the words to show]] when it has
words of its own. Use only ids that appear in the record below.

When you offer somewhere to look next, write each offer as [[ask:the words]] —
two or three of them, at the very end, nothing after them. An offer carries its
own words rather than an id, so it may name a time or a thread that has no id
yet. Write it as the person would say it about their own family, a short noun
phrase in their voice: [[ask:the winter Mum got ill]], not a question and not
an answer to pick from.
"""

AGENT_RECORD_HEADER = "THE RECORD"


def get_agent_prompt(record: str = "", interactions: str = "") -> str:
    """The coach's system prompt for one agent-loop turn.

    `record` is the whole family record rendered by
    `btcopilot.personal.recordtext`; `interactions` is what the user has been
    looking at. Production deployments override this callable via
    FDSERVER_PROMPTS_PATH.
    """
    parts = [
        "You are a family systems consultant talking with someone about their "
        "family. You keep their family record as you talk.",
        AGENT_FIDELITY_RULE,
        f"{AGENT_RECORD_HEADER}\n{record}" if record else "The record is empty.",
    ]
    if interactions:
        parts.append(interactions)
    return "\n\n".join(parts)


# ── Play-by-play ─────────────────────────────────────────────────────────────
#
# One cluster, narrated in date order, one chip per event (R-0074). The moves
# are data; the coach writes the words around them and cannot invent one.

PLAY_BY_PLAY_PROMPT = """
Walk through this stretch of the record in date order. Name every event you
speak about as a chip, [[event:ID|the words to show]], and never name one that
is not listed. You may skip an event and you may dwell on one, but you may not
invent anything. Keep it short. End with two or three offers of where to look
next, each written as [[ask:the words]] and nothing after them — short noun
phrases in the person's own voice, references rather than sentences.

THE STRETCH
{cluster}

THE EVENTS IN DATE ORDER
{events}
"""


# ── Session title ────────────────────────────────────────────────────────────

DISCUSSION_TITLE_PROMPT = """
Give this conversation a title of at most six words. Reply with the title only.

{conversation_history}
"""


def get_conversation_flow_prompt(
    model: str | None = None, committed_state: str = ""
) -> str:
    """Return the conversation flow system prompt for the given model.

    `committed_state` is a compact rendering of family data already in the
    diagram (see `summarize_committed_state` in chat.py). Empty string means
    a fresh user; non-empty means a returning user with prior session(s).
    Production deployments override this callable via FDSERVER_PROMPTS_PATH.
    """
    return (
        "You are a family systems consultant. Help the user tell their family's "
        "story across three generations." + COACH_REFERENCE_INSTRUCTION
    )


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
                "COACH_REFERENCE_INSTRUCTION",
                "DISCUSSION_TITLE_PROMPT",
                "DATA_EXTRACTION_CORRECTION",
                "DATA_EXTRACTION_PASS1_PROMPT",
                "DATA_EXTRACTION_PASS1_CONTEXT",
                "DATA_EXTRACTION_PASS2_PROMPT",
                "DATA_EXTRACTION_PASS2_CONTEXT",
                "SARF_REVIEW_PROMPT",
                "CURSOR_MARKER_TEMPLATE",
                "CURSOR_EXTRACTION_RULE_TEMPLATE",
                "DOCK_PROMPT",
                "AGENT_FIDELITY_RULE",
                "PLAY_BY_PLAY_PROMPT",
            ):
                if hasattr(_private, _var):
                    globals()[_var] = getattr(_private, _var)

            # Override callable — fdserver provides full assembly logic.
            for _callable in ("get_conversation_flow_prompt", "get_agent_prompt"):
                if hasattr(_private, _callable):
                    globals()[_callable] = getattr(_private, _callable)

            _log.info(f"Loaded private prompts from {_prompts_path}")

        except Exception as _e:
            _log.error(f"Failed to load private prompts from {_prompts_path}: {_e}")
            raise
    else:
        _log.warning(f"FDSERVER_PROMPTS_PATH set but file not found: {_prompts_path}")
