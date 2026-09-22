"""What one coach call puts on the wire, and what it keeps there.

A turn is several calls over the same coaching text, the same tools and a
growing chat, so each call marks what the next one may read back instead of
paying for it again.
"""

import logging

import pytest
from mock import patch

from btcopilot.personal import prompts
from btcopilot.personal.coachmodel import CACHE, CoachModel

TOOLS = [
    {"name": "first", "description": "one", "input_schema": {"type": "object"}},
    {"name": "last", "description": "two", "input_schema": {"type": "object"}},
]


class Usage:
    input_tokens = 120
    output_tokens = 30
    cache_creation_input_tokens = 4100
    cache_read_input_tokens = 8200


class Reply:
    content = []
    usage = Usage()


class Wire:
    """Anthropic's client with the call recorded instead of made."""

    def __init__(self, **_):
        self.sent = {}

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
        return Reply()

    def close(self):
        pass


@pytest.fixture
def wire(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")
    sent = Wire()
    with patch("btcopilot.personal.coachmodel.anthropic.Anthropic", lambda **k: sent):
        yield sent


def call(wire, system, messages, tools=TOOLS, turn_id="abc123"):
    words = CoachModel(model="claude-opus-4-6").turn(system, messages, tools, turn_id)
    while True:
        try:
            next(words)
        except StopIteration:
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
