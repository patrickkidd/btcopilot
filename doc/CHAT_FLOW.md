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
2. Calls LLM with `CONVERSATION_FLOW_PROMPT`
3. Creates Statement records for both user and AI
4. Returns AI response text

Uses Flask `g.custom_prompts` to override `CONVERSATION_FLOW_PROMPT` if set.

## Prompt Engineering

### Chat Prompts

`CONVERSATION_FLOW_PROMPT` in `btcopilot/personal/prompts.py` (overridden by
fdserver in production) drives the coaching conversation. Key elements:
- Consultant role, not therapist
- Bowen Theory data collection stack
- One question at a time, place events in time
- Temperature 0.45

### Extraction Prompts

Extraction prompts are separate from chat prompts. See
[PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md) for extraction prompt rules.

### Modifying Prompts

**For chat quality**: Modify `CONVERSATION_FLOW_PROMPT`.
**For extraction quality**: Modify `DATA_FULL_EXTRACTION_CONTEXT` and related
constants. See [PROMPT_ENGINEERING_LOG.md](PROMPT_ENGINEERING_LOG.md).

Real prompts are in fdserver (production overrides btcopilot defaults).

## Related Files

- [btcopilot/btcopilot/personal/chat.py](btcopilot/btcopilot/personal/chat.py) - Chat-only orchestration
- [btcopilot/btcopilot/personal/routes/discussions.py](btcopilot/btcopilot/personal/routes/discussions.py) - HTTP routes (chat + extract)
- [btcopilot/btcopilot/personal/prompts.py](btcopilot/btcopilot/personal/prompts.py) - Default prompt constants
- [btcopilot/btcopilot/pdp.py](btcopilot/btcopilot/pdp.py) - `extract_full()`, validation
- [btcopilot/btcopilot/tests/personal/conftest.py](btcopilot/btcopilot/tests/personal/conftest.py) - Test fixtures
- [btcopilot/btcopilot/tests/personal/test_ask.py](btcopilot/btcopilot/tests/personal/test_ask.py) - Chat flow tests
