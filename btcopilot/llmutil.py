import os
import enum
import json
import time
import logging
from dataclasses import fields, MISSING
from functools import lru_cache
from typing import get_origin, get_args, Union

from btcopilot.schema import from_dict

_log = logging.getLogger(__name__)

EXTRACTION_MODEL = "gemini-2.5-flash"
EXTRACTION_MODEL_LARGE = "gemini-2.5-flash"
RESPONSE_MODEL = "gemini-3-flash-preview"


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
}


# --- Gemini client ---


GEMINI_TIMEOUT_MS = 120_000


@lru_cache(maxsize=1)
def _client():
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=os.environ["GOOGLE_GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
    )


# --- Public API ---


async def gemini_structured(prompt, response_format, large=False):
    from google.genai import types

    start_time = time.time()
    response_schema = dataclass_to_json_schema(
        response_format, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )

    model = EXTRACTION_MODEL_LARGE if large else EXTRACTION_MODEL

    response = await _client().aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=65536,
            response_mime_type="application/json",
            response_schema=response_schema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

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
    from btcopilot.async_utils import one_result

    return one_result(gemini_structured(prompt, response_format, large=large))


async def gemini_text(prompt=None, **kwargs):
    from google.genai import types

    start_time = time.time()
    temperature = kwargs.get("temperature", 0.45)

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
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

    response = await _client().aio.models.generate_content(
        model=RESPONSE_MODEL,
        contents=contents,
        config=config,
    )
    content = response.text
    _log.debug(f"Completed response in {time.time() - start_time} seconds")
    _log.debug(f"gemini_text(): --> \n\n{content}")
    return content


def gemini_text_sync(prompt=None, **kwargs):
    from btcopilot.async_utils import one_result

    return one_result(gemini_text(prompt, **kwargs))
