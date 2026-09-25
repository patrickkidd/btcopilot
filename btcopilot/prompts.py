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

from btcopilot.promptdir import PromptDir

# Stands in for the record while the fixed head of the agent prompt is found.
MARK = "\ue000"

PUBLIC = Path(__file__).parent / "prompty"
PRIVATE = Path(__file__).parents[1] / "private" / "prompts"


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
    Notes = "notes"
    EndDate = "end_date"
    Location = "location"
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
    ReadNotes = "read_notes"


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


def onboarding(missing: list[str], person_id: int) -> str:
    """What the coach must get first while the person's own name or birth date
    is not in the record."""
    return files().text("onboarding", missing=", ".join(missing), person_id=person_id)


def get_agent_prompt(record: str = "", interactions: str = "", today: str = "") -> str:
    """The coach's system prompt for one agent-loop turn. `record` is the whole
    family record rendered by `btcopilot.recordtext`; `interactions` is
    what the user has been looking at; `today` is the date as YYYY-MM-DD."""
    return files().text(
        "agent", committed_state=record, interactions=interactions, today=today
    )


@functools.cache
def _agent_fixed() -> str:
    """The head of the agent prompt that does not move with the record or with
    what the person has been looking at. Found by rendering the template both
    ways rather than declared, so a private template splits where it differs."""
    return os.path.commonprefix(
        [
            files().text("agent", committed_state="", interactions="", today=""),
            files().text(
                "agent", committed_state=MARK, interactions=MARK, today=MARK
            ),
        ]
    )


def agent_prompt(
    record: str = "", interactions: str = "", today: str = ""
) -> tuple[str, str]:
    """The same prompt in two parts: the coaching text that repeats every call,
    which the wire caches, and the tail that changes with the record and the
    day."""
    text = get_agent_prompt(record, interactions, today)
    fixed = _agent_fixed()
    if not text.startswith(fixed):
        raise ValueError("The agent prompt no longer opens with its fixed part")
    return fixed, text[len(fixed) :]


def question_backfill(map: str, transcript: str) -> str:
    """The system prompt for going back once over a past session to fill in the
    questions asked in it. `transcript` numbers each coach message by its
    statement id."""
    return files().text("question_backfill", map=map, transcript=transcript)


def impression_backfill(map: str, transcript: str) -> str:
    """The system prompt for going back once over a past session to fill in the
    impressions given in it, numbered the same way as the question backfill's."""
    return files().text("impression_backfill", map=map, transcript=transcript)


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
