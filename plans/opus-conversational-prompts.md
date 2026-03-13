# Opus-Specific Conversational Prompt Tuning

## Problem Statement

After switching from Gemini 3 Flash Preview to Claude Opus 4.6 for conversational responses, the output has degraded to terse, single-line questions. Gemini naturally produced more varied, conversational output with some warmth and flow. The current `CONVERSATION_FLOW_PROMPT` was tuned for Gemini and doesn't leverage Opus's strengths or account for its behavioral tendencies.

**Goal**: Create a model-specific prompt layer so each model gets tuning that plays to its strengths, while sharing the core domain instructions.

---

## Analysis: Why Opus Produces Terse Output

The current prompt heavily emphasizes brevity and constraint:
- "Keep responses brief" (line 28)
- "One question per turn" (line 28)
- "Do NOT parrot back what the user just said" (line 249)
- Long list of "AVOID" patterns (therapy clichés)
- "RED FLAG" warnings about giving advice

Gemini Flash naturally adds conversational texture despite these constraints — it tends toward verbosity, so the constraints act as useful guardrails. **Opus is the opposite**: it's already concise and instruction-following by nature. Telling an already-terse model to "keep responses brief" produces one-liners.

Additionally, extended thinking is enabled (4096 token budget), which forces `temperature=1.0` per the Anthropic API — but the actual output is still constrained by the prompt's tone. The thinking budget may be "eating" creative energy that would otherwise go into the response.

---

## Architecture: Model-Specific Prompt System

### Design

Split the conversational prompt into:
1. **Core prompt** (shared): Domain knowledge, conversation phases, data checklist, red flags — the "what to do"
2. **Model-specific addendum** (per-model): Tone, style, response texture — the "how to do it"

```
CONVERSATION_FLOW_PROMPT_CORE = "..." # Shared domain instructions
CONVERSATION_FLOW_PROMPT_OPUS = "..." # Opus-specific style guide
CONVERSATION_FLOW_PROMPT_GEMINI = "..." # Gemini-specific style guide (current behavior preserved)
```

At runtime in `chat.py`, assemble the final prompt based on the active `RESPONSE_MODEL`:

```python
def _get_conversation_prompt():
    if _is_claude_model(RESPONSE_MODEL):
        return CONVERSATION_FLOW_PROMPT_CORE + "\n\n" + CONVERSATION_FLOW_PROMPT_OPUS
    else:
        return CONVERSATION_FLOW_PROMPT_CORE + "\n\n" + CONVERSATION_FLOW_PROMPT_GEMINI
```

The private prompts override mechanism stays intact — production can override the assembled prompt entirely via `g.custom_prompts`.

### Files Changed

| File | Change |
|------|--------|
| `btcopilot/personal/prompts.py` | Split `CONVERSATION_FLOW_PROMPT` into core + model addenda |
| `btcopilot/personal/chat.py` | Import model-aware prompt assembly, use it in `ask()` |
| `btcopilot/llmutil.py` | Export `_is_claude_model` and `RESPONSE_MODEL` (already available) |

---

## Opus-Specific Prompt Addendum: Design

### Key Differences from Gemini Tuning

| Aspect | Gemini Behavior (natural) | Opus Behavior (natural) | Opus Addendum Goal |
|--------|---------------------------|------------------------|---------------------|
| Length | Tends verbose, needs constraints | Tends terse, needs encouragement | Explicitly encourage 2-4 sentence responses |
| Warmth | Naturally warm/chatty | Clinical precision | Add warmth cues without triggering therapy-speak |
| Variety | Naturally varied | Tends to repeat patterns | Encourage response type rotation |
| Questions | Asks fine, sometimes too many | Asks well but nothing else | Encourage observations, reflections, normalizing |
| Thinking | N/A | Extended thinking enabled | May need thinking budget adjustment |

### Opus Addendum Content (Draft)

```
**Response Style (Opus-specific)**

Your responses should feel like a real conversation with a knowledgeable consultant —
not a questionnaire. Vary your response types across turns:

- **Question turns**: Ask one specific question. But frame it naturally: "I'm curious
  about your dad's side — what was his mother like?" not just "What was your paternal
  grandmother's name?"
- **Observation turns**: Sometimes reflect back a pattern or connection you notice:
  "That's interesting — your mom moved cross-country the same year your grandfather
  got sick. Those things often go together." Then let them respond.
- **Bridging turns**: When transitioning topics, acknowledge what they just shared
  before asking about something new: "That gives me a good picture of how things
  were between your parents. Let me ask about your siblings now."
- **Normalizing turns**: When someone shares something heavy, a brief normalizing
  comment before moving on: "A lot of families go through that kind of shift after
  a death. How did your brother handle it?"

Aim for 2-4 sentences per response. One sentence is too abrupt. Five+ is lecturing.
The sweet spot is enough to show you're engaged without dominating the conversation.

Don't be afraid to share a brief thought before asking your question. The user should
feel like they're talking WITH someone, not being interviewed.

When the user shares something emotional or significant, resist the urge to immediately
pivot to the next data point. Spend one beat acknowledging what they said — not with
therapy-speak, but with genuine human engagement: "That's a big deal" or "That must
have changed everything" — then ask your follow-up.
```

### Gemini Addendum Content (Preserve Current Behavior)

```
**Response Style (Gemini-specific)**

Keep responses brief. One question per turn — like real conversation. Not every turn
needs a question; sometimes a short reflection or observation keeps them talking
without being asked.

Do NOT parrot back what the user just said — move the conversation forward.
```

This preserves the existing Gemini behavior exactly as-is.

---

## Experiments to Run

### Experiment 1: Baseline Comparison (Before Any Changes)

**Goal**: Document current Opus output quality to measure improvement.

**Method**:
1. Run 3 synthetic conversations with current prompts using Opus
2. Run 3 synthetic conversations with current prompts using Gemini
3. Score both using `ClientRealismEvaluator` (adapted for coach-side evaluation)
4. Document: average response length, question-only ratio, response type variety

**Metrics**:
- Average words per AI response
- % of responses that are single questions only (no other content)
- Response type distribution (question / observation / bridge / normalization)
- Subjective warmth rating (1-5, human-judged from sample)

### Experiment 2: Opus Addendum A — Gentle Encouragement

**Goal**: Test whether light-touch style guidance improves variety without losing focus.

**Addendum**: The draft above — encourage 2-4 sentences, vary response types, brief acknowledgments before questions.

**Hypothesis**: Response length increases to 2-3 sentences average, question-only ratio drops below 50%, warmth improves.

### Experiment 3: Opus Addendum B — Stronger Persona

**Goal**: Test whether giving Opus a stronger consultant persona improves naturalness.

**Addendum variant**:
```
You are an experienced family systems consultant who has done hundreds of these
intake conversations. You're genuinely fascinated by family patterns — not in an
academic way, but because you've seen how powerful it is when people start to see
the connections in their own family's story. You speak like a real person having
a real conversation. You use contractions. You occasionally share brief observations.
You're warm but direct — you don't pad your responses with filler, but you also
don't fire questions like you're reading from a checklist.
```

**Hypothesis**: Persona framing gives Opus more creative latitude while staying in-role.

### Experiment 4: Thinking Budget Tuning

**Goal**: Test whether extended thinking budget affects response quality/variety.

**Variants**:
- A: `CLAUDE_THINKING_BUDGET = 0` (disable thinking entirely)
- B: `CLAUDE_THINKING_BUDGET = 2048` (current: 4096)
- C: `CLAUDE_THINKING_BUDGET = 8192` (more thinking)

**Hypothesis**: Thinking may be over-constraining responses. With 4096 tokens of "careful thought," Opus may be over-analyzing and producing ultra-safe, minimal responses. Reducing the budget might produce more natural flow.

**Note**: Disabling thinking also means temperature is no longer forced to 1.0 — the configured 0.45 would take effect, which could independently affect output quality.

### Experiment 5: Temperature Exploration (Thinking Disabled)

**Goal**: If thinking is disabled, explore temperature's effect on conversational quality.

**Variants**: 0.45, 0.6, 0.75, 0.9

**Hypothesis**: Higher temperature with Opus (no thinking) may produce more varied, natural responses. The current 0.45 was tuned for Gemini.

### Experiment 6: Combined Best Settings

**Goal**: Combine the winning addendum with the best thinking/temperature settings.

**Method**: Take best from experiments 2-5, run full synthetic conversation suite, compare against Experiment 1 baselines for both Opus and Gemini.

---

## Implementation Sequence

### Phase 1: Architecture (prompt splitting)
1. Split `CONVERSATION_FLOW_PROMPT` into `_CORE` + model addenda in `prompts.py`
2. Add model-aware prompt assembly function
3. Update `chat.py` to use the assembled prompt
4. Update private prompts override to handle new structure (backward compatible)
5. Verify Gemini behavior unchanged (addendum preserves current text exactly)

### Phase 2: Baseline measurement
6. Run Experiment 1 — document current Opus and Gemini baselines

### Phase 3: Prompt tuning
7. Run Experiments 2 and 3 — test addendum variants
8. Pick best addendum, iterate if needed

### Phase 4: Technical tuning
9. Run Experiments 4 and 5 — thinking budget + temperature
10. Run Experiment 6 — combined best settings

### Phase 5: Integration
11. Commit final prompt + settings
12. Update `doc/PROMPT_ENGINEERING_LOG.md` with findings
13. Update `doc/CHAT_FLOW.md` with model-specific prompt architecture

---

## Risk Assessment

- **Low risk**: Prompt changes only affect conversational output, not extraction (separate model/prompts)
- **Reversible**: Environment variable `BTCOPILOT_RESPONSE_MODEL` allows instant model switching
- **No data impact**: Chat responses aren't used for training data or F1 metrics
- **Backward compatible**: Private prompts override still works; Gemini behavior preserved exactly
