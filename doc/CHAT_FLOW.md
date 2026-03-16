# Chat Flow Architecture

Chat flow for the Personal app. Chat is **chat-only** — no PDP extraction
during conversation. Extraction is a separate endpoint-driven operation (see
[PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md)).

## Overview

The chat flow implements a coaching-style conversation using Bowen Family
Systems Theory. The AI coach collects family system data through conversation.
Extraction of structured data (people, events, pair bonds) happens separately
via `POST /personal/discussions/<id>/extract`.

## Flow Entry Points

### HTTP Routes

#### POST /personal/discussions/ (Create Discussion)

Creates a new discussion and optionally processes an initial statement.
- Creates initial diagram with User (ID 1) and Assistant (ID 2) people if user has no free_diagram
- Creates discussion with Subject (User) and Expert (Assistant) speakers
- If statement provided, calls `ask()` and returns both discussion and response

#### POST /personal/discussions/{id}/statements (Chat)

Processes a new user statement in existing discussion.
- Calls `ask()` to generate response
- Returns AI response text (no PDP deltas)

#### POST /personal/discussions/{id}/extract (Extraction)

Endpoint-driven single-prompt extraction. See [PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md).

### Core Chat Function

#### btcopilot.personal.chat.ask()

Chat-only function:
1. Builds conversation turns from discussion history
2. Calls LLM with assembled prompt from `get_conversation_flow_prompt(model)`
3. Creates Statement records for both user and AI
4. Returns AI response text

Uses Flask `g.custom_prompts` to override the assembled prompt if set.

## Model Configuration

The chat response model is configurable via the `BTCOPILOT_RESPONSE_MODEL`
environment variable. This enables A/B testing between models.

| Model | Env Value | Use Case |
|-------|-----------|----------|
| Claude Opus 4.6 | `claude-opus-4-6` (default) | Chat responses — superior conversational quality |
| Gemini Flash | `gemini-3-flash-preview` | Legacy / fallback |

**Tiered model strategy:**
- **Chat/responses:** Claude Opus 4.6 (configurable) — via `response_text_sync()` in llmutil.py
- **Extraction:** Gemini Flash (hardcoded — optimized prompts, structured output)
- **Calibration:** Gemini Flash (hardcoded)
- **RAG:** Gemini Flash (hardcoded)

The backend (Anthropic vs Google) is auto-detected from the model name prefix.
Set `ANTHROPIC_API_KEY` in the environment when using Claude models.

All code that generates user-facing text responses should use `response_text_sync()`
(not `gemini_text_sync()` directly) to respect the configured model.

## Prompt Architecture

### Multi-Model Conversation Prompts

The conversation flow prompt is assembled by a callable override:

| Component | Location | Purpose |
|-----------|----------|---------|
| `get_conversation_flow_prompt(model)` stub | `btcopilot/personal/prompts.py` | Returns minimal default; overridden by fdserver |
| `get_conversation_flow_prompt(model)` impl | `fdserver/prompts/private_prompts.py` | Full assembly: core + model-specific addendum |

fdserver internally maintains `_CONVERSATION_FLOW_CORE`, `_CONVERSATION_FLOW_OPUS`,
and `_CONVERSATION_FLOW_GEMINI` as module-level strings, but these are not exported.
The callable has full control over per-model assembly.

**Why per-model addenda**: Opus and Gemini have opposite natural tendencies.
Gemini tends verbose (needs brevity constraints). Opus tends terse (needs
encouragement to produce 2-4 sentence responses with conversational texture).
Shared constraints that work for one model harm the other.

### Override Mechanism

btcopilot's `prompts.py` defines stub callables and constants. fdserver's
`private_prompts.py` provides production implementations via the
`FDSERVER_PROMPTS_PATH` override loop.

- **Conversation flow**: callable override (`get_conversation_flow_prompt`)
- **Other prompts** (extraction, SARF, etc.): constant overrides (legacy mechanism)

**Tuned prompt content is production IP in fdserver.** btcopilot contains
only architectural stubs.

### Modifying Prompts

**For conversation prompts**: Edit `get_conversation_flow_prompt()` in
fdserver's `private_prompts.py`. Full per-model control — Opus and Gemini
can have entirely different prompt structures.
**For extraction quality**: See [PROMPT_ENGINEERING_LOG.md](PROMPT_ENGINEERING_LOG.md).

### Extraction Prompts

Extraction prompts are separate from chat prompts. See
[PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md) for extraction prompt rules.

## Related Files

- [btcopilot/btcopilot/personal/chat.py](btcopilot/btcopilot/personal/chat.py) - Chat-only orchestration
- [btcopilot/btcopilot/personal/routes/discussions.py](btcopilot/btcopilot/personal/routes/discussions.py) - HTTP routes (chat + extract)
- [btcopilot/btcopilot/personal/prompts.py](btcopilot/btcopilot/personal/prompts.py) - Default prompt constants
- [btcopilot/btcopilot/pdp.py](btcopilot/btcopilot/pdp.py) - `extract_full()`, validation
- [btcopilot/btcopilot/tests/personal/conftest.py](btcopilot/btcopilot/tests/personal/conftest.py) - Test fixtures
- [btcopilot/btcopilot/tests/personal/test_ask.py](btcopilot/btcopilot/tests/personal/test_ask.py) - Chat flow tests
