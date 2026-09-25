"""The model behind the coach, with the one seam the tests replace.

`CoachModel.turn` makes one call and returns the words and the tool calls it
asked for. The agent loop owns the looping; this owns the wire.
"""

import logging
from dataclasses import dataclass, field

import anthropic
from opentelemetry import trace

from btcopilot.llmutil import (
    RESPONSE_MODEL,
    Served,
    anthropic_args,
    fallback_args,
    resolve_model,
    served,
    wire_model,
)

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

# Thinking counts toward the cap even though its text is not returned.
MAX_TOKENS = 16000
# How hard the coach thinks before it speaks. Medium keeps the first word quick.
COACH_EFFORT = "medium"

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
    served: Served | None = None


class Refusal(Exception):
    """Every model in the fallback chain declined the call on safety grounds.
    The turn fails with the category it named rather than ending in silence."""

    def __init__(self, message: str, category: str | None):
        super().__init__(message)
        self.category = category


class CoachModel:
    def __init__(self, model: str | None = None, effort: str | None = COACH_EFFORT):
        """No effort is for a model that rejects the setting (Haiku 4.5)."""
        self.model = wire_model(resolve_model(model) if model else RESPONSE_MODEL)
        self.effort = effort

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
        # Counts only: no prompt or message text, which is private health data.
        with _tracer.start_span(
            "coach.turn",
            attributes={"model": self.model, "turn_id": turn_id, "tools": len(tools)},
        ) as span:
            client = anthropic.Anthropic(**anthropic_args())
            try:
                with client.beta.messages.stream(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=system_blocks(system),
                    messages=marked_messages(messages),
                    **({"tools": marked_tools(tools)} if tools else {}),
                    **(
                        {"output_config": {"effort": self.effort}}
                        if self.effort
                        else {}
                    ),
                    **fallback_args(self.model),
                ) as stream:
                    yield from stream.text_stream
                    message = stream.get_final_message()
            finally:
                client.close()

            answered = served(message, f"Coach turn {turn_id}")
            if message.stop_reason == "refusal":
                category = (
                    message.stop_details.category if message.stop_details else None
                )
                raise Refusal(
                    f"Coach model {answered.model} turn {turn_id} refused, "
                    f"with every fallback: {category}",
                    category,
                )

            # Echo back only the fields the API accepts: a whole block dump carries
            # SDK-side extras the next request rejects. Thinking goes back
            # unchanged, or the next call in a tool loop fails. A model that was
            # cut off mid-answer leaves only its words: its thinking and tool
            # calls before the last hop were never finished and are not run.
            turn = ModelTurn(served=answered)
            hops = [i for i, b in enumerate(message.content) if b.type == "fallback"]
            boundary = hops[-1] if hops else -1
            for index, block in enumerate(message.content):
                if index < boundary and block.type != "text":
                    continue
                if block.type == "thinking":
                    turn.blocks.append(
                        {
                            "type": "thinking",
                            "thinking": block.thinking,
                            "signature": block.signature,
                        }
                    )
                elif block.type == "redacted_thinking":
                    turn.blocks.append(
                        {"type": "redacted_thinking", "data": block.data}
                    )
                elif block.type == "text":
                    turn.text += block.text
                    turn.blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    turn.calls.append(
                        ToolCall(id=block.id, name=block.name, args=block.input)
                    )
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
                f"Coach model {answered.model} turn {turn_id}: {len(turn.text)} chars, "
                f"{len(turn.calls)} tool calls, {used.input_tokens} tokens in, "
                f"{used.output_tokens} out, {used.cache_creation_input_tokens} kept, "
                f"{used.cache_read_input_tokens} read back"
            )
            span.set_attributes(
                {
                    "tool_calls": len(turn.calls),
                    "tokens.input": turn.spent.input,
                    "tokens.output": turn.spent.output,
                    "tokens.cache_creation": turn.spent.cache_creation,
                    "tokens.cache_read": turn.spent.cache_read,
                }
            )
            return turn
