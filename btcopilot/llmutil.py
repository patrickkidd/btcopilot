import asyncio
import os
import enum
import json
import time
import logging
from dataclasses import fields, MISSING
from typing import get_origin, get_args, Union

from google.genai.errors import ClientError, ServerError

from btcopilot.schema import from_dict

_log = logging.getLogger(__name__)

EXTRACTION_MODEL = "gemini-3-flash-preview"
EXTRACTION_MODEL_LARGE = "gemini-3-flash-preview"
CALIBRATION_MODEL = "gemini-3-flash-preview"

# Chat/response model: configurable via env var for A/B testing.
# Set BTCOPILOT_RESPONSE_MODEL to override. Supported values:
#   "claude-opus-4-6" (default) — Anthropic Claude Opus 4.6
#   "gemini-3-flash-preview" — Google Gemini Flash (legacy)
#   Any valid Anthropic or Gemini model identifier.
# The backend is auto-detected from the model name prefix.
RESPONSE_MODEL = os.environ.get("BTCOPILOT_RESPONSE_MODEL", "claude-opus-4-6")
GEMINI_RESPONSE_MODEL = "gemini-3-flash-preview"

CLAUDE_THINKING_BUDGET = 4096

# Client-facing model aliases → actual API model IDs.
# The Personal app sends these aliases; the backend resolves them here.
MODEL_ALIASES = {
    "opus-4.6": "claude-opus-4-6",
    "gemini-2.5-flash": "gemini-2.5-flash",
}

DEFAULT_RESPONSE_MODEL_ALIAS = "opus-4.6"


def resolve_model(alias: str | None) -> str:
    """Resolve a client-facing model alias to an API model ID.

    Falls back to RESPONSE_MODEL if alias is None or unknown.
    """
    if alias and alias in MODEL_ALIASES:
        return MODEL_ALIASES[alias]
    return RESPONSE_MODEL


def _is_claude_model(model: str) -> bool:
    """Return True if the model identifier is a Claude/Anthropic model."""
    return model.startswith("claude-")


class OutputTruncatedError(Exception):
    pass


# --- JSON Schema generation for Gemini structured output ---


def dataclass_to_json_schema(
    cls, descriptions: dict = None, force_required: dict = None
) -> dict:
    """Convert a dataclass to JSON Schema for Gemini structured output."""
    if not hasattr(cls, "__dataclass_fields__"):
        raise TypeError(f"{cls} is not a dataclass")

    descriptions = descriptions or {}
    force_required = force_required or {}
    properties = {}
    required = []
    class_name = cls.__name__
    class_force_required = force_required.get(class_name, [])

    for f in fields(cls):
        field_name = f.name
        field_type = f.type
        prop = _type_to_schema(field_type, descriptions, force_required)

        desc_key = f"{class_name}.{field_name}"
        if desc_key in descriptions:
            prop["description"] = descriptions[desc_key]

        properties[field_name] = prop

        if f.default is MISSING and f.default_factory is MISSING:
            required.append(field_name)
        elif field_name in class_force_required:
            required.append(field_name)

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _type_to_schema(
    field_type, descriptions: dict = None, force_required: dict = None
) -> dict:
    descriptions = descriptions or {}
    force_required = force_required or {}
    origin = get_origin(field_type)

    if field_type is type(None):
        return {"type": "null"}

    if origin is list:
        args = get_args(field_type)
        if args:
            item_type = args[0]
            if hasattr(item_type, "__dataclass_fields__"):
                return {
                    "type": "array",
                    "items": dataclass_to_json_schema(
                        item_type, descriptions, force_required
                    ),
                }
            else:
                return {
                    "type": "array",
                    "items": _type_to_schema(item_type, descriptions, force_required),
                }
        return {"type": "array"}

    if origin is Union or (
        hasattr(field_type, "__origin__") and str(origin) == "typing.Union"
    ):
        args = get_args(field_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _type_to_schema(non_none_args[0], descriptions, force_required)
        if non_none_args:
            return _type_to_schema(non_none_args[0], descriptions, force_required)

    if (
        hasattr(field_type, "__class__")
        and field_type.__class__.__name__ == "UnionType"
    ):
        args = get_args(field_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _type_to_schema(non_none_args[0], descriptions, force_required)
        if non_none_args:
            return _type_to_schema(non_none_args[0], descriptions, force_required)

    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        enum_values = [e.value for e in field_type]
        return {"type": "string", "enum": enum_values}

    if hasattr(field_type, "__dataclass_fields__"):
        return dataclass_to_json_schema(field_type, descriptions, force_required)

    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    return type_map.get(field_type, {"type": "string"})


# --- PDP schema hints for Gemini ---

PDP_SCHEMA_DESCRIPTIONS = {
    "PDPDeltas.people": "NEW people mentioned for the first time. Use NEGATIVE IDs (-1, -2, etc.)",
    "PDPDeltas.events": "NEW events/incidents with specific timeframes. Use NEGATIVE IDs.",
    "PDPDeltas.pair_bonds": "NEW pair bonds between people. Use NEGATIVE IDs.",
    "PDPDeltas.delete": "IDs of items to delete from PDP.",
    "Person.id": "REQUIRED - MUST be negative integer for new entries (-1, -2, -3, etc.)",
    "Person.name": "Person's name or role (e.g., 'Mom', 'Dr. Smith', 'Brother')",
    "Person.parents": "ID of the PairBond representing this person's parents",
    "Event.id": "REQUIRED - NEVER null. MUST be negative integer for new entries (-1, -2, -3, etc.)",
    "Event.kind": "REQUIRED - NEVER null.Type of event: shift (SARF variable change), birth, death, married, etc.",
    "Event.person": "REQUIRED - NEVER null. ID of the main person this event is about",
    "Event.description": "REQUIRED - NEVER null. Minimal phrase, 3 words ideal, 5 max (e.g., 'Trouble sleeping', 'Diagnosed with dementia')",
    "Event.notes": "Optional additional detail about the event, multi-line text for context not captured in description. May contain opinions, feelings, and other subjective material that adds detail to the factual Event.description. Put opinions in quotes.",
    "Event.dateTime": "REQUIRED - NEVER null. When it happened (ISO format or fuzzy like '2025-03-15')",
    "Event.dateCertainty": "REQUIRED - NEVER null. Certainty of the date: certain, approximate, unknown",
    "Event.symptom": "Change in physical/mental health: up, down, or same",
    "Event.anxiety": "Change in anxiety level: up (more anxious), down (relieved), same",
    "Event.functioning": "Change in functioning: up (more productive), down (overwhelmed)",
    "Event.relationship": "Type of relationship behavior (conflict, distance, etc.)",
    "Event.relationshipTargets": "REQUIRED for relationship events: list of person IDs involved",
    "Event.relationshipTriangles": "For triangle moves: list of person IDs on the 'outside'",
    "PairBond.id": "REQUIRED - NEVER null. MUST be negative integer for new entries",
    "PairBond.person_a": "REQUIRED - NEVER null. ID of first person in the bond",
    "PairBond.person_b": "REQUIRED - NEVER null. ID of second person in the bond",
}

PDP_FORCE_REQUIRED = {
    "Event": ["description", "dateTime", "person", "dateCertainty"],
    "PairBond": ["id", "person_a", "person_b"],
}


# --- Gemini client ---


GEMINI_TIMEOUT_MS = 120_000
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_BACKOFF = 5  # seconds, doubled each retry


def _client():
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=os.environ["GOOGLE_GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
    )


# --- Anthropic client ---


ANTHROPIC_TIMEOUT = 120  # seconds
ANTHROPIC_MAX_RETRIES = 3


def _anthropic_client():
    import anthropic

    return anthropic.AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=ANTHROPIC_TIMEOUT,
        max_retries=ANTHROPIC_MAX_RETRIES,
    )


def _prepare_claude_messages(prompt=None, turns=None):
    """Build Anthropic-compatible messages from prompt or turns.

    Handles:
      - Mapping Gemini role "model" to Anthropic "assistant"
      - Prepending a user turn if conversation starts with assistant
      - Merging consecutive same-role messages (Anthropic requires alternating)

    Returns list of {"role": str, "content": str} dicts.
    """
    if turns:
        messages = []
        for role, text in turns:
            api_role = "assistant" if role == "model" else "user"
            messages.append({"role": api_role, "content": text})
    elif prompt:
        messages = [{"role": "user", "content": prompt}]
    else:
        raise ValueError("Requires either 'prompt' or 'turns'")

    # Anthropic requires messages to start with "user" role.
    if messages and messages[0]["role"] == "assistant":
        messages.insert(0, {"role": "user", "content": "Hello"})

    # Anthropic requires strictly alternating user/assistant messages.
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] += "\n\n" + msg["content"]
        else:
            merged.append(msg)
    return merged


async def claude_text(prompt=None, **kwargs):
    """Generate unstructured text using Claude (Anthropic API).

    Accepts the same interface as gemini_text():
      - model: str — Claude model identifier (default: RESPONSE_MODEL)
      - system_instruction: str — system prompt
      - turns: list of (role, text) tuples — "user"/"model" mapped to "user"/"assistant"
      - temperature: float (ignored when thinking is enabled — API forces 1.0)
      - max_output_tokens: int (default 8192, covers thinking + response)
      - prompt: str — simple single-turn prompt (alternative to turns)

    When CLAUDE_THINKING_BUDGET > 0, extended thinking is enabled (forces
    temperature=1.0 per Anthropic API). When 0, thinking is disabled and
    temperature from kwargs is respected.
    """
    start_time = time.time()
    model = kwargs.get("model", RESPONSE_MODEL)
    max_output_tokens = kwargs.get("max_output_tokens", 8192)
    system_instruction = kwargs.get("system_instruction")

    messages = _prepare_claude_messages(prompt=prompt, turns=kwargs.get("turns"))

    resolved_model = kwargs.get("model", RESPONSE_MODEL)
    client = _anthropic_client()
    api_kwargs = {
        "model": resolved_model,
        "max_tokens": max_output_tokens,
        "messages": messages,
    }
    if CLAUDE_THINKING_BUDGET > 0:
        api_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": CLAUDE_THINKING_BUDGET,
        }
    else:
        temperature = kwargs.get("temperature", 0.45)
        api_kwargs["temperature"] = temperature
    if system_instruction:
        api_kwargs["system"] = system_instruction

    response = await client.messages.create(**api_kwargs)

    content = "".join(block.text for block in response.content if block.type == "text")
    _log.debug(f"Completed Claude response in {time.time() - start_time} seconds")
    _log.debug(f"claude_text(): --> \n\n{content}")
    return content


def claude_text_sync(prompt=None, **kwargs):
    return asyncio.run(claude_text(prompt, **kwargs))


# --- Unified response text API (routes to Claude or Gemini based on model) ---


async def response_text(prompt=None, model=None, **kwargs):
    """Generate text using the configured RESPONSE_MODEL or an override.

    Auto-routes to Claude or Gemini based on model name. Same interface as
    gemini_text() / claude_text(). Use this instead of calling either directly
    for any code that should respect the RESPONSE_MODEL setting.

    model: optional client-facing alias (e.g. "opus-4.6") or raw API model ID.
    """
    resolved = resolve_model(model) if model else RESPONSE_MODEL
    if _is_claude_model(resolved):
        _log.info(f"response_text using Claude: {resolved}")
        return await claude_text(prompt, model=resolved, **kwargs)
    else:
        _log.info(f"response_text using Gemini: {resolved}")
        return await gemini_text(prompt, model=resolved, **kwargs)


def response_text_sync(prompt=None, model=None, **kwargs):
    """Sync wrapper for response_text()."""
    return asyncio.run(response_text(prompt, model=model, **kwargs))


# --- Public API ---


async def gemini_structured(prompt, response_format, large=False):
    from google.genai import types

    start_time = time.time()
    response_schema = dataclass_to_json_schema(
        response_format, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )

    model = EXTRACTION_MODEL_LARGE if large else EXTRACTION_MODEL

    client = _client()
    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=65536,
        response_mime_type="application/json",
        response_schema=response_schema,
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
    )

    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            break
        except ServerError as e:
            if attempt == GEMINI_MAX_RETRIES - 1:
                raise
            delay = GEMINI_RETRY_BACKOFF * (2**attempt)
            _log.warning(
                f"Gemini ServerError (attempt {attempt + 1}/{GEMINI_MAX_RETRIES}), "
                f"retrying in {delay}s: {e}"
            )
            await asyncio.sleep(delay)

    _log.debug(f"Completed response in {time.time() - start_time} seconds")
    finish_reason = response.candidates[0].finish_reason
    _log.debug(f"gemini_structured() finish_reason: {finish_reason}")
    _log.debug(f"gemini_structured() raw: {response.text}")

    if finish_reason == "MAX_TOKENS":
        raise OutputTruncatedError(
            "LLM response truncated due to token limit. Input data too large."
        )

    data = json.loads(response.text)
    result = from_dict(response_format, data)
    _log.debug(f"gemini_structured(): --> {result}")
    return result


def gemini_structured_sync(prompt, response_format, large=False):
    return asyncio.run(gemini_structured(prompt, response_format, large=large))


async def gemini_text(prompt=None, **kwargs):
    from google.genai import types

    start_time = time.time()
    model = kwargs.get("model", GEMINI_RESPONSE_MODEL)
    temperature = kwargs.get("temperature", 0.45)

    max_output_tokens = kwargs.get("max_output_tokens", 2048)
    thinking_budget = kwargs.get("thinking_budget", 4096)
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
    )

    system_instruction = kwargs.get("system_instruction")
    turns = kwargs.get("turns")
    if system_instruction and turns:
        config.system_instruction = system_instruction
        contents = [
            types.Content(role=role, parts=[types.Part(text=text)])
            for role, text in turns
        ]
    else:
        contents = prompt

    client = _client()
    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            resolved_model = kwargs.get("model", GEMINI_RESPONSE_MODEL)
            response = await client.aio.models.generate_content(
                model=resolved_model,
                contents=contents,
                config=config,
            )
            break
        except ServerError as e:
            if attempt == GEMINI_MAX_RETRIES - 1:
                raise
            delay = GEMINI_RETRY_BACKOFF * (2**attempt)
            _log.warning(
                f"Gemini ServerError (attempt {attempt + 1}/{GEMINI_MAX_RETRIES}), "
                f"retrying in {delay}s: {e}"
            )
            await asyncio.sleep(delay)

    content = response.text
    _log.debug(f"Completed response in {time.time() - start_time} seconds")
    _log.debug(f"gemini_text(): --> \n\n{content}")
    return content


def gemini_text_sync(prompt=None, **kwargs):
    return asyncio.run(gemini_text(prompt, **kwargs))


async def gemini_calibration(prompt, system_instruction=None, deep=False):
    from google.genai import types

    start_time = time.time()
    if deep:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=4096),
        )
    else:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
        )
    if system_instruction:
        config.system_instruction = system_instruction

    client = _client()
    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=CALIBRATION_MODEL,
                contents=prompt,
                config=config,
            )
            break
        except ClientError as e:
            if "RESOURCE_EXHAUSTED" not in str(e) or attempt == GEMINI_MAX_RETRIES - 1:
                raise
            delay = 30 * (attempt + 1)
            _log.warning(
                f"Gemini rate limit (attempt {attempt + 1}/{GEMINI_MAX_RETRIES}), "
                f"retrying in {delay}s"
            )
            await asyncio.sleep(delay)
        except ServerError as e:
            if attempt == GEMINI_MAX_RETRIES - 1:
                raise
            delay = GEMINI_RETRY_BACKOFF * (2**attempt)
            _log.warning(
                f"Gemini ServerError (attempt {attempt + 1}/{GEMINI_MAX_RETRIES}), "
                f"retrying in {delay}s: {e}"
            )
            await asyncio.sleep(delay)

    content = response.text
    _log.debug(f"gemini_calibration() completed in {time.time() - start_time}s")
    _log.debug(f"gemini_calibration(): --> \n\n{content}")
    return content


def gemini_calibration_sync(prompt, system_instruction=None):
    return asyncio.run(gemini_calibration(prompt, system_instruction))
