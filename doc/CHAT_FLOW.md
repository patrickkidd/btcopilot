# Chat Flow Architecture

This document describes the chat flow architecture for the btcopilot personal app, starting with `btcopilot.personal.ask` and including test fixtures that mock various parts of the flow.

## Overview

The chat flow implements a coaching-style conversation system that extracts family relationship data (PDP - Pending Data Pool) from user messages and generates contextually appropriate AI responses based on Bowen Family Systems Theory.

## Flow Entry Points

### HTTP Routes

#### POST /personal/discussions/ (Create Discussion)
[btcopilot/btcopilot/personal/routes/discussions.py:73-88](btcopilot/btcopilot/personal/routes/discussions.py#L73-L88)

Creates a new discussion and optionally processes an initial statement.
- Creates initial diagram with User (ID 1) and Assistant (ID 2) people if user has no free_diagram
- Creates discussion with Subject (User) and Expert (Assistant) speakers
- If statement provided, calls `ask()` and returns both discussion and response

#### POST /personal/discussions/{id}/statements (Chat)
[btcopilot/btcopilot/personal/routes/discussions.py:112-200](btcopilot/btcopilot/personal/routes/discussions.py#L112-L200)

Processes a new user statement in existing discussion.
- Calls `ask()` to generate response
- Returns AI response and PDP deltas
- (Commented out SSE notification code for audit system)

### Core Chat Function

#### btcopilot.personal.ask()
[btcopilot/btcopilot/personal/chat.py:58-189](btcopilot/btcopilot/personal/chat.py#L58-L189)

Main orchestration function that:
1. Extracts PDP deltas from user message
2. Determines conversation direction (Lead vs Follow)
3. Generates AI response based on direction
4. Creates Statement records for both user and AI

**Key Dependencies:**
- `pdp.update()` - Async extraction of family data from user message
- `detect_response_direction()` - Async determination of conversation mode
- `_generate_response()` - Synchronous LLM call for AI response
- `gather()` - Async utility to run parallel operations

## Data Flow

### 1. PDP (Pending Data Pool) Update Flow

**Entry:** [btcopilot/pdp.py:183-245](btcopilot/btcopilot/pdp.py#L183-L245)

```
User Message → pdp.update()
              ├→ Compiles system prompt with:
              │  ├→ PDP_ROLE_AND_INSTRUCTIONS
              │  ├→ PDP_EXAMPLES
              │  ├→ Existing DiagramData (DO NOT RE-EXTRACT)
              │  ├→ Conversation history (context only)
              │  └→ New user statement (ANALYZE FOR DELTAS)
              ├→ Calls LLM with PDPDeltas response format
              ├→ Returns (new_pdp, pdp_deltas)
              └→ Applies deltas via apply_deltas()
```

**PDP Delta Extraction Rules:**
- Extract ONLY new information or changes from current statement
- Most responses return sparse/empty arrays
- Entries have negative IDs (< 0) and confidence < 1.0
- Positive IDs reference committed database entries

**Validation:** [btcopilot/pdp.py:37-157](btcopilot/btcopilot/pdp.py#L37-L157)
- Ensures no ID collisions between people/events/pair_bonds
- Validates all references to negative IDs exist in PDP
- Validates all PDP items have negative IDs
- Raises PDPValidationError on failures

**Application:** [btcopilot/pdp.py:248-357](btcopilot/btcopilot/pdp.py#L248-L357)
- Deep copies PDP
- Upserts people, events, pair_bonds
- Processes deletes
- Maintains referential integrity

### 2. Response Direction Detection

**Entry:** [btcopilot/btcopilot/personal/chat.py:34-55](btcopilot/btcopilot/personal/chat.py#L34-L55)

```
User Message + Conversation History → detect_response_direction()
                                     ↓
                              LLM determines:
                              ├→ "lead" - Guide data collection per Bowen stack
                              └→ "follow" - Stay curious about user's topic
```

### 3. Response Generation

**Entry:** [btcopilot/btcopilot/personal/chat.py:192-200](btcopilot/btcopilot/personal/chat.py#L192-L200)

Different meta-prompts based on direction:

**Lead Mode** (lines 117-141):
- Work backward from symptom/problem
- Follow Bowen Theory stack for data collection:
  1. Clarify/define problem
  2. Course of problem over time
  3. Notable points of better/worse
  4. Life/relationship context around notable points
  5. Family system information (who, ages, relationships)

**Follow Mode** (lines 145-170):
- Be curious about what user just said
- Less about data collection, more about discussion
- Avoid canned therapist responses
- Focus on correlating four main variables (anxiety, relationship, symptom, functioning)

**Custom Prompts for Testing:**
Uses Flask `g.custom_prompts` if available to override:
- ROLE_COACH_NOT_THERAPIST
- BOWEN_THEORY_COACHING_IN_A_NUTSHELL
- DATA_MODEL_DEFINITIONS

### 4. Async Execution

**Parallel Operations:** [btcopilot/btcopilot/async_utils.py:16-18](btcopilot/btcopilot/async_utils.py#L16-L18)

```python
results = gather(
    pdp.update(discussion, diagram_data, user_statement),
    detect_response_direction(user_statement, discussion),
)
```

Uses asyncio event loop to run both operations concurrently.

### 5. LLM Integration

**Entry:** [btcopilot/btcopilot/extensions/llm.py](btcopilot/btcopilot/extensions/llm.py)

**LLMFunction Enum:**
- `Direction` - Determine lead vs follow
- `JSON` - Structured PDP delta extraction
- `Respond` - Generate human-like responses
- `Summarize` - Generate summaries

**Current Model:** `gpt-4o-mini` (OpenAI)

**Async Methods:**
- `llm.submit()` - Async LLM calls with optional response_format
- `llm.submit_one()` - Synchronous wrapper for async submit

**Response Format:**
- PDPDeltas uses pydantic-ai Agent with structured output
- Temperature 0.45 for responses (controlled randomness)

### 6. Database Persistence

**Statement Creation:**
```
User Statement → Statement(speaker=chat_user_speaker, pdp_deltas=dict)
AI Response   → Statement(speaker=chat_ai_speaker)
```

**Diagram Updates:**
```
diagram_data.pdp = new_pdp
discussion.diagram.set_diagram_data(diagram_data)
```

## Test Fixtures

### chat_flow Fixture

**Location:** [btcopilot/btcopilot/tests/personal/conftest.py:20-62](btcopilot/btcopilot/tests/personal/conftest.py#L20-L62)

**Purpose:** Mock the entire intelligence flow for deterministic testing

**Usage:**
```python
@pytest.mark.chat_flow(
    response="That's too bad",
    pdp={"people": [...], "events": [...], "pair_bonds": [...]},
    response_direction=ResponseDirection.Follow
)
def test_ask(test_user):
    # Test runs with mocked LLM responses
```

**What It Mocks:**
1. `btcopilot.pdp.update` - Returns pre-defined PDP deltas
2. `btcopilot.personal.chat.detect_response_direction` - Returns preset direction
3. `btcopilot.personal.chat._generate_response` - Returns preset response string

**Benefits:**
- No actual LLM calls (fast, deterministic)
- Test business logic without external dependencies
- Control exact PDP output for edge cases
- Verify correct handling of different response directions

### Other Fixtures

**discussion:** [btcopilot/btcopilot/tests/personal/conftest.py:75-113](btcopilot/btcopilot/tests/personal/conftest.py#L75-L113)
- Creates discussion with speakers and statements
- Pre-populated with test conversation history

**discussions:** [btcopilot/btcopilot/tests/personal/conftest.py:65-71](btcopilot/btcopilot/tests/personal/conftest.py#L65-L71)
- Creates multiple empty discussions for testing list operations

## Key Data Models

### PDP (Pending Data Pool)
Contains unconfirmed family data with:
- `people: list[Person]` - Negative IDs, confidence < 1.0
- `events: list[Event]` - Negative IDs, track variable shifts
- `pair_bonds: list[PairBond]` - Negative IDs, represent couples

### PDPDeltas
Delta changes to apply:
- `people: list[Person]` - New or updated people
- `events: list[Event]` - New or updated events
- `pair_bonds: list[PairBond]` - New or updated pair bonds
- `delete: list[int]` - IDs to remove

### Person
- `id: int` - Negative for PDP, positive for committed
- `name: str`
- `parents: int | None` - Reference to PairBond ID
- `confidence: float` - 0.0-0.9 for PDP, 1.0 for committed

### Event
- `id: int` - Negative for PDP, positive for committed
- `kind: EventKind` - shift, married, birth, death, etc.
- `person: int` - Primary person ID
- `dateTime: str | None` - ISO format or partial date
- `description: str`
- Variable fields:
  - `symptom: "up" | "down" | "same"`
  - `anxiety: "up" | "down" | "same"`
  - `functioning: "up" | "down" | "same"`
  - `relationship: RelationshipKind` - distance, conflict, overfunctioning, etc.
- `relationshipTargets: list[int]` - People involved in relationship shifts
- `relationshipTriangles: list[int]` - People in triangle positions
- `child: int | None` - For projection mechanism
- `confidence: float`

### PairBond
- `id: int` - Negative for PDP, positive for committed
- `person_a: int` - First person in relationship
- `person_b: int | None` - Second person (can be null for single parent)
- `confidence: float`

### Response
- `statement: str` - AI-generated response text
- `pdp: PDP | None` - Updated PDP state

## Prompt Engineering Strategy

### System Prompts Location
[btcopilot/btcopilot/personal/prompts.py](btcopilot/btcopilot/personal/prompts.py)

### Key Prompts

**ROLE_COACH_NOT_THERAPIST:**
- Emphasizes consultant role, not therapist
- Focus on information gathering over emotional support
- Avoid "feeling words," prefer objective/measurable terms
- One question at a time
- Place events in time

**BOWEN_THEORY_COACHING_IN_A_NUTSHELL:**
Five-step data collection stack:
1. Define problem (symptom or life challenge)
2. Course of problem over time
3. Notable better/worse periods
4. Life/relationship context at those points
5. Family system structure and triangles

**DATA_MODEL_DEFINITIONS:**
Defines Person, Event, Variables (symptom, anxiety, functioning, relationship) with:
- Anxiety binding mechanisms (distance, conflict, over/underfunctioning, projection)
- Triangle moves (inside, outside positions)

**PDP_ROLE_AND_INSTRUCTIONS:**
Critical instructions for delta extraction:
- Extract ONLY NEW information (not re-extract existing data)
- SPARSE output (often empty arrays)
- Negative IDs for PDP entries
- Confidence levels 0.0-0.9
- Single events per statement (avoid duplicates)

**PDP_EXAMPLES:**
Provides few-shot learning examples showing:
- Sparse delta extraction (brother-in-law already exists)
- Complex multi-person updates with triangles
- Anxiety/functioning shifts
- Deletion handling

## Improving System Prompts for LLM Alignment

When Claude Code makes changes to improve system prompts based on developer requests, follow these guidelines:

### 1. Understand Current Behavior First
- Read this CHAT_FLOW.md to understand the full architecture
- Check [btcopilot/btcopilot/personal/prompts.py](btcopilot/btcopilot/personal/prompts.py) for current prompts
- Review recent AI responses in ai_log.txt (if available)
- Look at test cases to understand expected behavior

### 2. Identify Which Prompt to Modify

**For Response Quality Issues:**
- Modify `ROLE_COACH_NOT_THERAPIST` (tone, style, approach)
- Modify `BOWEN_THEORY_COACHING_IN_A_NUTSHELL` (conversation flow, data collection)

**For Data Extraction Issues:**
- Modify `PDP_ROLE_AND_INSTRUCTIONS` (extraction rules)
- Add/modify examples in `PDP_EXAMPLES` (few-shot learning)
- Modify `DATA_MODEL_DEFINITIONS` (data model understanding)

**For Direction Detection Issues:**
- Modify direction_prompt in [btcopilot/btcopilot/personal/chat.py:39-50](btcopilot/btcopilot/personal/chat.py#L39-L50)

### 3. Testing Strategy

**Unit Tests with Mocks:**
Use `@pytest.mark.chat_flow()` to test changes without LLM calls:
```python
@pytest.mark.chat_flow(
    pdp={"people": [...]},  # Expected extraction
    response="Expected response",
    response_direction=ResponseDirection.Lead
)
def test_new_behavior(test_user):
    # Test logic changes
```

**E2E Tests:**
Mark tests with `@pytest.mark.e2e` to test actual LLM responses:
```python
@pytest.mark.e2e
def test_ask_e2e(test_user):
    # Makes real LLM calls
    response = ask(discussion, "User message")
    # Assert on response quality
```

**Manual Testing with Flask `g.custom_prompts`:**
Override prompts temporarily for testing:
```python
from flask import g
g.custom_prompts = {
    "ROLE_COACH_NOT_THERAPIST": "Modified prompt...",
}
```

### 4. Common Alignment Issues

**Issue: LLM re-extracts existing data**
- Strengthen emphasis in PDP_ROLE_AND_INSTRUCTIONS
- Add negative examples to PDP_EXAMPLES showing what NOT to extract
- Increase prominence of "DO NOT RE-EXTRACT" warning

**Issue: Too verbose or therapist-like responses**
- Emphasize brevity in ROLE_COACH_NOT_THERAPIST
- Add examples of good vs bad responses
- Adjust temperature in _generate_response() (currently 0.45)

**Issue: Missing data from user messages**
- Add few-shot examples for specific data patterns
- Review DATA_MODEL_DEFINITIONS for clarity
- Check if validation is too strict in validate_pdp_deltas()

**Issue: Wrong response direction**
- Improve direction_prompt clarity
- Add examples of lead vs follow scenarios
- Consider adding conversation context to direction detection

### 5. Iterative Refinement Process

1. Make small, targeted changes to one prompt at a time
2. Test with existing test suite (both mocked and e2e)
3. Review ai_log.txt for actual LLM behavior
4. Adjust based on failure patterns
5. Update PDP_EXAMPLES if adding new capabilities
6. Document behavior changes in commit messages

### 6. Monitoring LLM Behavior

**Development Mode Logging:**
When `FLASK_CONFIG=development`, detailed logs in ai_log.txt show:
- User statements
- Response direction
- PDP deltas extracted
- AI responses

**Review logs for:**
- Unwanted re-extraction patterns
- Tone/style consistency
- Data model understanding
- Edge case handling

## Common Development Patterns

### Adding New Variable Types
1. Update EventKind or RelationshipKind enums
2. Modify DATA_MODEL_DEFINITIONS in prompts.py
3. Add examples to PDP_EXAMPLES
4. Update validation in pdp.py if needed
5. Add test cases

### Changing Response Style
1. Modify ROLE_COACH_NOT_THERAPIST
2. Add style guidance to meta_prompt in ask()
3. Test with e2e tests
4. Adjust temperature if needed

### Improving Data Extraction
1. Add examples to PDP_EXAMPLES (most effective)
2. Clarify rules in PDP_ROLE_AND_INSTRUCTIONS
3. Update DATA_MODEL_DEFINITIONS if model unclear
4. Consider adding validation to catch bad extractions early

## Architecture Weaknesses to Consider

1. **No retry logic** - If LLM fails, request fails (could add retry with exponential backoff)
2. **No validation on AI responses** - Text responses not checked for quality
3. **Single LLM model** - No fallback if OpenAI unavailable
4. **Synchronous direction detection** - Could be optimized
5. **No streaming** - All responses generated before returning
6. **Temperature hardcoded** - Could be configurable per conversation context
7. **No conversation summarization** - Full history sent every time (token cost grows)

## Related Files

- [btcopilot/btcopilot/personal/chat.py](btcopilot/btcopilot/personal/chat.py) - Main chat orchestration
- [btcopilot/btcopilot/personal/routes/discussions.py](btcopilot/btcopilot/personal/routes/discussions.py) - HTTP routes
- [btcopilot/btcopilot/personal/prompts.py](btcopilot/btcopilot/personal/prompts.py) - System prompts
- [btcopilot/btcopilot/pdp.py](btcopilot/btcopilot/pdp.py) - PDP update/validation
- [btcopilot/btcopilot/extensions/llm.py](btcopilot/btcopilot/extensions/llm.py) - LLM client
- [btcopilot/btcopilot/async_utils.py](btcopilot/btcopilot/async_utils.py) - Async utilities
- [btcopilot/btcopilot/tests/personal/conftest.py](btcopilot/btcopilot/tests/personal/conftest.py) - Test fixtures
- [btcopilot/btcopilot/tests/personal/test_ask.py](btcopilot/btcopilot/tests/personal/test_ask.py) - Chat flow tests
