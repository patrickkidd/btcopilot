"""What one coach call puts on the wire, and what it keeps there.

A turn is several calls over the same coaching text, the same tools and a
growing chat, so each call marks what the next one may read back instead of
paying for it again.
"""

import logging

import pytest
from mock import patch

from btcopilot.personal import prompts
from btcopilot.personal.coachmodel import CACHE, COACH_EFFORT, CoachModel, Refusal

TOOLS = [
    {"name": "first", "description": "one", "input_schema": {"type": "object"}},
    {"name": "last", "description": "two", "input_schema": {"type": "object"}},
]


class Usage:
    input_tokens = 120
    output_tokens = 30
    cache_creation_input_tokens = 4100
    cache_read_input_tokens = 8200


class Block:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class Reply:
    def __init__(self, content=(), stop_reason="end_turn", stop_details=None):
        self.content = list(content)
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.usage = Usage()


class Wire:
    """Anthropic's client with the call recorded instead of made."""

    def __init__(self, **_):
        self.sent = {}
        self.reply = Reply()

    def messages_stream(self, **kwargs):
        self.sent = dict(kwargs)
        return self

    @property
    def messages(self):
        return type("M", (), {"stream": self.messages_stream})()

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
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert [block["text"] for block in sent["system"]] == ["COACHING", "RECORD"]
    assert sent["system"][0]["cache_control"] == CACHE
    assert "cache_control" not in sent["system"][1]


def test_the_last_tool_is_marked_so_the_whole_list_is_kept(wire):
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert "cache_control" not in sent["tools"][0]
    assert sent["tools"][-1]["cache_control"] == CACHE


def test_the_end_of_the_chat_is_marked_so_the_next_call_reads_it_back(wire):
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
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert sent["messages"][-1]["content"] == [
        {"type": "text", "text": "hi", "cache_control": CACHE}
    ]


def test_no_more_than_four_places_are_ever_marked(wire):
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert marks(sent) == 3
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}], [])
    assert marks(sent) == 2


def test_what_the_call_cost_and_what_it_read_back_is_logged(wire, caplog):
    with caplog.at_level(logging.INFO, logger="btcopilot.personal.coachmodel"):
        call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    logged = caplog.text
    assert "abc123" in logged
    assert "120 tokens in" in logged
    assert "30 out" in logged
    assert "4100 kept" in logged
    assert "8200 read back" in logged


def test_the_two_halves_of_the_coach_prompt_are_the_whole_prompt():
    fixed, tail = prompts.agent_prompt(record="Marcus, 40", interactions="looked at 3")
    assert fixed + tail == prompts.get_agent_prompt(
        record="Marcus, 40", interactions="looked at 3"
    )
    assert "Marcus, 40" not in fixed
    assert "looked at 3" not in fixed
    assert fixed == prompts.agent_prompt(record="Someone else, 12")[0]


def test_the_coach_asks_for_its_effort_and_no_sampling(wire):
    sent = call(wire, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert sent["output_config"] == {"effort": COACH_EFFORT}
    assert "temperature" not in sent


def test_a_model_without_effort_sends_none(wire):
    model = CoachModel(model="haiku-4.5", effort=None)
    run(model, ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
    assert "output_config" not in wire.sent


def test_thinking_goes_back_unchanged_before_the_tool_call(wire):
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
    wire.reply = Reply(stop_reason="refusal", stop_details=Block(category="bio"))
    with pytest.raises(Refusal, match="bio"):
        run(CoachModel(), ["COACHING", "RECORD"], [{"role": "user", "content": "hi"}])
