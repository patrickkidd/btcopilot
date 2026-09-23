"""What one coach call puts on the wire, and what it keeps there.

A turn is several calls over the same coaching text, the same tools and a
growing chat, so each call marks what the next one may read back instead of
paying for it again.
"""

import logging
from decimal import Decimal

import pytest
from mock import patch

from btcopilot.llmutil import FALLBACK_BETA
from btcopilot.personal import prompts
from btcopilot.personal.coachmodel import (
    CACHE,
    COACH_EFFORT,
    CoachModel,
    Refusal,
    Spent,
)
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import ModelCall
from btcopilot.personal.pricing import cost

TOOLS = [
    {"name": "first", "description": "one", "input_schema": {"type": "object"}},
    {"name": "last", "description": "two", "input_schema": {"type": "object"}},
]


class Usage:
    input_tokens = 120
    output_tokens = 30
    cache_creation_input_tokens = 4100
    cache_read_input_tokens = 8200

    def __init__(self, iterations=None):
        self.iterations = iterations


class Block:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class Reply:
    def __init__(
        self,
        content=(),
        stop_reason="end_turn",
        stop_details=None,
        model="claude-opus-5-5",
        iterations=None,
    ):
        self.content = list(content)
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.model = model
        self.usage = Usage(iterations)


class Wire:
    """Anthropic's client with the call recorded instead of made."""

    def __init__(self, **_):
        self.sent = {}
        self.reply = Reply()

    def messages_stream(self, **kwargs):
        self.sent = dict(kwargs)
        return self

    @property
    def beta(self):
        messages = type("M", (), {"stream": self.messages_stream})()
        return type("B", (), {"messages": messages})()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return iter(["hello"])

    def get_final_message(self):
        return self.reply

    def close(self):
        pass


@pytest.fixture
def wire(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")
    sent = Wire()
    with patch("btcopilot.personal.coachmodel.anthropic.Anthropic", lambda **k: sent):
        yield sent


def run(model, system, messages, tools=TOOLS, turn_id="abc123"):
    words = model.turn(system, messages, tools, turn_id)
    while True:
        try:
            next(words)
        except StopIteration as stop:
            return stop.value


def call(wire, system, messages, tools=TOOLS, turn_id="abc123"):
    run(CoachModel(model="claude-opus-5-5"), system, messages, tools, turn_id)
    return wire.sent


def marks(sent: dict) -> int:
    blocks = list(sent["system"]) + list(sent.get("tools", []))
    for message in sent["messages"]:
        content = message["content"]
        blocks += content if isinstance(content, list) else []
    return len([block for block in blocks if block.get("cache_control")])


def test_the_coaching_text_goes_over_as_its_own_block_and_is_kept(wire):
    # R-0392
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert [block["text"] for block in sent["system"]] == ["COACHING", "RECORD"]
    assert sent["system"][0]["cache_control"] == CACHE
    assert "cache_control" not in sent["system"][1]


def test_the_last_tool_is_marked_so_the_whole_list_is_kept(wire):
    # R-0392
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert "cache_control" not in sent["tools"][0]
    assert sent["tools"][-1]["cache_control"] == CACHE


def test_the_end_of_the_chat_is_marked_so_the_next_call_reads_it_back(wire):
    # R-0392
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": [{"type": "text", "text": "said"}]},
        {"role": "user", "content": [{"type": "text", "text": "then this"}]},
    ]
    sent = call(wire, ["COACHING", "RECORD"], messages)
    assert sent["messages"][-1]["content"][-1]["cache_control"] == CACHE
    assert "cache_control" not in sent["messages"][-2]["content"][-1]
    assert messages[-1]["content"][-1] == {"type": "text", "text": "then this"}


def test_a_message_of_plain_words_becomes_a_block_so_it_can_be_marked(wire):
    # R-0392
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert sent["messages"][-1]["content"] == [
        {"type": "text", "text": "hi", "cache_control": CACHE}
    ]


def test_no_more_than_four_places_are_ever_marked(wire):
    # R-0392
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert marks(sent) == 3
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}], [])
    assert marks(sent) == 2


def test_what_the_call_cost_and_what_it_read_back_is_logged(wire, caplog):
    # no ruling
    with caplog.at_level(logging.INFO, logger="btcopilot.personal.coachmodel"):
        call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    logged = caplog.text
    assert "abc123" in logged
    assert "120 tokens in" in logged
    assert "30 out" in logged
    assert "4100 kept" in logged
    assert "8200 read back" in logged


def test_the_two_halves_of_the_coach_prompt_are_the_whole_prompt():
    # R-0392
    fixed, tail = prompts.agent_prompt(record="Marcus, 40", interactions="looked at 3")
    assert fixed + tail == prompts.get_agent_prompt(
        record="Marcus, 40", interactions="looked at 3"
    )
    assert "Marcus, 40" not in fixed
    assert "looked at 3" not in fixed
    assert fixed == prompts.agent_prompt(record="Someone else, 12")[0]


def test_the_coach_asks_for_its_effort_and_no_sampling(wire):
    # no ruling
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert sent["output_config"] == {"effort": COACH_EFFORT}
    assert "temperature" not in sent


def test_a_model_without_effort_sends_none(wire):
    # no ruling
    model = CoachModel(model="haiku-4.5", effort=None)
    run(model, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert "output_config" not in wire.sent


def test_thinking_goes_back_unchanged_before_the_tool_call(wire):
    # no ruling
    wire.reply = Reply(
        [
            Block(type="thinking", thinking="", signature="sig", extra="sdk"),
            Block(type="redacted_thinking", data="opaque"),
            Block(type="tool_use", id="t1", name="first", input={}),
        ],
        stop_reason="tool_use",
    )
    turn = run(
        CoachModel(), ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}]
    )
    assert turn.blocks[:2] == [
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "redacted_thinking", "data": "opaque"},
    ]
    assert [call.id for call in turn.calls] == ["t1"]


def test_a_refusal_fails_the_turn_with_its_category(wire):
    # R-0410
    wire.reply = Reply(stop_reason="refusal", stop_details=Block(category="bio"))
    with pytest.raises(Refusal, match="bio"):
        run(CoachModel(), ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])


def test_the_coach_asks_for_the_fallbacks(wire):
    # R-0410, R-0409
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert sent["betas"] == [FALLBACK_BETA]
    assert sent["extra_body"] == {
        "fallbacks": [{"model": "claude-opus-5"}, {"model": "claude-opus-4-8"}]
    }


def test_a_model_that_takes_no_fallbacks_is_sent_none(wire):
    # no ruling
    run(
        CoachModel(model="haiku-4.5", effort=None),
        ["COACHING", "RECORD"],
        [{"role": "user", "content": "hi"}],
    )
    assert "betas" not in wire.sent
    assert "extra_body" not in wire.sent


FELL = dict(
    content=[
        Block(
            type="fallback",
            to={"model": "claude-opus-5"},
            **{"from": {"model": "claude-opus-5-5"}},
        ),
        Block(type="text", text="Tell me more about that."),
    ],
    model="claude-opus-5",
    iterations=[
        Block(type="message", model="claude-opus-5-5", stop_details={"category": "bio"}),
        Block(type="fallback_message", model="claude-opus-5"),
    ],
)


def test_a_refused_call_answered_by_a_fallback_is_priced_and_logged_as_its(
    wire, discussion, caplog, monkeypatch
):
    # R-0409, R-0410
    monkeypatch.setattr(
        "btcopilot.personal.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )
    wire.reply = Reply(**FELL)
    reply = CoachTurn(discussion, "hi", model=CoachModel()).run()
    assert reply["statement"] == "Tell me more about that."

    row = ModelCall.query.one()
    assert row.model == "claude-opus-5"
    assert row.fallback == {
        "hops": [{"from": "claude-opus-5-5", "to": "claude-opus-5", "category": "bio"}],
        "sticky": False,
    }
    spent = Spent(input=120, output=30, cache_creation=4100, cache_read=8200)
    assert row.cost_usd == cost("claude-opus-5", spent).quantize(Decimal("0.000001"))
    assert row.cost_usd != cost("claude-opus-5-5", spent).quantize(Decimal("0.000001"))
    hop = [r for r in caplog.records if "took over" in r.message]
    assert len(hop) == 1
    assert "claude-opus-5-5 refused (bio), claude-opus-5 took over" in hop[0].message


def test_a_turn_served_by_an_earlier_fallback_is_marked_sticky(wire):
    # R-0410
    wire.reply = Reply(
        [Block(type="text", text="Go on.")],
        model="claude-opus-5",
        iterations=[Block(type="fallback_message", model="claude-opus-5")],
    )
    turn = run(CoachModel(), ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert turn.served.model == "claude-opus-5"
    assert turn.served.hops == []
    assert turn.served.fallback == {"hops": [], "sticky": True}


def test_a_model_cut_off_mid_answer_leaves_no_tool_call_to_run(wire):
    # no ruling
    wire.reply = Reply(
        [
            Block(type="text", text="Let me "),
            Block(type="tool_use", id="t0", name="first", input={}),
            *FELL["content"],
        ],
        model="claude-opus-5",
        iterations=FELL["iterations"],
    )
    turn = run(CoachModel(), ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert turn.calls == []
    assert [b["type"] for b in turn.blocks] == ["text", "text"]

