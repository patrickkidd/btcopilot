import json
import os
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal

import pytest

from btcopilot import llmutil
from btcopilot.coachmodel import CoachModel, Spent
from btcopilot.pricing import cost, price


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
    return dict(zip(("model", "alias", "none"), json.loads(said.stdout.splitlines()[-1])))


def test_the_conversation_runs_on_opus_5_5():
    # R-0405
    assert unset() == {"model": "claude-opus-5-5", "alias": "claude-opus-5-5", "none": "claude-opus-5-5"}


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

    async def claude_structured(prompt, response_format, model):
        asked.append(model)

    anthropic_env.setattr(llmutil, "claude_structured", claude_structured)
    llmutil.gemini_structured_sync("prompt", Named)
    assert asked == [llmutil.EXTRACTION_MODEL]


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


def test_sonnet_5_5_costs_what_sonnet_5_costs():
    # R-0405
    assert price("claude-sonnet-5-5") == price("claude-sonnet-5")


def test_gemini_pro_is_3_1_pro_preview_with_its_own_price():
    # R-0405
    model = llmutil.resolve_model("gemini-pro")
    assert model == "gemini-3.1-pro-preview"
    assert llmutil.is_gemini(model)
    rate = price(model)
    assert (rate.input, rate.output, rate.cache_read) == (2, 12, Decimal("0.20"))
