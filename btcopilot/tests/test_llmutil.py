import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal

import pytest
from anthropic.types import Message, Usage
from anthropic.types.beta import BetaMessage, BetaUsage

from btcopilot import coachmodel, llmutil
from btcopilot.coachmodel import COACH_EFFORT, CoachModel, Spent
from btcopilot.pricing import cost, price
from btcopilot.provider import SETTING, Provider


def unset() -> dict:
    """What a fresh import chooses with no model named in the environment. Asked
    in a process of its own: reloading the module here would give its error
    and record classes a second identity for every test after it."""
    env = {k: v for k, v in os.environ.items() if k != "BTCOPILOT_RESPONSE_MODEL"}
    said = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from btcopilot import llmutil as u; print(json.dumps(["
            "u.RESPONSE_MODEL, u.resolve_model(u.DEFAULT_RESPONSE_MODEL_ALIAS), "
            "u.resolve_model(None)]))",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(
        zip(("model", "alias", "none"), json.loads(said.stdout.splitlines()[-1]))
    )


def test_the_conversation_runs_on_opus_5_5():
    # R-0405
    assert unset() == {
        "model": "claude-opus-5-5",
        "alias": "claude-opus-5-5",
        "none": "claude-opus-5-5",
    }


def test_opus_5_5_costs_less_than_the_opus_it_replaced():
    # R-0405
    now, before = price(unset()["model"]), price("claude-opus-5")
    assert now.input < before.input
    assert now.output < before.output


@pytest.fixture
def anthropic_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv(llmutil.LOCAL_URL, raising=False)
    monkeypatch.delenv(llmutil.LOCAL_MODEL, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    return monkeypatch


def test_a_local_url_sends_every_call_to_the_local_model(anthropic_env):
    # R-0507
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    client = llmutil._anthropic_client()
    assert str(client.base_url) == "http://127.0.0.1:11434"
    assert client.api_key != "anthropic-key"
    assert CoachModel().model == "qwen3:8b"
    assert CoachModel(model="opus-5.5").model == "qwen3:8b"
    assert llmutil.wire_model("claude-opus-5-5") == "qwen3:8b"


def test_without_a_local_url_calls_go_to_anthropic(anthropic_env):
    # R-0507
    client = llmutil._anthropic_client()
    assert str(client.base_url) == "https://api.anthropic.com"
    assert client.api_key == "anthropic-key"
    assert CoachModel().model == llmutil.RESPONSE_MODEL


def test_a_local_url_without_a_model_fails(anthropic_env):
    # R-0507
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    with pytest.raises(KeyError):
        CoachModel()


def test_the_local_model_costs_nothing(anthropic_env):
    # R-0507
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    assert cost("qwen3:8b", Spent(input=1000, output=1000)) == 0


@dataclass
class Named:
    name: str = ""


def test_a_local_url_sends_gemini_extraction_to_the_local_model(anthropic_env):
    # R-0507
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    anthropic_env.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    asked = []

    async def claude_structured(prompt, response_format, model, schema, limit):
        asked.append(model)

    anthropic_env.setattr(llmutil, "claude_structured", claude_structured)
    llmutil.gemini_structured_sync("prompt", Named)
    assert asked == [llmutil.EXTRACTION_MODEL]


def test_a_structured_call_goes_to_the_model_it_names(anthropic_env):
    # R-0856, R-0857
    asked = []

    async def claude_structured(prompt, response_format, model, schema, limit):
        asked.append(model)

    anthropic_env.setattr(llmutil, "claude_structured", claude_structured)
    llmutil.gemini_structured_sync("prompt", Named, model="claude-sonnet-5")
    assert asked == ["claude-sonnet-5"]


def test_a_local_url_sends_gemini_text_to_the_local_model(anthropic_env):
    # R-0507
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    anthropic_env.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    asked = []

    async def claude_text(prompt, **kwargs):
        asked.append(kwargs["model"])

    anthropic_env.setattr(llmutil, "claude_text", claude_text)
    llmutil.gemini_text_sync("Name this session", model=llmutil.EXTRACTION_MODEL)
    assert asked == [llmutil.EXTRACTION_MODEL]


class Stream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self.message


class Messages:
    def __init__(self, message):
        self.message = message

    def stream(self, **kwargs):
        return Stream(self.message)


class Client:
    def __init__(self):
        said = {
            "id": "msg_1",
            "role": "assistant",
            "model": "qwen3:8b",
            "content": [{"type": "text", "text": '{"name": "Harold"}'}],
            "stop_reason": "end_turn",
            "type": "message",
        }
        self.messages = Messages(
            Message(**said, usage=Usage(input_tokens=10, output_tokens=5))
        )
        self.beta = type("Beta", (), {})()
        self.beta.messages = Messages(
            BetaMessage(**said, usage=BetaUsage(input_tokens=10, output_tokens=5))
        )


def test_structured_calls_read_the_local_models_answer(anthropic_env):
    # R-0507
    anthropic_env.setattr(llmutil, "_extraction_anthropic_client", Client)
    parsed = asyncio.run(
        llmutil.claude_structured("prompt", Named, "qwen3:8b", {}, 100)
    )
    assert parsed.value == Named(name="Harold")


def test_sonnet_5_5_costs_what_sonnet_5_costs():
    # R-0405
    assert price("claude-sonnet-5-5") == price("claude-sonnet-5")


def test_gemini_3_1_pro_preview_has_its_own_price():
    # R-0405
    rate = price("gemini-3.1-pro-preview")
    assert (rate.input, rate.output, rate.cache_read) == (2, 12, Decimal("0.20"))


class Sent(Exception):
    """Stops a call once its request is seen."""


class Seen:
    """A client that keeps each request it is sent and answers none."""

    def __init__(self, sent: list, *args, **kwargs):
        self.sent = sent
        self.beta = self
        self.messages = self

    def stream(self, **kwargs):
        self.sent.append(kwargs)
        raise Sent

    async def create(self, **kwargs):
        self.sent.append(kwargs)
        raise Sent


class AsyncSeen(Seen):
    async def close(self):
        pass


class SyncSeen(Seen):
    def close(self):
        pass


SHAPE = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "kin": {"type": "array", "items": {"type": "object", "properties": {}}},
    },
}


def test_the_structured_call_sends_the_schema_as_the_output_format(anthropic_env):
    # R-0856, R-0857
    """Cluster detection, the structured call, sends its schema as Claude's
    structured output format, every object closed, and the prompt exactly as
    given, with no schema in it; Sonnet 5 keeps adaptive thinking at the
    structured effort, Haiku 4.5 sends no thinking setting."""
    anthropic_env.setenv(SETTING, Provider.Anthropic.value)
    sent: list[dict] = []
    anthropic_env.setattr(
        llmutil, "_extraction_anthropic_client", lambda: AsyncSeen(sent)
    )

    def structured(model: str) -> dict:
        with pytest.raises(Sent):
            asyncio.run(
                llmutil.claude_structured("the family", Named, model, SHAPE, 100)
            )
        return sent.pop()

    closed = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "kin": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }
    form = {"type": "json_schema", "schema": closed}
    sonnet = structured("claude-sonnet-5")
    assert sonnet["messages"] == [{"role": "user", "content": "the family"}]
    assert sonnet["thinking"] == {"type": "adaptive"}
    assert sonnet["output_config"] == {
        "effort": llmutil.STRUCTURED_EFFORT,
        "format": form,
    }
    haiku = structured("claude-haiku-4-5-20251001")
    assert haiku["messages"] == [{"role": "user", "content": "the family"}]
    assert "thinking" not in haiku
    assert haiku["output_config"] == {"format": form}
    assert not hasattr(llmutil, "CLAUDE_JSON_INSTRUCTION")


def test_an_answer_that_is_not_the_json_asked_for_is_unreadable(anthropic_env):
    # R-0856, R-0857
    """Only the returned JSON is loaded: a reply in prose is refused as
    unreadable, never searched for JSON."""

    class Prose(Client):
        def __init__(self):
            super().__init__()
            said = self.beta.messages.message
            text = said.content[0].model_copy(
                update={"text": 'Thinking it over: {"name": "Harold"}'}
            )
            self.beta.messages.message = said.model_copy(update={"content": [text]})

    anthropic_env.setattr(llmutil, "_extraction_anthropic_client", Prose)
    with pytest.raises(llmutil.Unreadable):
        asyncio.run(llmutil.claude_structured("prompt", Named, "qwen3:8b", {}, 100))


def test_the_coachs_turn_and_the_text_calls_are_unchanged(anthropic_env):
    # R-0856, R-0857
    """A text call on Sonnet 5 keeps adaptive thinking at the text effort and
    sends no output format, and the coach's turn on Sonnet 5 sends its own
    effort and no thinking setting, as before."""
    anthropic_env.setenv(SETTING, Provider.Anthropic.value)
    sent: list[dict] = []
    anthropic_env.setattr(llmutil, "_anthropic_client", lambda: AsyncSeen(sent))
    anthropic_env.setattr(
        coachmodel, "anthropic_client", lambda **options: SyncSeen(sent)
    )

    def thinking(request: dict) -> tuple:
        return request.get("thinking"), request.get("output_config")

    with pytest.raises(Sent):
        llmutil.claude_text_sync("prompt", model="claude-sonnet-5")
    assert thinking(sent.pop()) == (
        {"type": "adaptive"},
        {"effort": llmutil.TEXT_EFFORT},
    )
    with pytest.raises(Sent):
        list(
            CoachModel(model="sonnet-5").turn(
                "system", [{"role": "user", "content": "hello"}], []
            )
        )
    assert thinking(sent.pop()) == (None, {"effort": COACH_EFFORT})
    assert sent == []
