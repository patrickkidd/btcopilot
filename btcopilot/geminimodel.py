"""The coach on a Gemini model: the same turn as `CoachModel.turn`, with the
chat and the tools the agent loop builds for Claude translated on the way out
and the answer translated back."""

import base64
import enum
import logging
import uuid

from google.genai import types
from opentelemetry import trace

from btcopilot.llmutil import Served, gemini_client, gemini_spent
from btcopilot.modelturn import MAX_TOKENS, ModelTurn, Refusal, ToolCall

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

ROLES = {"user": "user", "assistant": "model"}
REFUSED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}
# Gemini 3 rejects a call from the current turn sent back without the
# signature it came with. A call it did not make, such as a past turn's call
# rebuilt from the record or one Claude made, carries this one instead.
UNSIGNED = b"skip_thought_signature_validator"


class Block(enum.StrEnum):
    Text = "text"
    ToolUse = "tool_use"
    ToolResult = "tool_result"


def contents(messages: list[dict]) -> list[types.Content]:
    names = {}
    said = []
    for message in messages:
        content = message["content"]
        blocks = (
            [{"type": Block.Text, "text": content}]
            if isinstance(content, str)
            else content
        )
        unsigned = not any(block.get("signature") for block in blocks)
        parts = []
        for block in blocks:
            kind = Block(block["type"])
            if kind is Block.Text:
                if block["text"]:
                    parts.append(types.Part(text=block["text"]))
            elif kind is Block.ToolUse:
                names[block["id"]] = block["name"]
                signature = block.get("signature")
                if signature:
                    signature = base64.b64decode(signature)
                elif unsigned:
                    signature, unsigned = UNSIGNED, False
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            name=block["name"], args=block["input"]
                        ),
                        thought_signature=signature,
                    )
                )
            else:
                key = "error" if block.get("is_error") else "output"
                parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=names[block["tool_use_id"]],
                            response={key: block["content"]},
                        )
                    )
                )
        said.append(types.Content(role=ROLES[message["role"]], parts=parts))
    return said


def declarations(tools: list[dict]) -> list[types.Tool]:
    if not tools:
        return []
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters_json_schema=tool["input_schema"],
                )
                for tool in tools
            ]
        )
    ]


def _parts(chunk: types.GenerateContentResponse) -> list[types.Part]:
    """A chunk that only closes the stream carries no content."""
    if not chunk.candidates or not chunk.candidates[0].content:
        return []
    return chunk.candidates[0].content.parts or []


class GeminiModel:
    def __init__(
        self, model: str, effort: str | None = None, timeout: float | None = None
    ):
        self.model = model
        self.effort = effort
        self.timeout = timeout

    def _config(self, system: str | list[str], tools: list[dict]):
        parts = [system] if isinstance(system, str) else [p for p in system if p]
        thinking = (
            types.ThinkingConfig(
                thinking_level=types.ThinkingLevel[self.effort.upper()]
            )
            if self.effort
            else None
        )
        return types.GenerateContentConfig(
            system_instruction="\n\n".join(parts),
            max_output_tokens=MAX_TOKENS,
            tools=declarations(tools),
            thinking_config=thinking,
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
            text = ""
            calls = []
            with gemini_client(self.timeout) as client:
                for chunk in client.models.generate_content_stream(
                    model=self.model,
                    contents=contents(messages),
                    config=self._config(system, tools),
                ):
                    last = chunk
                    for part in _parts(chunk):
                        if part.function_call:
                            calls.append(part)
                        elif part.text and not part.thought:
                            text += part.text
                            yield part.text

            blocked = last.prompt_feedback and last.prompt_feedback.block_reason
            finish = last.candidates[0].finish_reason if last.candidates else None
            if blocked or finish in REFUSED:
                category = (blocked or finish).value.lower()
                raise Refusal(
                    f"Coach model {self.model} turn {turn_id} refused: {category}",
                    category,
                )

            turn = ModelTurn(
                text=text,
                served=Served(model=last.model_version),
                spent=gemini_spent(last.usage_metadata),
            )
            if text:
                turn.blocks.append({"type": Block.Text.value, "text": text})
            for part in calls:
                call = ToolCall(
                    id=f"gemini_{uuid.uuid4().hex[:12]}",
                    name=part.function_call.name,
                    args=dict(part.function_call.args or {}),
                )
                turn.calls.append(call)
                block = {
                    "type": Block.ToolUse.value,
                    "id": call.id,
                    "name": call.name,
                    "input": call.args,
                }
                if part.thought_signature:
                    block["signature"] = base64.b64encode(
                        part.thought_signature
                    ).decode()
                turn.blocks.append(block)
            _log.info(
                f"Coach model {turn.served.model} turn {turn_id}: {len(text)} chars, "
                f"{len(calls)} tool calls, {turn.spent.input} tokens in, "
                f"{turn.spent.output} out, {turn.spent.cache_read} read back"
            )
            span.set_attributes(
                {
                    "tool_calls": len(turn.calls),
                    "tokens.input": turn.spent.input,
                    "tokens.output": turn.spent.output,
                    "tokens.cache_read": turn.spent.cache_read,
                }
            )
            return turn
