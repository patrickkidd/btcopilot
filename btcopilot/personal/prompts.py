"""Every prompt is a file, not a constant.

`prompty/` holds the open-source defaults. `private/prompts/` holds the ones
that are private IP, encrypted with sops and decrypted as they are read. A name
found in the private directory wins; anything missing there falls through to the
open source default, so the app runs whole with the private directory absent.
"""

import enum
import functools
import os
from pathlib import Path

from btcopilot.llmutil import RESPONSE_MODEL, _is_claude_model
from btcopilot.personal.promptdir import PromptDir

PUBLIC = Path(__file__).parent / "prompty"
PRIVATE = Path(__file__).parents[2] / "private" / "prompts"


@functools.cache
def files() -> PromptDir:
    """Where the prompts are read from. Resolved on first use, not at import,
    so a caller that points FD_PRIVATE_PROMPTS somewhere else is heard however
    early this module was imported."""
    return PromptDir([Path(os.environ.get("FD_PRIVATE_PROMPTS", PRIVATE)), PUBLIC])


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


# The prompts that take no inputs still read as module constants, but nothing is
# read from disk until one is asked for: importing this module must not decrypt
# anything, or a test run and the migration chain need a key to start.
FIXED = {
    "SUMMARIZE_MESSAGES_PROMPT": "summarize_messages",
    "DISCUSSION_TITLE_PROMPT": "discussion_title",
    "PLAY_BY_PLAY_PROMPT": "play_by_play",
    "CLUSTER_PROMPT": "cluster",
    "CLUSTER_REJECTED": "cluster_rejected",
    "DOCK_PROMPT": "dock",
    "DATA_EXTRACTION_CORRECTION": "extraction_correction",
    "DATA_EXTRACTION_PASS1_PROMPT": "extraction_pass1",
    "DATA_EXTRACTION_PASS1_CONTEXT": "extraction_pass1_context",
    "DATA_EXTRACTION_PASS2_PROMPT": "extraction_pass2",
    "DATA_EXTRACTION_PASS2_CONTEXT": "extraction_pass2_context",
    "SARF_REVIEW_PROMPT": "sarf_review",
    "CURSOR_MARKER_TEMPLATE": "cursor_marker",
    "CURSOR_EXTRACTION_RULE_TEMPLATE": "cursor_rule",
}
FRAGMENTS = {"COACH_REFERENCE_INSTRUCTION": "coach_reference"}

# What has been read so far. Kept out of the module's own namespace: reloading a
# module updates that namespace rather than emptying it, so a value cached there
# would outlive a caller that reloads to point somewhere else.
READ: dict[str, str] = {}


def __getattr__(name: str) -> str:
    if name in READ:
        return READ[name]
    if name in FIXED:
        value = files().text(FIXED[name])
    elif name in FRAGMENTS:
        value = files().fragment(FRAGMENTS[name])
    else:
        raise AttributeError(name)
    READ[name] = value
    return value


def get_conversation_flow_prompt(
    model: str | None = None, committed_state: str = ""
) -> str:
    """The coach's system prompt for a plain chat turn. Which model is answering
    is a deployment setting, so it is resolved here and never named in a prompt
    file."""
    return files().text(
        "conversation_flow",
        committed_state=committed_state,
        claude=_is_claude_model(model or RESPONSE_MODEL),
    )


def onboarding(missing: list[str], person_id: int) -> str:
    """What the coach must get first while the person's own name or birth date
    is not in the record."""
    return files().text("onboarding", missing=", ".join(missing), person_id=person_id)


def get_agent_prompt(record: str = "", interactions: str = "") -> str:
    """The coach's system prompt for one agent-loop turn. `record` is the whole
    family record rendered by `btcopilot.personal.recordtext`; `interactions` is
    what the user has been looking at."""
    return files().text("agent", committed_state=record, interactions=interactions)


def note_register() -> str:
    """What changes when the session is a clinician's note rather than a chat
    about their own family (R-0281)."""
    return files().text("note_register")


def scribe_prompt(record: str = "") -> str:
    """The review scribe's system prompt for one coding turn."""
    return files().text("scribe", committed_state=record)


def tool_meanings() -> dict[ToolText, str]:
    """What each tool parameter means to the model. A private file replaces the
    wording of the parameters it names and leaves the rest as they are, because
    what most of them mean is the shape of a value and not clinical."""
    meanings = {}
    for head in files().heads("tool_meanings"):
        meanings.update({ToolText(k): v for k, v in head["meanings"].items()})
    return meanings


def generic_name(other: str, role: Role) -> str:
    """What a parent or partner nobody named is called, so the bond can be made
    of two people rather than left half-written (R-0325 rules 9 and 10)."""
    return f"{other}'s {Role(role).value}"
