# Opus Conversational Prompt Tuning

**Date**: 2026-03-15
**Scope**: Conversation flow prompt changes (core), thinking budget experiment, QualityEvaluator classifier fix

## What Changed

### Experiment 1: Core Prompt Rewrites (SHIPPED)

Three changes to `_CONVERSATION_FLOW_CORE` in `fdserver/prompts/private_prompts.py`:

**A. Terminal directive rewrite** — Was: "Ask for the next missing data point from the current phase." Now: menu of response types (observation, bridge, normalization, question) with guidance on when each fits. This was the highest-leverage change — terminal directives have the strongest recency effect on LLM behavior.

**B. Removed phase exchange counts** — Removed "5-10 exchanges", "2-3 exchanges", "2-4 exchanges" from all phase headers. These created artificial urgency to pivot topics before they were explored.

**C. Rewrote pivot logic** — Removed the "8+ statements" red flag (acted as a ceiling, not a floor). Replaced scripted pivot line with natural-transition guidance. Added "You keep asking questions without ever making an observation" as a new red flag.

### Experiment 2: Thinking Budget = 0 (REJECTED)

Tested `CLAUDE_THINKING_BUDGET = 0` in `btcopilot/llmutil.py`. Three problems emerged:
- **Sentence completion**: Opus fabricated what the user was about to say instead of waiting
- **Context loss**: AI reset mid-conversation ("Sorry, let me start over")
- **No strategic pivot**: Marcus persona spent all 20 turns on presenting problem, never reached family structure (coverage 64% → 27%)

Thinking budget stays at 4096. The conditional code was kept as a clean toggle for future experiments.

### QualityEvaluator Classifier Fix

Original `_classify_response_types` used narrow keyword regex that under-detected Mixed responses. Replaced with sentence-level analysis: split on sentence boundaries, classify each sentence as question vs declarative, check for bridge/normalization phrases, then determine overall response type. Also unified sentence-splitting regex between `_question_only_ratio` and `_classify_response_types` (DRY fix).

### Prompt Override Refactor

Replaced constant-overriding mechanism with callable override for conversation flow prompts. btcopilot defines stub `get_conversation_flow_prompt(model)`, fdserver overrides with production implementation. This isolates per-model prompt assembly in fdserver with no risk of cross-model contamination.

## Why

Opus conversations were mostly bare questions with early topic pivots. Root causes:
1. Terminal directive ("Ask for the next missing data point") hardcoded question-asking
2. Phase exchange counts created artificial urgency to pivot
3. "8+ statements" red flag punished staying with a topic
4. Extended thinking (4096 tokens) used to audit the data checklist, producing optimal-next-question behavior

## Results

### Experiment 1 — Opus (baseline → experiment)

| Persona | QO% | Entropy | AvgWords | Coverage |
|---------|:---:|:---:|:---:|:---:|
| Sarah_Evasive | 15% → 45% | 0.29 → 1.00 | 18 → 23 | 36% → 27% |
| Marcus_Oversharing | 20% → 10% | 0.29 → 1.19 | 25 → 25 | 64% → 64% |
| Parent_Terse | 35% → 15% | 0.00 → 0.97 | 28 → 33 | 27% → 45% |

Response type entropy improved dramatically across all personas (from near-zero to ~1.0). The AI now produces observations, bridges, and mixed responses instead of bare questions.

### Experiment 1 — Gemini (no regression, improved)

| Persona | QO% | Coverage |
|---------|:---:|:---:|
| Sarah_Evasive | 70% → 0% | 36% → 64% |
| Marcus_Oversharing | 65% → 5% | 36% → 73% |
| Parent_Terse | 55% → 0% | 36% → 55% |

Core prompt changes improved Gemini even more than Opus. No regression.

### Experiment 2 — Opus (thinking=0 vs thinking=4096)

| Persona | QO% | Coverage | Problem |
|---------|:---:|:---:|---------|
| Sarah | 10% | 55% | Sentence completion (fabricates user's words) |
| Marcus | 25% | **27%** | No strategic pivot |
| Parent_Terse | 5% | 45% | Context loss |

Rejected. Thinking is essential for strategic state tracking.

## Clinical Observations

**Experiment 1 (positive)**: The AI now makes observations about family patterns ("That timing is interesting"), normalizes heavy disclosures ("A lot of families hit that kind of wall"), and bridges between topics naturally. Conversations feel more like a first coaching session and less like a structured intake questionnaire.

**Experiment 2 (negative)**: Without thinking, the AI completed the user's sentences by fabricating content (e.g., user says "I was fifteen, so I was right in the middle of high school, and" → AI responds with "Michael would've been about eleven" without the user saying this). This is worse than asking too many questions — it puts words in people's mouths. A real clinician would never do this.

## ⚠️ Retroactive Finding: Synthetic Client Bug Contaminated All Prior Runs

After reviewing transcripts, Patrick flagged that the synthetic client (Gemini playing the user) was generating incomplete sentences — fragments like "It's been going on for a few" or "My mind just starts". This was traced to instructions in `_CONVERSATIONAL_REALISM` ("Trail off on hard topics", "Correct yourself mid-thought") introduced in `d9effef` which Gemini interprets literally. The incomplete user turns caused the AI coach to waste turns asking "Go ahead..." which inflated question-only ratio and compressed coverage.

**Impact**: All baselines and experiments above have contaminated client behavior. Directional improvements in Exp 1 are still valid (the coach AI changes are real), but absolute metrics are unreliable.

**Fix (2026-03-16)**: Three changes to `btcopilot/tests/personal/synthetic.py`:
1. Removed "Trail off on hard topics" from `_CONVERSATIONAL_REALISM`
2. Changed "Correct yourself mid-thought" to "Correct yourself — finish your sentence, then walk it back"
3. Added post-processing in `simulate_user_response`: appends "." if response lacks terminal punctuation (Gemini ignores all prompt-based constraints on this)

**Clean runs**: `baseline2/` (original prompts + fixed client), `experiment1b/` (Exp 1 prompts + fixed client). These supersede the original runs.

## Artifacts

| Type | Path | Status |
|------|------|--------|
| Baseline transcripts | `baselines/2026-03-15_19-01_*.txt` | ⚠️ Contaminated |
| Baseline JSON | `baselines/2026-03-15_19-01_full_results.json` | ⚠️ Contaminated |
| Experiment 1 transcripts | `experiment1/2026-03-15_19-33_*.txt` | ⚠️ Contaminated |
| Experiment 1 JSON | `experiment1/2026-03-15_19-33_full_results.json` | ⚠️ Contaminated |
| Experiment 2 transcripts | `experiment2/2026-03-15_19-50_*.txt` | ⚠️ Contaminated |
| Experiment 2 JSON | `experiment2/2026-03-15_19-50_full_results.json` | ⚠️ Contaminated |
| Baseline2 transcripts | `baseline2/` | ✅ Clean (original prompts + fixed client) |
| Experiment 1b transcripts | `experiment1b/` | ✅ Clean (Exp 1 prompts + fixed client) |
