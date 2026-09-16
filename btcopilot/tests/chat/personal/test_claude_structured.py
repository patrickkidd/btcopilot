"""Tests for the Claude structured-extraction adapter in llmutil.py."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from btcopilot.llmutil import (
    gemini_structured,
    claude_structured,
    CLAUDE_STRUCTURED_USAGE,
    OutputTruncatedError,
)
from btcopilot.schema import PDPDeltas


def stream_client(text, stop_reason="end_turn", in_tokens=100, out_tokens=50):
    block = MagicMock(type="text", text=text)
    response = MagicMock(
        content=[block],
        stop_reason=stop_reason,
        usage=MagicMock(input_tokens=in_tokens, output_tokens=out_tokens),
    )
    stream = MagicMock()
    stream.get_final_message = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=stream)
    cm.__aexit__ = AsyncMock(return_value=False)
    client = MagicMock()
    client.messages.stream = MagicMock(return_value=cm)
    return client


@pytest.mark.asyncio
async def test_gemini_structured_dispatches_claude_models():
    with patch(
        "btcopilot.llmutil.claude_structured", new_callable=AsyncMock
    ) as structured:
        structured.return_value = PDPDeltas()
        result = await gemini_structured("prompt", PDPDeltas, model="claude-fable-5")
    structured.assert_awaited_once_with("prompt", PDPDeltas, "claude-fable-5")
    assert isinstance(result, PDPDeltas)


@pytest.mark.asyncio
async def test_claude_structured_parses_fenced_json_and_counts_usage():
    payload = {
        "people": [{"id": -1, "name": "Mary", "gender": "female"}],
        "events": [],
        "pair_bonds": [],
        "delete": [],
    }
    client = stream_client(f"```json\n{json.dumps(payload)}\n```")
    calls_before = CLAUDE_STRUCTURED_USAGE["calls"]
    with patch("btcopilot.llmutil._extraction_anthropic_client", return_value=client):
        result = await claude_structured("extract", PDPDeltas, "claude-fable-5")
    assert result.people[0].name == "Mary"
    assert CLAUDE_STRUCTURED_USAGE["calls"] == calls_before + 1
    prompt_sent = client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert '"type": "object"' in prompt_sent


@pytest.mark.asyncio
async def test_claude_structured_raises_on_truncation():
    client = stream_client('{"people": []}', stop_reason="max_tokens")
    with patch("btcopilot.llmutil._extraction_anthropic_client", return_value=client):
        with pytest.raises(OutputTruncatedError):
            await claude_structured("extract", PDPDeltas, "claude-fable-5")
