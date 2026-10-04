"""A call the provider answered and charged for writes its row in the
model-calls ledger even when the call then fails: a refusal, a cut-off answer,
an answer that is not the JSON asked for."""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from btcopilot import llmutil, pricing
from btcopilot.llmutil import OutputTruncatedError, Served, Spent, Unreadable
from btcopilot.metered import Metered
from btcopilot.modelturn import Refusal
from btcopilot.models.modelcall import ModelCall, Purpose

SPENT = Spent(input=1000, output=50, cache_creation=0, cache_read=200)


class Refuses:
    model = "claude-opus-5-5"

    def turn(self, system, messages, tools, turn_id=""):
        yield "Let me"
        raise Refusal("refused", "bio", Served(self.model), SPENT)


def rows() -> list[tuple]:
    return [
        (r.purpose, r.model, r.input_tokens, r.output_tokens, r.cache_read_tokens, r.cost_usd)
        for r in ModelCall.query.order_by(ModelCall.id)
    ]


def test_a_refused_turn_is_written_down_with_what_it_spent(discussion):
    # R-0628
    meter = Metered(
        discussion.user_id, discussion.diagram_id, "t1", Purpose.Coach, model=Refuses()
    )
    with pytest.raises(Refusal):
        list(meter.turn("system", [], []))
    assert rows() == [
        (
            Purpose.Coach,
            "claude-opus-5-5",
            1000,
            50,
            200,
            pricing.cost("claude-opus-5-5", SPENT),
        )
    ]


def test_an_unreadable_structured_answer_is_written_down(discussion, monkeypatch):
    # R-0628
    def unreadable(prompt, response_format):
        raise Unreadable("not JSON", Served("gemini-3.1-flash-lite"), SPENT)

    monkeypatch.setattr("btcopilot.metered.gemini_structured_sync", unreadable)
    meter = Metered(discussion.user_id, discussion.diagram_id, "t1", Purpose.Cluster)
    with pytest.raises(Unreadable):
        meter.structured("prompt", dict)
    assert [r[:4] for r in rows()] == [(Purpose.Cluster, "gemini-3.1-flash-lite", 1000, 50)]


@dataclass
class Named:
    name: str


def answer(text: str, finish: str):
    usage = SimpleNamespace(
        prompt_token_count=1200,
        cached_content_token_count=200,
        candidates_token_count=40,
        thoughts_token_count=10,
    )
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish)],
        usage_metadata=usage,
        model_version="gemini-3.1-flash-lite",
    )


@pytest.mark.parametrize(
    "text, finish, error",
    [
        ('{"name": "Ada"', "MAX_TOKENS", OutputTruncatedError),
        ("Here is the JSON you asked for", "STOP", Unreadable),
    ],
)
def test_a_failed_gemini_answer_carries_what_it_spent(monkeypatch, text, finish, error):
    # R-0628
    async def generate_content(**kwargs):
        return answer(text, finish)

    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(llmutil, "_client", lambda: client)
    monkeypatch.setattr(llmutil, "local_model", lambda: None)
    with pytest.raises(error) as failed:
        asyncio.run(llmutil.gemini_structured("prompt", Named, model="gemini-3.1-flash-lite"))
    assert failed.value.spent == Spent(input=1000, output=50, cache_read=200)
    assert failed.value.served.model == "gemini-3.1-flash-lite"
