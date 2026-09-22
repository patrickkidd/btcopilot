"""The model behind the coach, with the one seam the tests replace.

`CoachModel.turn` makes one call and returns the words and the tool calls it
asked for. The agent loop owns the looping; this owns the wire.
"""

import logging
import os
from dataclasses import dataclass, field

import anthropic

from btcopilot.llmutil import RESPONSE_MODEL, resolve_model

_log = logging.getLogger(__name__)

MAX_TOKENS = 4096
TEMPERATURE = 0.45

# What the wire keeps between calls. One turn is several calls over the same
# coaching text, the same tools and a growing history, so everything up to a
# mark is sent once and read back cheaply by the calls after it. The API allows
# four marks; this path sets three.
CACHE = {"type": "ephemeral"}


def _marked(block: dict) -> dict:
    return dict(block, cache_control=CACHE)


def system_blocks(system: str | list[str]) -> list[dict]:
    """The system prompt as blocks, its head marked. One string has nothing
    stable to keep apart, so the whole of it is the head."""
    parts = [system] if isinstance(system, str) else [part for part in system if part]
    blocks = [{"type": "text", "text": part} for part in parts]
    return [_marked(blocks[0])] + blocks[1:]


def marked_tools(tools: list[dict]) -> list[dict]:
    """The tools with the last one marked, which keeps the whole list."""
    return tools[:-1] + [_marked(tools[-1])]


def marked_messages(messages: list[dict]) -> list[dict]:
    """The chat with its last block marked, so the next call in the same turn
    reads back everything this one sent."""
    last = messages[-1]
    content = last["content"]
    blocks = (
        [{"type": "text", "text": content}]
        if isinstance(content, str)
        else list(content)
    )
    blocks[-1] = _marked(blocks[-1])
    return messages[:-1] + [dict(last, content=blocks)]


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class Spent:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    def add(self, other: "Spent") -> None:
        self.input += other.input
        self.output += other.output
        self.cache_creation += other.cache_creation
        self.cache_read += other.cache_read


@dataclass
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    spent: Spent = field(default_factory=Spent)


class CoachModel:
    def __init__(self, model: str | None = None):
        self.model = resolve_model(model) if model else RESPONSE_MODEL

    def turn(
        self,
        system: str | list[str],
        messages: list[dict],
        tools: list[dict],
        turn_id: str = "",
    ):
        """One model call: yields the words as they arrive, returns the turn.

        No tools means the call cannot make one, which is how a turn is forced
        to end in words. A system prompt in two parts is the coaching text and
        then the record, so the wire keeps the first and re-reads the second.
        """
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_blocks(system),
                messages=marked_messages(messages),
                **({"tools": marked_tools(tools)} if tools else {}),
            ) as stream:
                yield from stream.text_stream
                message = stream.get_final_message()
        finally:
            client.close()

        # Echo back only the fields the API accepts: a whole block dump carries
        # SDK-side extras the next request rejects.
        turn = ModelTurn()
        for block in message.content:
            if block.type == "text":
                turn.text += block.text
                turn.blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                turn.calls.append(ToolCall(id=block.id, name=block.name, args=block.input))
                turn.blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        used = message.usage
        turn.spent = Spent(
            input=used.input_tokens,
            output=used.output_tokens,
            cache_creation=used.cache_creation_input_tokens or 0,
            cache_read=used.cache_read_input_tokens or 0,
        )
        _log.info(
            f"Coach model {self.model} turn {turn_id}: {len(turn.text)} chars, "
            f"{len(turn.calls)} tool calls, {used.input_tokens} tokens in, "
            f"{used.output_tokens} out, {used.cache_creation_input_tokens} kept, "
            f"{used.cache_read_input_tokens} read back"
        )
        return turn
