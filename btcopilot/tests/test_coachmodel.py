import pytest

from btcopilot import llmutil
from btcopilot.coachmodel import COACH_EFFORT, model_for
from btcopilot.tests.test_llmutil import anthropic_env


def test_no_name_is_the_default_model(anthropic_env):
    # R-0647
    model = model_for()
    assert model.model == llmutil.RESPONSE_MODEL
    assert model.effort == COACH_EFFORT


def test_an_alias_names_its_model(anthropic_env):
    # R-0647
    assert model_for("sonnet-5").model == "claude-sonnet-5"


def test_an_unknown_name_raises(anthropic_env):
    # R-0647
    with pytest.raises(KeyError):
        model_for("sonet-5")


def test_haiku_gets_no_effort(anthropic_env):
    # R-0647
    model = model_for("haiku-4.5")
    assert model.model == "claude-haiku-4-5-20251001"
    assert model.effort is None


def test_a_local_url_runs_every_name_on_the_local_model(anthropic_env):
    # R-0647
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    assert model_for("sonnet-5").model == "qwen3:8b"
