import asyncio
import os
import enum
import json
import time
import logging
from dataclasses import dataclass, field, fields, MISSING
from typing import get_origin, get_args, Union

import anthropic
import openai
from google import genai
from google.genai import types
import aiohttp
from google.genai.errors import APIError, ClientError, ServerError

from btcopilot.provider import (
    Provider,
    bedrock_model,
    credentials,
    provider,
    region,
    require_bedrock_ids,
)
from btcopilot.schema import from_dict

_log = logging.getLogger(__name__)

EXTRACTION_MODEL = "gemini-3.1-flash-lite"
EXTRACTION_MODEL_LARGE = "gemini-3.6-flash"
SARF_REVIEW_MODEL = "gemini-3.6-flash"
CALIBRATION_MODEL = "gemini-3-flash-preview"

# Chat/response model: configurable via env var for A/B testing.
# Set BTCOPILOT_RESPONSE_MODEL to override. Supported values:
#   "claude-opus-5-5" (default) — Anthropic Claude Opus 5.5
#   "claude-opus-4-6" — Anthropic Claude Opus 4.6
#   Any valid Anthropic model identifier.
RESPONSE_MODEL = os.environ.get("BTCOPILOT_RESPONSE_MODEL", "claude-opus-5-5")
GEMINI_RESPONSE_MODEL = "gemini-3-flash-preview"

# Gemini does only cheap-tier work, so on Bedrock, where Google is unreachable,
# Haiku, the matching tier, answers every call that names a Gemini model.
GEMINI_STAND_IN = "claude-haiku-4-5-20251001"

TEXT_EFFORT = "medium"
STRUCTURED_EFFORT = "high"

# Client-facing model aliases → actual API model IDs.
# The Personal app sends these aliases; the backend resolves them here.
MODEL_ALIASES = {
    "opus-5.5": "claude-opus-5-5",
    "opus-4.6": "claude-opus-4-6",
    "haiku-4.5": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5-5",
    "sonnet-5": "claude-sonnet-5",
    "claude-opus-5-5": "claude-opus-5-5",
    "claude-opus-5": "claude-opus-5",
    "claude-opus-4-8": "claude-opus-4-8",
    "gpt": "gpt-6.1-sol",
}

DEFAULT_RESPONSE_MODEL_ALIAS = "opus-5.5"


def resolve_model(alias: str | None) -> str:
    """No alias is RESPONSE_MODEL; an unknown one raises KeyError."""
    return MODEL_ALIASES[alias] if alias else RESPONSE_MODEL


def is_openai(model: str) -> bool:
    return model.startswith("gpt-")


def _is_claude_model(model: str) -> bool:
    """Return True if the model identifier is a Claude/Anthropic model."""
    return model.startswith("claude-")


# Models that reject adaptive thinking and the effort setting with HTTP 400
# (both start at Opus 4.6 and Sonnet 4.6; Haiku 4.5 takes neither).
NO_ADAPTIVE_THINKING = {"claude-haiku-4-5-20251001"}


def reasoning_args(model: str, effort: str) -> dict:
    """Adaptive thinking and effort, for the models that take them (app names)."""
    if model in NO_ADAPTIVE_THINKING:
        return {}
    return {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort}}


def bedrock_models() -> set[str]:
    """Every Claude model the app may name, each of which Bedrock must serve."""
    named = {*MODEL_ALIASES.values(), RESPONSE_MODEL, GEMINI_STAND_IN}
    return {model for model in named if _is_claude_model(model)}


if provider() is Provider.Bedrock:
    require_bedrock_ids(bedrock_models())


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
    "PairBond.married": "true if the couple is or was married. false ONLY when stated as romantic but never married (dating, girlfriend/boyfriend, ex-partner). Omit when not stated",
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


def openai_client(timeout: float | None = None) -> openai.OpenAI:
    """No timeout, in seconds, is the OpenAI default."""
    return openai.OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        **({"timeout": timeout} if timeout else {}),
    )


# --- Anthropic client ---


ANTHROPIC_TIMEOUT = 120  # seconds
ANTHROPIC_MAX_RETRIES = 3


# Who answers when the requested model refuses on safety grounds: the API runs
# the same request on the next model in the list [Oracle: R-0409]. Only the
# models listed take the parameter; the API rejects it for the others.
FALLBACK_BETA = "server-side-fallback-2026-06-01"
FALLBACKS = {
    "claude-opus-5-5": ["claude-opus-5", "claude-opus-4-8"],
    "claude-opus-5": ["claude-opus-4-8"],
}


def fallback_args(model: str) -> dict:
    """The request arguments that ask for the fallbacks, on the beta client.
    Bedrock does not take the parameter."""
    chain = FALLBACKS.get(model)
    if not chain or _bedrock():
        return {}
    return {
        "betas": [FALLBACK_BETA],
        "extra_body": {"fallbacks": [{"model": name} for name in chain]},
    }


@dataclass
class Hop:
    source: str
    target: str
    category: str | None = None


@dataclass
class Served:
    """Which model answered, every hop the fallbacks made on the way, and
    whether a fallback model answered straight away because it answered this
    conversation before (the API keeps that for about an hour)."""

    model: str
    hops: list[Hop] = field(default_factory=list)
    sticky: bool = False

    @property
    def fallback(self) -> dict | None:
        if not self.hops and not self.sticky:
            return None
        return {
            "hops": [
                {"from": hop.source, "to": hop.target, "category": hop.category}
                for hop in self.hops
            ],
            "sticky": self.sticky,
        }


@dataclass
class Spent:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    def add(self, other: "Spent") -> None:
        self.input += other.input
        self.output += other.output
        self.cache_creation += other.cache_creation
        self.cache_read += other.cache_read


class Billed(Exception):
    """The provider answered and charged for the call, and then the call
    failed. What it served and spent ride on the error, so the ledger still
    gets the call's row (R-0628)."""

    def __init__(self, message: str, served: "Served", spent: Spent):
        super().__init__(message)
        self.served = served
        self.spent = spent


class OutputTruncatedError(Billed):
    pass


# A call that never came back with an answer: the provider's error, the
# connection, or the wait.
UNANSWERED = (APIError, aiohttp.ClientError, TimeoutError)


class Unreadable(Billed):
    """The answer was not the JSON asked for."""


def claude_spent(usage) -> Spent:
    return Spent(
        input=usage.input_tokens,
        output=usage.output_tokens,
        cache_creation=usage.cache_creation_input_tokens or 0,
        cache_read=usage.cache_read_input_tokens or 0,
    )


def gemini_spent(usage: types.GenerateContentResponseUsageMetadata) -> Spent:
    """Cached input is part of the prompt count and thinking is billed as
    output. Gemini keeps its cache without charging to write it."""
    cached = usage.cached_content_token_count or 0
    return Spent(
        input=usage.prompt_token_count - cached,
        output=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
        cache_read=cached,
    )


def openai_spent(usage) -> Spent:
    """OpenAI's input count holds the cached and cache-written tokens, and
    its output count holds the reasoning."""
    cached = usage.input_tokens_details.cached_tokens
    written = usage.input_tokens_details.cache_write_tokens
    return Spent(
        input=usage.input_tokens - cached - written,
        output=usage.output_tokens,
        cache_creation=written,
        cache_read=cached,
    )


@dataclass
class Text:
    words: str
    spent: Spent
    served: Served
    # Claude's stop reason; "max_tokens" when the words were cut off.
    stop: str | None = None


@dataclass
class Parsed:
    value: object
    spent: Spent
    served: Served


def served(message, label: str) -> Served:
    """Read the fallbacks off a response and log one line per hop. The SDK this
    app pins does not type the fallback block, so its ends arrive as dicts."""
    iterations = message.usage.iterations or []
    declined = {
        entry.model: getattr(entry, "stop_details", None)
        for entry in iterations
        if entry.type == "message"
    }
    hops = []
    for block in message.content:
        if block.type != "fallback":
            continue
        source = getattr(block, "from")["model"]
        details = declined.get(source)
        hop = Hop(
            source=source,
            target=block.to["model"],
            category=details.get("category") if details else None,
        )
        _log.warning(
            f"{label}: {hop.source} refused ({hop.category}), {hop.target} took over"
        )
        hops.append(hop)
    fell = any(entry.type == "fallback_message" for entry in iterations)
    sticky = fell and not hops
    if sticky:
        _log.warning(f"{label}: served by {message.model}, which took over earlier")
    return Served(model=message.model, hops=hops, sticky=sticky)


# A local Anthropic-compatible server, such as Ollama, answers every Anthropic
# call and every structured or response-text Gemini call, on the one local
# model named. The sandbox sets
# both; production sets neither. With the URL set no Anthropic key is read.
LOCAL_URL = "BTCOPILOT_LOCAL_URL"
LOCAL_MODEL = "BTCOPILOT_LOCAL_MODEL"


def anthropic_args(key: str = "ANTHROPIC_API_KEY") -> dict:
    """The client's endpoint and key: the local server's, else Anthropic's."""
    url = os.environ.get(LOCAL_URL)
    if url:
        return {"base_url": url, "api_key": "local"}
    return {"api_key": os.environ[key]}


def local_model() -> str | None:
    return os.environ[LOCAL_MODEL] if os.environ.get(LOCAL_URL) else None


def _bedrock() -> bool:
    """Whether calls go to Bedrock: the local server, when set, comes first."""
    return not os.environ.get(LOCAL_URL) and provider() is Provider.Bedrock


def check_provider() -> None:
    """Run when the app starts: Bedrock calls need the machine's AWS sign-in."""
    if _bedrock():
        credentials()


def wire_model(model: str) -> str:
    """Model name on wire: local server > Bedrock > app name."""
    if local_model():
        return local_model()
    if _bedrock():
        return bedrock_model(model)
    return model


def anthropic_client(**options) -> anthropic.Anthropic | anthropic.AnthropicBedrock:
    """A client for the local server, Bedrock or Anthropic, in that order."""
    if _bedrock():
        return anthropic.AnthropicBedrock(aws_region=region(), **options)
    return anthropic.Anthropic(**anthropic_args(), **options)


def async_anthropic_client(
    key: str = "ANTHROPIC_API_KEY", **options
) -> anthropic.AsyncAnthropic | anthropic.AsyncAnthropicBedrock:
    if _bedrock():
        return anthropic.AsyncAnthropicBedrock(aws_region=region(), **options)
    return anthropic.AsyncAnthropic(**anthropic_args(key), **options)


def _anthropic_client():
    return async_anthropic_client(
        timeout=ANTHROPIC_TIMEOUT, max_retries=ANTHROPIC_MAX_RETRIES
    )


ANTHROPIC_EXTRACTION_TIMEOUT = 600  # seconds


def _extraction_anthropic_client():
    return async_anthropic_client(
        "ANTHROPIC_EXTRACTION_API_KEY",
        timeout=ANTHROPIC_EXTRACTION_TIMEOUT,
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
      - max_output_tokens: int (default 8192, covers thinking + response)
      - prompt: str — simple single-turn prompt (alternative to turns)

    Thinking is always on and there is no sampling control; effort is the
    only knob.
    """
    start_time = time.time()
    model = kwargs.get("model", RESPONSE_MODEL)
    max_output_tokens = kwargs.get("max_output_tokens", 8192)
    system_instruction = kwargs.get("system_instruction")

    messages = _prepare_claude_messages(prompt=prompt, turns=kwargs.get("turns"))

    resolved_model = wire_model(kwargs.get("model", RESPONSE_MODEL))
    client = _anthropic_client()
    api_kwargs = {
        "model": resolved_model,
        "max_tokens": max_output_tokens,
        "messages": messages,
        **reasoning_args(kwargs.get("model", RESPONSE_MODEL), TEXT_EFFORT),
    }
    if system_instruction:
        api_kwargs["system"] = system_instruction

    try:
        response = await client.beta.messages.create(
            **api_kwargs, **fallback_args(resolved_model)
        )
        answered = served(response, f"claude_text {resolved_model}")
        content = "".join(
            block.text for block in response.content if block.type == "text"
        )
    finally:
        # Close the httpx pool inside the loop that created it. Each call
        # makes a fresh client and asyncio.run() tears down the loop; without
        # this the client's deferred close fires against a closed loop
        # ("Event loop is closed", dangling-task noise) on the next call.
        await client.close()
    _log.debug(f"Completed Claude response in {time.time() - start_time} seconds")
    _log.debug(f"claude_text(): --> \n\n{content}")
    return Text(content, claude_spent(response.usage), answered, response.stop_reason)


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
    if _is_claude_model(resolved) or local_model():
        _log.info(f"response_text using Claude: {resolved}")
        return await claude_text(prompt, model=resolved, **kwargs)
    else:
        _log.info(f"response_text using Gemini: {resolved}")
        return await gemini_text(prompt, model=resolved, **kwargs)


def response_text_sync(prompt=None, model=None, **kwargs):
    """Sync wrapper for response_text()."""
    return asyncio.run(response_text(prompt, model=model, **kwargs))


# --- Public API ---


async def gemini_structured(
    prompt, response_format, large=False, model=None, schema=None, limit=None
):
    """`schema`, when given, narrows the answer's shape beyond what the
    dataclass says, such as the values a field may take. `limit` caps the
    answer's tokens, thinking included."""
    from google.genai import types

    model = model or (EXTRACTION_MODEL_LARGE if large else EXTRACTION_MODEL)
    response_schema = schema or dataclass_to_json_schema(
        response_format, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )
    if _is_claude_model(model) or local_model():
        return await claude_structured(
            prompt, response_format, model, response_schema, limit or 32000
        )
    if _bedrock():
        return await claude_structured(
            prompt, response_format, GEMINI_STAND_IN, response_schema, limit or 32000
        )

    start_time = time.time()

    client = _client()
    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=limit or 65536,
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

    answered = Served(model=response.model_version)
    spent = gemini_spent(response.usage_metadata)
    if finish_reason == "MAX_TOKENS":
        raise OutputTruncatedError(
            "LLM response truncated due to token limit. Input data too large.",
            answered,
            spent,
        )
    try:
        result = from_dict(response_format, json.loads(response.text))
    except (ValueError, TypeError, KeyError) as error:
        raise Unreadable(f"gemini_structured {model}: {error}", answered, spent) from error
    _log.debug(f"gemini_structured(): --> {result}")
    return Parsed(result, spent, answered)


def gemini_structured_sync(
    prompt, response_format, large=False, schema=None, limit=None
):
    return asyncio.run(
        gemini_structured(
            prompt, response_format, large=large, schema=schema, limit=limit
        )
    )


CLAUDE_STRUCTURED_USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

# Constrained decoding (output_config.format) rejects the PDPDeltas schema:
# >16 nullable params is over the union limit, and subset-required objects
# time out grammar compilation. Schema goes in the prompt instead; the JSON
# is validated client-side by from_dict().
CLAUDE_JSON_INSTRUCTION = """

OUTPUT FORMAT: Respond with ONLY a single valid JSON object conforming to this JSON Schema. No markdown fences, no commentary, no text before or after the JSON. Omit optional fields rather than emitting null.

{schema}"""


async def claude_structured(prompt, response_format, model, schema, limit):
    start_time = time.time()
    full_prompt = prompt + CLAUDE_JSON_INSTRUCTION.format(schema=json.dumps(schema))

    client = _extraction_anthropic_client()
    resolved_model = wire_model(model)
    async with client.beta.messages.stream(
        model=resolved_model,
        max_tokens=limit,
        **reasoning_args(model, STRUCTURED_EFFORT),
        messages=[{"role": "user", "content": full_prompt}],
        **fallback_args(resolved_model),
    ) as stream:
        response = await stream.get_final_message()

    CLAUDE_STRUCTURED_USAGE["calls"] += 1
    CLAUDE_STRUCTURED_USAGE["input_tokens"] += response.usage.input_tokens
    CLAUDE_STRUCTURED_USAGE["output_tokens"] += response.usage.output_tokens
    _log.info(
        f"claude_structured({model}): {time.time() - start_time:.1f}s, "
        f"in={response.usage.input_tokens} out={response.usage.output_tokens}"
    )

    answered = served(response, f"claude_structured {model}")
    spent = claude_spent(response.usage)
    if response.stop_reason == "max_tokens":
        raise OutputTruncatedError(
            "LLM response truncated due to token limit. Input data too large.",
            answered,
            spent,
        )
    if response.stop_reason == "refusal":
        raise Billed(f"claude_structured refusal: {response.stop_details}", answered, spent)

    text = next(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        result = from_dict(response_format, json.loads(text))
    except (ValueError, TypeError, KeyError) as error:
        raise Unreadable(f"claude_structured {model}: {error}", answered, spent) from error
    _log.debug(f"claude_structured(): --> {result}")
    return Parsed(result, spent, answered)


async def gemini_text(prompt=None, **kwargs):
    if _bedrock():
        return await claude_text(prompt, **dict(kwargs, model=GEMINI_STAND_IN))

    if local_model():
        return await claude_text(prompt, **kwargs)
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
    return Text(
        content,
        gemini_spent(response.usage_metadata),
        Served(model=response.model_version),
    )


def gemini_text_sync(prompt=None, **kwargs):
    return asyncio.run(gemini_text(prompt, **kwargs))


async def gemini_calibration(
    prompt, system_instruction=None, deep=False, max_output_tokens=None
):
    if _bedrock():
        return await claude_text(
            prompt,
            model=GEMINI_STAND_IN,
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens or (4096 if deep else 2048),
        )
    start_time = time.time()
    if deep:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=max_output_tokens or 4096,
            thinking_config=types.ThinkingConfig(thinking_budget=4096),
        )
    else:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=max_output_tokens or 2048,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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


def gemini_calibration_sync(prompt, system_instruction=None, max_output_tokens=None):
    return asyncio.run(
        gemini_calibration(
            prompt, system_instruction, max_output_tokens=max_output_tokens
        )
    )
