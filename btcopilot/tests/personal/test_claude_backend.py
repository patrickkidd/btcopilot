"""Tests for the Claude/Anthropic chat backend and unified routing in llmutil.py."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from btcopilot.llmutil import (
    claude_text,
    claude_text_sync,
    response_text_sync,
    _is_claude_model,
    _prepare_claude_messages,
)


# --- Model detection ---


def test_is_claude_model_positive():
    assert _is_claude_model("claude-opus-4-0-20250514")
    assert _is_claude_model("claude-sonnet-4-20250514")
    assert _is_claude_model("claude-3-opus-20240229")


def test_is_claude_model_negative():
    assert not _is_claude_model("gemini-3-flash-preview")
    assert not _is_claude_model("gpt-4o")
    assert not _is_claude_model("mistral-large-latest")


# --- Message preparation helper ---


def test_prepare_messages_from_turns():
    messages = _prepare_claude_messages(turns=[("user", "Hi"), ("model", "Hello")])
    assert messages == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]


def test_prepare_messages_from_prompt():
    messages = _prepare_claude_messages(prompt="What is 2+2?")
    assert messages == [{"role": "user", "content": "What is 2+2?"}]


def test_prepare_messages_prepends_user_if_starts_with_assistant():
    messages = _prepare_claude_messages(turns=[("model", "Welcome!"), ("user", "Thanks")])
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"


def test_prepare_messages_merges_consecutive_same_role():
    messages = _prepare_claude_messages(
        turns=[("user", "First"), ("user", "Second"), ("model", "Reply")]
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "First" in messages[0]["content"]
    assert "Second" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"


def test_prepare_messages_no_args_raises():
    with pytest.raises(ValueError, match="Requires either"):
        _prepare_claude_messages()


# --- Claude text API ---


def _make_mock_response(text="Hello there"):
    """Create a mock Anthropic API response with thinking + text blocks."""
    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.thinking = "internal reasoning"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response = MagicMock()
    response.content = [thinking_block, text_block]
    return response


@pytest.mark.asyncio
async def test_claude_text_with_turns():
    """Verify turns are mapped correctly and API is called."""
    mock_response = _make_mock_response("AI response")
    mock_create = AsyncMock(return_value=mock_response)

    with patch("btcopilot.llmutil._anthropic_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_fn.return_value = mock_client

        result = await claude_text(
            system_instruction="You are a coach.",
            turns=[("user", "Hi"), ("model", "Hello"), ("user", "How are you?")],
            temperature=0.45,
        )

    assert result == "AI response"
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["system"] == "You are a coach."
    messages = call_kwargs["messages"]
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"


@pytest.mark.asyncio
async def test_claude_text_with_simple_prompt():
    mock_response = _make_mock_response("Simple response")
    mock_create = AsyncMock(return_value=mock_response)

    with patch("btcopilot.llmutil._anthropic_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_fn.return_value = mock_client

        result = await claude_text(prompt="What is 2+2?")

    assert result == "Simple response"
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["messages"] == [{"role": "user", "content": "What is 2+2?"}]
    assert "system" not in call_kwargs


def test_claude_text_sync():
    mock_response = _make_mock_response("Sync response")
    mock_create = AsyncMock(return_value=mock_response)

    with patch("btcopilot.llmutil._anthropic_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_fn.return_value = mock_client

        result = claude_text_sync(prompt="Hello")

    assert result == "Sync response"


# --- Unified routing ---


def test_response_text_sync_routes_to_claude():
    """response_text_sync routes to Claude when RESPONSE_MODEL starts with claude-."""
    with patch("btcopilot.llmutil.RESPONSE_MODEL", "claude-opus-4-0-20250514"), \
         patch("btcopilot.llmutil._is_claude_model", return_value=True), \
         patch("btcopilot.llmutil.claude_text", new_callable=AsyncMock, return_value="Claude reply") as mock_claude, \
         patch("btcopilot.llmutil.gemini_text", new_callable=AsyncMock) as mock_gemini:
        result = response_text_sync(prompt="Hello")
        assert result == "Claude reply"
        mock_claude.assert_called_once()
        mock_gemini.assert_not_called()


def test_response_text_sync_routes_to_gemini():
    """response_text_sync routes to Gemini when RESPONSE_MODEL is not Claude."""
    with patch("btcopilot.llmutil.RESPONSE_MODEL", "gemini-3-flash-preview"), \
         patch("btcopilot.llmutil._is_claude_model", return_value=False), \
         patch("btcopilot.llmutil.gemini_text", new_callable=AsyncMock, return_value="Gemini reply") as mock_gemini, \
         patch("btcopilot.llmutil.claude_text", new_callable=AsyncMock) as mock_claude:
        result = response_text_sync(prompt="Hello")
        assert result == "Gemini reply"
        mock_gemini.assert_called_once()
        mock_claude.assert_not_called()


# --- Integration: chat.py and discussion.py use unified routing ---


@pytest.mark.chat_flow(response="Claude says hello")
def test_chat_flow_mock_still_works(test_user):
    """Existing chat_flow mock works regardless of backend (mocks _generate_response)."""
    from btcopilot.extensions import db
    from btcopilot.personal import ask
    from btcopilot.personal.models import Discussion

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    response = ask(discussion, "Hi")
    assert response.statement == "Claude says hello"


def test_chat_generate_response_uses_response_text_sync():
    """_generate_response in chat.py uses the unified response_text_sync."""
    with patch("btcopilot.personal.chat.response_text_sync", return_value="Routed reply") as mock:
        from btcopilot.personal.chat import _generate_response
        result = _generate_response("system prompt", [("user", "Hello")])
        assert result == "Routed reply"
        mock.assert_called_once_with(
            system_instruction="system prompt",
            turns=[("user", "Hello")],
            temperature=0.45,
        )


def test_discussion_update_summary_uses_response_text_sync():
    """Discussion.update_summary uses the unified response_text_sync."""
    with patch("btcopilot.personal.models.discussion.response_text_sync", return_value="  Summary text  ") as mock:
        from btcopilot.personal.models.discussion import Discussion
        d = MagicMock(spec=Discussion)
        d.conversation_history.return_value = "User: Hello\nExpert: Hi"
        # Call the unbound method with the mock instance
        Discussion.update_summary(d)
        mock.assert_called_once()
        assert d.summary == "  Summary text  "
