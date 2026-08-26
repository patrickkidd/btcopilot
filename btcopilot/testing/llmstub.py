"""Deterministic LLM doubles for the sandbox harness.

Enabled by BTCOPILOT_LLM=stub. Replaces llmutil's client factories rather than
its public functions, because callers bind those functions at import time while
the factories are looked up per call.

Chat returns a coach reply echoing the user's last statement. Extraction stages
one person per capitalized word in the conversation that is not already
committed, plus one shift event on the first of them.

With stubbing off nothing is patched, so a call with no key fails the way it
does in production — but note that Flask's app.run() loads the nearest .env
before serving, which on a developer machine supplies real provider keys the
launcher never set. A sandbox that must not reach a provider has to blank the
names in credentials.BLANKED in the server's environment; credentialed()
reports what the serving process actually ended up with.
"""

import enum
import json
import os
import re

from btcopilot import llmutil
from btcopilot.personal import prompts
from btcopilot.testing.credentials import BLANKED
from btcopilot.schema import (
    DateCertainty,
    Event,
    EventKind,
    VariableShift,
    asdict,
)

LLM_ENV = "BTCOPILOT_LLM"
STUB_EVENT_DATE = "2020-01-01"
FACTORIES = ("_client", "_anthropic_client", "_extraction_anthropic_client")

# Pronouns and connectives that survive the sentence-initial rule below because
# they follow a comma. Every word the prompt templates themselves use is
# subtracted at install time, so this stays short.
STOP_WORDS = frozenset(
    """Because Before But However Not Then There They This Though Which While Who""".split()
)

_SPEAKER_LINE = re.compile(r"^(?![ \t\W])([^:\n]{1,40}): (.+)$", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CAPITALIZED = re.compile(r"\b[A-Z][a-z]{2,}\b")
_JSON_NAME = re.compile(r'"name":\s*"([^"]*)"')

_originals: dict = {}
_boilerplate: frozenset = frozenset()


class LLMMode(enum.StrEnum):
    Stub = "stub"
    Real = "real"


def stubbed() -> bool:
    return os.getenv(LLM_ENV) == LLMMode.Stub.value


def credentialed() -> bool:
    """Whether the serving process holds any credential a sandbox should have
    been stripped of. Reports presence only — never a key."""
    return any(os.getenv(name) for name in BLANKED)


def install():
    global _boilerplate
    if _originals:
        return
    _boilerplate = _prompt_vocabulary()
    for name in FACTORIES:
        _originals[name] = getattr(llmutil, name)
    llmutil._client = _gemini_client
    llmutil._anthropic_client = _anthropic_client
    llmutil._extraction_anthropic_client = _anthropic_client


def uninstall():
    for name, original in _originals.items():
        setattr(llmutil, name, original)
    _originals.clear()


def _prompt_vocabulary() -> frozenset:
    texts = [
        value
        for name, value in vars(prompts).items()
        if name.isupper() and not name.startswith("_") and isinstance(value, str)
    ]
    texts.append(prompts.get_conversation_flow_prompt())
    return frozenset(_CAPITALIZED.findall("\n".join(texts)))


def coach_reply(statement: str) -> str:
    return f"Tell me more about that. You said: {statement.strip()}"


def _mid_sentence_names(text: str):
    """Capitalized words that are not the first word of their sentence, so
    ordinary sentence openers are not mistaken for people."""
    for sentence in _SENTENCE.split(text.strip()):
        opener = sentence.split(" ", 1)[0].strip(".,;:!?\"'")
        for word in _CAPITALIZED.findall(sentence):
            if word != opener:
                yield word


def new_names(prompt: str) -> list[str]:
    """Capitalized words from the conversation lines of a prompt that are not
    prompt boilerplate, not a speaker label, and not already committed."""
    known = set(_JSON_NAME.findall(prompt)) | _boilerplate | STOP_WORDS
    names = {}
    for speaker, text in _SPEAKER_LINE.findall(prompt):
        if speaker.isupper():
            continue
        known.add(speaker.strip())
        for word in _mid_sentence_names(text):
            names[word] = None
    return [name for name in names if name not in known]


def deltas_for(prompt: str) -> dict:
    people = [
        {"id": -(index + 1), "name": name}
        for index, name in enumerate(new_names(prompt))
    ]
    events = []
    if people:
        events.append(
            asdict(
                Event(
                    id=-(len(people) + 1),
                    kind=EventKind.Shift,
                    person=people[0]["id"],
                    description=f"Stub shift for {people[0]['name']}",
                    dateTime=STUB_EVENT_DATE,
                    dateCertainty=DateCertainty.Approximate,
                    anxiety=VariableShift.Up,
                )
            )
        )
    return {"people": people, "events": events, "pair_bonds": [], "delete": []}


def _is_pdp(schema: dict) -> bool:
    return {"people", "events", "pair_bonds"} <= set(schema.get("properties", {}))


def _minimal(schema: dict):
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        required = schema.get("required", [])
        return {
            key: _minimal(value)
            for key, value in schema.get("properties", {}).items()
            if key in required
        }
    if kind == "array":
        return []
    if kind == "integer":
        return 0
    if kind == "number":
        return 0.0
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    return ""


def structured_json(prompt: str, schema: dict) -> str:
    return json.dumps(deltas_for(prompt) if _is_pdp(schema) else _minimal(schema))


def _last_user_text(contents) -> str:
    if isinstance(contents, str):
        return contents
    for entry in reversed(contents):
        if getattr(entry, "role", "user") == "user":
            return "".join(part.text for part in entry.parts)
    return ""


class _Usage:
    input_tokens = 0
    output_tokens = 0


class _TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _Candidate:
    finish_reason = "STOP"


class _GeminiResponse:
    candidates = [_Candidate()]

    def __init__(self, text: str):
        self.text = text


class _GeminiModels:
    async def generate_content(self, model=None, contents=None, config=None):
        schema = getattr(config, "response_schema", None)
        if schema:
            return _GeminiResponse(structured_json(_last_user_text(contents), schema))
        return _GeminiResponse(coach_reply(_last_user_text(contents)))


class _GeminiAio:
    models = _GeminiModels()


class _GeminiClient:
    aio = _GeminiAio()


class _AnthropicMessage:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]
        self.usage = _Usage()
        self.stop_reason = "end_turn"


class _AnthropicStream:
    def __init__(self, message: _AnthropicMessage):
        self._message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get_final_message(self) -> _AnthropicMessage:
        return self._message


class _AnthropicMessages:
    async def create(self, **kwargs) -> _AnthropicMessage:
        return _AnthropicMessage(coach_reply(kwargs["messages"][-1]["content"]))

    def stream(self, **kwargs) -> _AnthropicStream:
        prompt = kwargs["messages"][-1]["content"]
        schema = json.loads(prompt.rsplit("\n\n", 1)[-1])
        return _AnthropicStream(_AnthropicMessage(structured_json(prompt, schema)))


class _AnthropicClient:
    messages = _AnthropicMessages()

    async def close(self):
        return None


def _gemini_client() -> _GeminiClient:
    return _GeminiClient()


def _anthropic_client() -> _AnthropicClient:
    return _AnthropicClient()
