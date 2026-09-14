"""Every prompt is a file, not a constant.

`prompty/` holds the open-source defaults. `private/prompts/` holds the ones
that are private IP, encrypted with sops and decrypted as they are read. A name
found in the private directory wins; anything missing there falls through to the
open source default, so the app runs whole with the private directory absent.
"""

import enum
import os
from pathlib import Path

from btcopilot.llmutil import RESPONSE_MODEL, _is_claude_model
from btcopilot.personal.promptdir import PromptDir

PUBLIC = Path(__file__).parent / "prompty"
PRIVATE = Path(
    os.environ.get("FD_PRIVATE_PROMPTS", Path(__file__).parents[2] / "private" / "prompts")
)

files = PromptDir([PRIVATE, PUBLIC])


class ToolText(enum.StrEnum):
    """The tool parameters whose wording the private prompts may replace."""

    EventKind = "kind"
    Description = "description"
    Person = "person"
    Spouse = "spouse"
    Child = "child"
    Anxiety = "anxiety"
    Symptom = "symptom"
    Functioning = "functioning"
    Relationship = "relationship"
    RelationshipTargets = "relationship_targets"
    RelationshipTriangles = "relationship_triangles"
    PersonA = "person_a"
    PersonB = "person_b"
    Parents = "parents"


class Role(enum.StrEnum):
    """What a generically named person is to the person they were named after."""

    Father = "father"
    Mother = "mother"
    Partner = "partner"


SUMMARIZE_MESSAGES_PROMPT = files.text("summarize_messages")
DISCUSSION_TITLE_PROMPT = files.text("discussion_title")
COACH_REFERENCE_INSTRUCTION = files.fragment("coach_reference")
PLAY_BY_PLAY_PROMPT = files.text("play_by_play")
CLUSTER_PROMPT = files.text("cluster")
CLUSTER_REJECTED = files.text("cluster_rejected")
DOCK_PROMPT = files.text("dock")
DATA_EXTRACTION_CORRECTION = files.text("extraction_correction")
DATA_EXTRACTION_PASS1_PROMPT = files.text("extraction_pass1")
DATA_EXTRACTION_PASS1_CONTEXT = files.text("extraction_pass1_context")
DATA_EXTRACTION_PASS2_PROMPT = files.text("extraction_pass2")
DATA_EXTRACTION_PASS2_CONTEXT = files.text("extraction_pass2_context")
SARF_REVIEW_PROMPT = files.text("sarf_review")
CURSOR_MARKER_TEMPLATE = files.text("cursor_marker")
CURSOR_EXTRACTION_RULE_TEMPLATE = files.text("cursor_rule")


def get_conversation_flow_prompt(
    model: str | None = None, committed_state: str = ""
) -> str:
    """The coach's system prompt for a plain chat turn. Which model is answering
    is a deployment setting, so it is resolved here and never named in a prompt
    file."""
    return files.text(
        "conversation_flow",
        committed_state=committed_state,
        claude=_is_claude_model(model or RESPONSE_MODEL),
    )


def get_agent_prompt(record: str = "", interactions: str = "") -> str:
    """The coach's system prompt for one agent-loop turn. `record` is the whole
    family record rendered by `btcopilot.personal.recordtext`; `interactions` is
    what the user has been looking at."""
    return files.text("agent", committed_state=record, interactions=interactions)


def note_register() -> str:
    """What changes when the session is a clinician's note rather than a chat
    about their own family (R-0281)."""
    return files.text("note_register")


def scribe_prompt(record: str = "") -> str:
    """The review scribe's system prompt for one coding turn."""
    return files.text("scribe", committed_state=record)


def tool_meanings() -> dict[ToolText, str]:
    """What each tool parameter means to the model."""
    return {ToolText(k): v for k, v in files.head("tool_meanings")["meanings"].items()}


def generic_name(other: str, role: Role) -> str:
    """What a parent or partner nobody named is called, so the bond can be made
    of two people rather than left half-written (R-0325 rules 9 and 10)."""
    return f"{other}'s {Role(role).value}"
