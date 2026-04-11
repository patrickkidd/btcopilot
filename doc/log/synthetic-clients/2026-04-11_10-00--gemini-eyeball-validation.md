# Gemini Flash Eyeball Validation Against Exp1 Core Prompt

**Date**: 2026-04-11
**Scope**: First validation of Gemini Flash with the Exp1 `_CONVERSATION_FLOW_CORE` rewrite
**Model**: gemini-2.5-flash
**Persona**: Sarah (DismissiveAvoidant, Evasive/Defensive)
**Turns**: 8 (crashed on turn 9 — `NoneType.strip()` in response handling)

## Context

Exp1 rewrote `_CONVERSATION_FLOW_CORE` and `_CONVERSATION_FLOW_OPUS` but left `_CONVERSATION_FLOW_GEMINI` (5 lines) untouched. This is the first time Gemini has been run against the new core.

## Observed Failure Modes

### FM1: Topic Stagnation
Coach stayed on the sleep topic for all 8 turns. Never pivoted to family structure, relationships, or multigenerational patterns — the core purpose of the conversation. The Exp1 core prompt includes bridging guidance ("OK, that gives me a good picture of your parents' side. Let me ask about your siblings.") but Gemini does not execute it.

**Turns affected**: All 8
**Example**: Turn 5 is the 4th consecutive attempt to ask about sleep timing.

### FM2: Question Reformulation Loop
When the user gave evasive answers (turns 2, 3, 4, 5, 8 were fallback evasive responses), the coach rephrased the same question rather than pivoting. Four consecutive turns asked variants of "when did the sleep problem start" / "what does your sleep look like."

**Turns affected**: 2, 3, 4, 5
**Root**: The existing addendum says "move the conversation forward" but this is too vague for Gemini. Gemini interprets "forward" as "get the answer to the current question" rather than "move to a new topic."

### FM3: Fragment Completion
Turn 6 — user said "Usually I fall asleep okay because I am." (period-appended stub from synthetic client). Coach responded: "You fall asleep okay because you are... [pause] Can you tell me more about that?" — echoing and attempting to complete the user's unfinished thought.

**Turns affected**: 6
**Root**: The existing addendum says "Do NOT parrot back what the user just said" but does not address completing fragments.

### FM4: Zero Response Type Variety
Every AI turn follows the same pattern: acknowledgment sentence + question. No observations about family patterns, no bridges to new topics, no normalizing statements. The Exp1 core includes a response type menu but Gemini defaults to validate+question on every turn.

**Turns affected**: All 8
**Metric**: Response type entropy would be near 0 (all Question-Only or Mixed with no Observation/Bridge/Normalize).

## Raw Transcript

(Not saved to file — script crashed before write. Captured from console.)

```
[1] AI: Thanks for sharing that. It's a good place to start.
When did you first notice your sleep wasn't as good? Was it a sudden change or more gradual?

[2] AI: No problem at all. Sometimes it helps to think about specific moments.
Can you remember roughly when you first started noticing a change in your sleep? For example, was it in the last few months, or longer ago?

[3] AI: That's perfectly fine. Sometimes it's hard to pinpoint an exact date.
Has this been going on for a few weeks, a few months, or longer than that?

[4] AI: That's understandable. Sometimes these things creep up on us.
What does your sleep look like now? For example, are you having trouble falling asleep, staying asleep, or waking up too early?

[5] AI: I understand it can be tough to describe. Let's try a different way.
When you go to bed, do you find yourself lying awake for a long time before you fall asleep? Or do you fall asleep okay but then wake up in the middle of the night?

[6] AI: You fall asleep okay because you are... [pause] Can you tell me more about that?

[7] AI: Thanks for clarifying. So you're often exhausted when you go to bed and fall asleep fairly easily.
What happens after that? Do you stay asleep through the night, or do you find yourself waking up?

[8] AI: That's fair. Sometimes we don't pay close attention until something feels off.
So, once you fall asleep because you're exhausted, do you tend to stay asleep through the night, or do you find yourself waking up at some point?
```

## Proposed Metrics

| Failure Mode | Metric | How to Measure | Threshold |
|-------------|--------|----------------|-----------|
| FM1: Topic Stagnation | Max consecutive turns on same topic | Keyword clustering or manual tag | Fail if >3 turns without family-related question |
| FM2: Reformulation Loop | Consecutive semantically similar questions | Embedding similarity between AI questions | Fail if >2 consecutive similar questions |
| FM3: Fragment Completion | AI echoes user's incomplete phrase | Regex: AI response contains "..." + user's last words | Any occurrence = fail |
| FM4: Response Type Variety | Response entropy | Existing QualityEvaluator `_classify_response_types` | Entropy < 0.5 = fail |

## Iteration 1: Guideline-Based Addendum Rewrite

**Change**: Replaced 5-line rule-based addendum with guideline-based voice/approach framing, similar to how Opus addendum works. Key principle: "You're curious about the whole family picture, not any single detail. If someone doesn't want to talk about something... you move to a different part of the family." Added "breadth first" orientation and "work with what they actually say."

**Rationale**: Patrick flagged that rule-based constraints ("if X do Y") are lazy prompting. Better to orient the model's approach so it infers the right behavior. The Opus addendum succeeds because it gives voice, not rules.

### Results (10 turns, Sarah, 2026-04-11_10-18)

**Improvements**:
- FM3 (fragment completion): **Fixed.** No instances of completing user's fragments.
- FM1 (topic stagnation): **Partial.** Turn 4 pivoted from sleep details to "who else in your life" — a family-oriented move. Previously stayed on sleep for all 8 turns.

**Still present**:
- FM2 (reformulation loop): Turns 6-8 ask "who is David" three times in a row before pivoting at turn 9. The "breadth first" guideline helped on initial pivot but Gemini still fixates when it asks a specific question.
- FM4 (response variety): Still mostly bare questions. Turn 3 picked up on "again" (good inference), but no observations about family patterns, no normalizing.

**New issue**:
- FM5: Off-domain pivot — Turn 9-10 pivoted to "What have you tried so far to help with your sleep?" — a medical question, not family systems. The breadth-first guideline was interpreted as "explore the sleep problem broadly" instead of "explore the family broadly."

**Confounding factor**: The synthetic client generated fallback evasive responses on 7/10 turns. Sarah IS DismissiveAvoidant, so evasion is realistic, but the generic fallback sentences ("I couldn't really tell you why it happened that way") give the coach nothing to work with. Hard to assess coaching quality when the client isn't participating meaningfully. This is a synthetic client infrastructure problem, not a prompt problem.

### Raw Transcript

See: `eyeball-comparison/2026-04-11_10-18_gemini-exp1_Sarah.txt`

## Iteration 2: Root Cause Found — Thinking Budget

**Discovery (2026-04-11)**: The synthetic client's sentence fragment problem was caused by `thinking_budget=4096` on all `gemini_text()` calls in `llmutil.py`. With thinking enabled, Gemini consumed tokens on internal reasoning and produced truncated, fragmentary output (2-5 word stubs). With `thinking_budget=0`, Gemini produces rich, complete, in-character responses natively — 30-300 words per turn, all properly punctuated, zero fragments.

**Evidence**: 5/5 raw Gemini calls with `thinking_budget=0` returned 47-59 word complete sentences. Full 20-turn conversation with fresh persona "Tiffany" (AnxiousPreoccupied, Oversharing+Tangential) produced zero stubs, zero fallbacks, zero prompt leaks.

**What this means**: All the post-processing hacks (`_trim_to_sentence` complexity, dangling-tail regex, period-append, sub-8-word fallback with retry) were treating a symptom. The fix was one parameter change.

**Fix applied**: `simulate_user_response` now passes `thinking_budget=0` to `gemini_text_sync`. `_trim_to_sentence` simplified back to a safety net. `llmutil.gemini_text()` now accepts `thinking_budget` kwarg (default 4096 preserved for other callers).

### Transcript

See: `eyeball-comparison/2026-04-11_11-18_opus-fresh-20t.txt`

## Assessment

With thinking disabled, the synthetic client is no longer the bottleneck. The coach prompt quality differences are now clearly visible:
- Opus Exp1: Excellent. Pivots to factual questions when blocked, makes pattern observations, tracks emotional state across turns.
- Gemini coach: Still needs validation with a non-broken client. Previous Gemini eyeball tests were confounded by the broken client generating 50-70% fallback responses. Needs re-run.

**Open question**: Re-run Gemini coach eyeball now that the synthetic client produces substantive responses. The previous Gemini coach assessment (FM1-FM5) may have been entirely caused by the broken client, not Gemini coaching ability.