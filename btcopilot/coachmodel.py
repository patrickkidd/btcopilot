"""The model behind the coach, with the one seam the tests replace.

`CoachModel.turn` makes one call and returns the words and the tool calls it
asked for. The agent loop owns the looping; this owns the wire.
"""

import logging

from opentelemetry import trace

from btcopilot.geminimodel import GeminiModel
from btcopilot.openaimodel import OpenAIModel
from btcopilot.llmutil import (
    anthropic_client,
    claude_spent,
    fallback_args,
    NotOnBedrockError,
    off_bedrock,
    is_gemini,
    is_openai,
    local_model,
    resolve_model,
    served,
    wire_model,
)
from btcopilot.modelturn import MAX_TOKENS, ModelTurn, Refusal, Spent, ToolCall

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

# How hard the coach thinks before it speaks. Medium keeps the first word quick.
COACH_EFFORT = "low"
HAIKU = "claude-haiku-4-5"

# What the wire keeps between calls. The wire reads tools, then the system
# prompt, then the chat, and keeps everything up to a mark, so the mark on the
# coaching text keeps the tools too. The record and the day go after the chat,
# the chat is marked where it has settled, and a turn's later calls and the
# next turn read all of that back. The API allows four marks.
CACHE = {"type": "ephemeral"}


def _marked(block: dict) -> dict:
    return dict(block, cache_control=CACHE)


def system_blocks(system: str | list[str]) -> list[dict]:
    """The system prompt as blocks, its head marked. One string has nothing
    stable to keep apart, so the whole of it is the head."""
    parts = [system] if isinstance(system, str) else [part for part in system if part]
    blocks = [{"type": "text", "text": part} for part in parts]
    return [_marked(blocks[0])] + blocks[1:]


def _mark_last(message: dict) -> dict:
    content = message["content"]
    blocks = (
        [{"type": "text", "text": content}]
        if isinstance(content, str)
        else list(content)
    )
    blocks[-1] = _marked(blocks[-1])
    return dict(message, content=blocks)


def marked_ends(messages: list[dict], ends: list[int]) -> list[dict]:
    """The chat with the last block of each of its first `ends` messages
    marked: where it has settled, so a later turn reads it back."""
    marked = list(messages)
    for end in ends:
        if end:
            marked[end - 1] = _mark_last(marked[end - 1])
    return marked


def marked_messages(messages: list[dict]) -> list[dict]:
    """The chat with its last block marked, so the next call in the same turn
    reads back everything this one sent."""
    return messages[:-1] + [_mark_last(messages[-1])]


class CoachModel:
    def __init__(
        self,
        model: str | None = None,
        effort: str | None = COACH_EFFORT,
        timeout: float | None = None,
    ):
        """No effort is for a model that rejects the setting (Haiku 4.5). No
        timeout is the client's own default."""
        self.model = wire_model(resolve_model(model))
        self.effort = effort
        self.timeout = timeout

    def turn(
        self,
        system: str | list[str],
        messages: list[dict],
        tools: list[dict],
        turn_id: str = "",
    ):
        """One model call: yields the words as they arrive, returns the turn.

        No tools means the call cannot make one, which is how a turn is forced
        to end in words. A system prompt in parts keeps only the first.
        """
        # Counts only: no prompt or message text, which is private health data.
        with _tracer.start_span(
            "coach.turn",
            attributes={"model": self.model, "turn_id": turn_id, "tools": len(tools)},
        ) as span:
            client = anthropic_client(
                **({"timeout": self.timeout} if self.timeout else {})
            )
            try:
                with client.beta.messages.stream(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=system_blocks(system),
                    messages=marked_messages(messages),
                    **({"tools": tools} if tools else {}),
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
                    answered,
                    claude_spent(message.usage),
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
            turn.spent = claude_spent(used)
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


def model_for(
    name: str | None = None,
    effort: str | None = COACH_EFFORT,
    timeout: float | None = None,
) -> CoachModel | GeminiModel | OpenAIModel:
    """The coach model an alias names: none is the default, an unknown one
    raises KeyError. Haiku 4.5 rejects the effort setting, so it gets none. The
    local server answers every name, Gemini's and OpenAI's included. Bedrock
    has no Gemini or OpenAI, so such a coach there raises NotOnBedrockError."""
    model = resolve_model(name)
    if off_bedrock(model):
        raise NotOnBedrockError(
            f"Model {name} is not on Bedrock; unset BTCOPILOT_MODEL_PROVIDER"
            " or choose a Claude model"
        )
    if is_gemini(model) and not local_model():
        return GeminiModel(model, effort, timeout)
    if is_openai(model) and not local_model():
        return OpenAIModel(model, effort, timeout)
    if model.startswith(HAIKU):
        effort = None
    return CoachModel(name, effort, timeout)
