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


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)


class CoachModel:
    def __init__(self, model: str | None = None):
        self.model = resolve_model(model) if model else RESPONSE_MODEL

    def turn(self, system: str, messages: list[dict], tools: list[dict]):
        """One model call: yields the words as they arrive, returns the turn.

        No tools means the call cannot make one, which is how a turn is forced
        to end in words.
        """
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages,
                **({"tools": tools} if tools else {}),
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
        _log.info(
            f"Coach model {self.model}: {len(turn.text)} chars, "
            f"{len(turn.calls)} tool calls"
        )
        return turn
