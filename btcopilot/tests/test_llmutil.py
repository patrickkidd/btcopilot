import importlib

import pytest

from btcopilot import llmutil
from btcopilot.pricing import price


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
