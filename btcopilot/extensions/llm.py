import os
import time
import enum
import json
from dataclasses import fields, MISSING
from functools import lru_cache
from typing import get_origin, get_args, Union
import logging

from btcopilot.schema import from_dict

_log = logging.getLogger(__name__)


def dataclass_to_json_schema(cls, descriptions: dict = None) -> dict:
    """Convert a dataclass to JSON Schema for Gemini structured output.

    Args:
        cls: The dataclass type to convert
        descriptions: Optional dict mapping "ClassName.field_name" to description strings
    """
    if not hasattr(cls, "__dataclass_fields__"):
        raise TypeError(f"{cls} is not a dataclass")

    descriptions = descriptions or {}
    properties = {}
    required = []
    class_name = cls.__name__

    for f in fields(cls):
        field_name = f.name
        field_type = f.type
        prop = _type_to_schema(field_type, descriptions)

        # Add description if provided
        desc_key = f"{class_name}.{field_name}"
        if desc_key in descriptions:
            prop["description"] = descriptions[desc_key]

        properties[field_name] = prop

        # Field is required if it has no default and no default_factory
        if f.default is MISSING and f.default_factory is MISSING:
            required.append(field_name)

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _type_to_schema(field_type, descriptions: dict = None) -> dict:
    """Convert a Python type annotation to JSON Schema."""
    descriptions = descriptions or {}
    origin = get_origin(field_type)

    # Handle None type
    if field_type is type(None):
        return {"type": "null"}

    # Handle list[T]
    if origin is list:
        args = get_args(field_type)
        if args:
            item_type = args[0]
            if hasattr(item_type, "__dataclass_fields__"):
                return {
                    "type": "array",
                    "items": dataclass_to_json_schema(item_type, descriptions),
                }
            else:
                return {
                    "type": "array",
                    "items": _type_to_schema(item_type, descriptions),
                }
        return {"type": "array"}

    # Handle Union types (e.g., int | None, Optional[str])
    if origin is Union or (
        hasattr(field_type, "__origin__") and str(origin) == "typing.Union"
    ):
        args = get_args(field_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _type_to_schema(non_none_args[0], descriptions)
        if non_none_args:
            return _type_to_schema(non_none_args[0], descriptions)

    # Handle X | None syntax (Python 3.10+)
    if (
        hasattr(field_type, "__class__")
        and field_type.__class__.__name__ == "UnionType"
    ):
        args = get_args(field_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _type_to_schema(non_none_args[0], descriptions)
        if non_none_args:
            return _type_to_schema(non_none_args[0], descriptions)

    # Handle Enum types
    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        enum_values = [e.value for e in field_type]
        return {"type": "string", "enum": enum_values}

    # Handle dataclasses (nested)
    if hasattr(field_type, "__dataclass_fields__"):
        return dataclass_to_json_schema(field_type, descriptions)

    # Handle basic types
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    return type_map.get(field_type, {"type": "string"})


class LLMFunction(enum.StrEnum):
    """
    Identify which models are best for which task, balancing
    accuracy/performance with cost.

    """

    General = "general"

    # Identify data in a chat message
    JSON = "json"

    # Identify whether to segue into talking about data, or continue with a
    # user's current topic
    Direction = "direction"

    # Generate both long or short summaries
    Summarize = "summarize"

    # Generate responses that look and feel like a (good) therapist
    Respond = "respond"

    PDP = "pdp"  # Pending Data Pool, used to detect data points in chat messages

    Arrange = "arrange"


# Schema descriptions for PDPDeltas - critical semantic hints for Gemini
PDP_SCHEMA_DESCRIPTIONS = {
    # PDPDeltas top-level
    "PDPDeltas.people": "NEW people mentioned for the first time. Use NEGATIVE IDs (-1, -2, etc.)",
    "PDPDeltas.events": "NEW events/incidents with specific timeframes. Use NEGATIVE IDs.",
    "PDPDeltas.pair_bonds": "NEW pair bonds between people. Use NEGATIVE IDs.",
    "PDPDeltas.delete": "IDs of items to delete from PDP.",
    # Person fields
    "Person.id": "MUST be negative integer for new entries (-1, -2, -3, etc.)",
    "Person.name": "Person's name or role (e.g., 'Mom', 'Dr. Smith', 'Brother')",
    "Person.parents": "ID of the PairBond representing this person's parents",
    # Event fields
    "Event.id": "MUST be negative integer for new entries (-1, -2, -3, etc.)",
    "Event.kind": "Type of event: shift (SARF variable change), birth, death, married, etc.",
    "Event.person": "ID of the main person this event is about",
    "Event.description": "Minimal phrase, 3 words ideal, 5 max (e.g., 'Trouble sleeping')",
    "Event.symptom": "Change in physical/mental health: up, down, or same",
    "Event.anxiety": "Change in anxiety level: up (more anxious), down (relieved), same",
    "Event.functioning": "Change in functioning: up (more productive), down (overwhelmed)",
    "Event.relationship": "Type of relationship behavior (conflict, distance, etc.)",
    "Event.relationshipTargets": "REQUIRED for relationship events: list of person IDs involved",
    "Event.relationshipTriangles": "For triangle moves: list of person IDs on the 'outside'",
    # PairBond fields
    "PairBond.id": "MUST be negative integer for new entries",
    "PairBond.person_a": "ID of first person in the bond",
    "PairBond.person_b": "ID of second person in the bond",
}


def _markdown_json_2_json(markdown_json: str) -> str:
    return markdown_json.replace("```json", "").replace("```", "")


class LLM:
    """
    Really just here to cache the clients.
    """

    @lru_cache(maxsize=1)  # Thread-safe due to lru_cache
    def _openai(self):
        import openai

        return openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def ollama(self, prompt: str, **kwargs) -> str:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            _log.debug(f"Starting ollama request")
            async with session.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3:instruct",
                    "prompt": prompt,
                    **kwargs,
                },  # , "stream": False},
            ) as response:
                _log.debug(
                    f"Completed response w/ status code {response.status} in {time.time() - start_time} seconds"
                )
                full_response = ""
                count = 0
                async for line in response.content:  # Stream NDJSON lines
                    count += 1
                    _log.debug(f"Received line {count}")
                    if line.strip():  # Skip empty lines
                        data = json.loads(line)
                        if "response" in data:  # Check if this chunk contains text
                            full_response += data["response"]
                        if data.get("done", False):  # Exit when generation is complete
                            break

                _log.debug(f"Finished getting {count} lines of ndjson")
                cleaned_response = _markdown_json_2_json(full_response)
                _log.debug(cleaned_response)
                return cleaned_response

    async def openai(self, prompt: str = None, **kwargs) -> str:
        start_time = time.time()
        if "messages" not in kwargs:
            kwargs["messages"] = [{"role": "system", "content": prompt}]
        response = await self._openai().chat.completions.create(
            model="gpt-4o-mini",
            stream=False,
            **kwargs,
        )
        content = response.choices[0].message.content
        _log.debug(f"Completed response in {time.time() - start_time} seconds")
        _log.debug(f"llm.openai(): --> \n\n{content}")
        return content

    def _gemini_client(self):
        from google import genai

        return genai.Client(api_key=os.environ["GOOGLE_GEMINI_API_KEY"])

    async def gemini(self, prompt: str = None, response_format=None):
        """Gemini for structured data extraction (PDP) using native API."""
        from google.genai import types

        start_time = time.time()

        client = self._gemini_client()
        response_schema = dataclass_to_json_schema(
            response_format, PDP_SCHEMA_DESCRIPTIONS
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        _log.debug(f"Completed response in {time.time() - start_time} seconds")
        _log.debug(f"llm.gemini() raw: {response.text}")

        # Parse JSON and convert to dataclass instance
        data = json.loads(response.text)
        result = from_dict(response_format, data)
        _log.debug(f"llm.gemini(): --> {result}")
        return result

    async def submit(self, llm_type: LLMFunction, prompt: str = None, **kwargs):
        if llm_type in (LLMFunction.JSON, LLMFunction.PDP):
            return await self.gemini(
                prompt, response_format=kwargs.get("response_format")
            )
        else:
            return await self.openai(prompt, **kwargs)

    #     if llm_type == LLMFunction.Direction:
    #         client = self._openai()
    #         model_name = current_app.config["OPENAI_DIRECTION_MODEL"]
    #         messages = [{"role": "user", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     elif llm_type == LLMFunction.JSON:
    #         # return await ollama_rest(prompt, **kwargs)
    #         return await openai_rest(self._openai(), prompt, **kwargs)

    #     elif llm_type == LLMFunction.Summarize:
    #         client = self._openai()
    #         messages = [{"role": "system", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     elif llm_type == LLMFunction.Respond:
    #         client = self._openai()
    #         messages = [{"role": "system", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     else:
    #         raise ValueError(f"Unknown LLM type: {llm_type}")

    def submit_one(self, llm_type: LLMFunction, prompt: str, **kwargs) -> str:
        """
        Submit a single LLM request and return the response.
        This is a synchronous version of submit, for use in places where
        async is not available.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.submit(llm_type, prompt, **kwargs))
