"""The coach on an OpenAI model, through the Responses API: the same turn as
`CoachModel.turn`, with the chat and the tools the agent loop builds for Claude
translated on the way out and the answer translated back. Nothing is stored at
OpenAI, so the model's reasoning comes back encrypted and is sent back with
the tool results."""

import enum
import json
import logging

from opentelemetry import trace

from btcopilot.llmutil import Served, openai_client, openai_spent
from btcopilot.modelturn import MAX_TOKENS, ModelTurn, Refusal, ToolCall

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

REASONING = "reasoning.encrypted_content"
FILTERED = "content_filter"


class Block(enum.StrEnum):
    Text = "text"
    ToolUse = "tool_use"
    ToolResult = "tool_result"
    Reasoning = "reasoning"


class Event(enum.StrEnum):
    Delta = "response.output_text.delta"
    Completed = "response.completed"
    Incomplete = "response.incomplete"
    Failed = "response.failed"
    Error = "error"


class Item(enum.StrEnum):
    Message = "message"
    FunctionCall = "function_call"
    Reasoning = "reasoning"


class Part(enum.StrEnum):
    Text = "output_text"
    Refusal = "refusal"


class OpenAIFailed(Exception):
    pass


def inputs(messages: list[dict]) -> list[dict]:
    items = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if isinstance(content, str):
            items.append({"role": role, "content": content})
            continue
        for block in content:
            kind = Block(block["type"])
            if kind is Block.Text:
                if block["text"]:
                    items.append({"role": role, "content": block["text"]})
            elif kind is Block.ToolUse:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": block["id"],
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    }
                )
            elif kind is Block.ToolResult:
                key = "error" if block.get("is_error") else "output"
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": block["tool_use_id"],
                        "output": json.dumps({key: block["content"]}),
                    }
                )
            else:
                items.append(
                    {
                        "type": "reasoning",
                        "id": block["id"],
                        "summary": [],
                        "encrypted_content": block["encrypted_content"],
                    }
                )
    return items


def functions(tools: list[dict]) -> list[dict]:
    """Not strict: strict mode would demand a change to every schema."""
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
            "strict": False,
        }
        for tool in tools
    ]


class OpenAIModel:
    def __init__(
        self, model: str, effort: str | None = None, timeout: float | None = None
    ):
        """The effort goes to OpenAI's reasoning effort as it is; one the model
        does not take is rejected by the API."""
        self.model = model
        self.effort = effort
        self.timeout = timeout

    def _args(self, system: str | list[str], messages: list[dict], tools: list[dict]):
        parts = [system] if isinstance(system, str) else [p for p in system if p]
        return dict(
            model=self.model,
            instructions="\n\n".join(parts),
            input=inputs(messages),
            max_output_tokens=MAX_TOKENS,
            store=False,
            include=[REASONING],
            stream=True,
            **({"tools": functions(tools)} if tools else {}),
            **({"reasoning": {"effort": self.effort}} if self.effort else {}),
        )

    def turn(
        self,
        system: str | list[str],
        messages: list[dict],
        tools: list[dict],
        turn_id: str = "",
    ):
        """One model call: yields the words as they arrive, returns the turn.
        No tools means the call cannot make one."""
        # Counts only: no prompt or message text, which is private health data.
        with _tracer.start_span(
            "coach.turn",
            attributes={"model": self.model, "turn_id": turn_id, "tools": len(tools)},
        ) as span:
            response = None
            with openai_client(self.timeout) as client:
                for event in client.responses.create(
                    **self._args(system, messages, tools)
                ):
                    kind = event.type
                    if kind == Event.Delta:
                        yield event.delta
                    elif kind in (Event.Completed, Event.Incomplete):
                        response = event.response
                    elif kind == Event.Failed:
                        raise OpenAIFailed(
                            f"Coach model {self.model} turn {turn_id} failed: "
                            f"{event.response.error}"
                        )
                    elif kind == Event.Error:
                        raise OpenAIFailed(
                            f"Coach model {self.model} turn {turn_id} error "
                            f"{event.code}: {event.message}"
                        )

            incomplete = response.incomplete_details
            if incomplete and incomplete.reason == FILTERED:
                raise Refusal(
                    f"Coach model {self.model} turn {turn_id} refused: {FILTERED}",
                    FILTERED,
                    Served(model=response.model),
                    openai_spent(response.usage),
                )

            turn = ModelTurn(
                served=Served(model=response.model),
                spent=openai_spent(response.usage),
            )
            for item in response.output:
                if item.type == Item.Reasoning:
                    turn.blocks.append(
                        {
                            "type": Block.Reasoning.value,
                            "id": item.id,
                            "encrypted_content": item.encrypted_content,
                        }
                    )
                elif item.type == Item.Message:
                    for part in item.content:
                        if part.type == Part.Refusal:
                            raise Refusal(
                                f"Coach model {self.model} turn {turn_id} "
                                f"refused: {part.refusal}",
                                None,
                                turn.served,
                                turn.spent,
                            )
                        turn.text += part.text
                        turn.blocks.append({"type": Block.Text.value, "text": part.text})
                elif item.type == Item.FunctionCall:
                    call = ToolCall(
                        id=item.call_id,
                        name=item.name,
                        args=json.loads(item.arguments),
                    )
                    turn.calls.append(call)
                    turn.blocks.append(
                        {
                            "type": Block.ToolUse.value,
                            "id": call.id,
                            "name": call.name,
                            "input": call.args,
                        }
                    )
            _log.info(
                f"Coach model {turn.served.model} turn {turn_id}: "
                f"{len(turn.text)} chars, {len(turn.calls)} tool calls, "
                f"{turn.spent.input} tokens in, {turn.spent.output} out, "
                f"{turn.spent.cache_creation} kept, {turn.spent.cache_read} read back"
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
