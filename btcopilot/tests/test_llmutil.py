import importlib

import pytest

from btcopilot import llmutil
from btcopilot.coachmodel import CoachModel, Spent
from btcopilot.pricing import cost, price


@pytest.fixture
def unset(monkeypatch):
    monkeypatch.delenv("BTCOPILOT_RESPONSE_MODEL", raising=False)
    yield importlib.reload(llmutil)
    monkeypatch.undo()
    importlib.reload(llmutil)


def test_the_conversation_runs_on_opus_5_5(unset):
    # R-0405
    assert unset.RESPONSE_MODEL == "claude-opus-5-5"
    assert unset.resolve_model(unset.DEFAULT_RESPONSE_MODEL_ALIAS) == "claude-opus-5-5"
    assert unset.resolve_model(None) == "claude-opus-5-5"


def test_opus_5_5_costs_less_than_the_opus_it_replaced(unset):
    # R-0405
    now, before = price(unset.RESPONSE_MODEL), price("claude-opus-5")
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
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    client = llmutil._anthropic_client()
    assert str(client.base_url) == "http://127.0.0.1:11434"
    assert client.api_key != "anthropic-key"
    assert CoachModel().model == "qwen3:8b"
    assert CoachModel(model="opus-5.5").model == "qwen3:8b"
    assert llmutil.wire_model("claude-opus-5-5") == "qwen3:8b"


def test_without_a_local_url_calls_go_to_anthropic(anthropic_env):
    client = llmutil._anthropic_client()
    assert str(client.base_url) == "https://api.anthropic.com"
    assert client.api_key == "anthropic-key"
    assert CoachModel().model == llmutil.RESPONSE_MODEL


def test_a_local_url_without_a_model_fails(anthropic_env):
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    with pytest.raises(KeyError):
        CoachModel()


def test_the_local_model_costs_nothing(anthropic_env):
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    assert cost("qwen3:8b", Spent(input=1000, output=1000)) == 0
