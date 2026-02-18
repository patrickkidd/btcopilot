# Evaluator Build + Structural Token Enforcement

**Date**: 2026-02-18 ~05:14 UTC
**Session**: 9e478072-df36-4009-8b8e-45f6f502174d
**Files modified**: `btcopilot/llmutil.py`, `btcopilot/tests/personal/synthetic.py`

## Context

Workstream A+B from SYNTHETIC_CLIENT_PERSONALITIES plan was complete (behavioral prompt spec, dynamic persona generation, attachment styles). The generated conversations sounded AI-like despite good prompt guidance — monotonic response lengths, no pull-backs after vulnerability, therapy-speak.

## Problem

Existing synthetic conversations (e.g., Elena, discussion 47) scored 0.13/1.0 on a new realism evaluator. Average 271 words/turn with zero short responses. Every turn was a multi-paragraph essay regardless of whether the coach asked "How old is your mom?" or "Tell me about the hardest year."

## What Was Tried

### Attempt 1: Prompt-only changes
- Made `_RESPONSE_LENGTH` more forceful with "HARD LIMIT: Never exceed 5-6 sentences"
- User feedback: "The more concrete rules you give the more rigid things become. Dynamic guidance is better."
- Reworked to natural rhythm guidance ("vary your length turn to turn," "after a long answer, go shorter")
- **Result**: 0.13 → 0.16. The model ignores length guidance and fills available tokens.

### Attempt 2: Structural token limits (uniform)
- Made `max_output_tokens` overridable per call in `gemini_text()`
- Applied random token limits to each response
- **Result**: 0.13 → 0.57. Word count patterns became conversational, but no genuinely short responses.

### Attempt 3: Weighted response modes (final)
- Created three modes: "short" (25-50 tokens), "medium" (80-160), "long" (180-300)
- Phase-weighted probabilities: early phase favors short, middle favors medium+long, deep phase has all three
- **Result**: 0.13 → 0.61 mean across 3 conversations. Best individual: Marcus at 0.90.

## Key Insight

**LLMs do not respect prompt-based length guidance.** They fill available `max_output_tokens`. The only reliable way to control response length is structural: set `max_output_tokens` per call. Prompt wording helps with *style* but not *length*.

## ClientRealismEvaluator

Built a hybrid heuristic + LLM evaluator with these dimensions:

| Dimension | Method | What it catches |
|-----------|--------|----------------|
| Therapy-speak | 16 regex patterns | "I realize I have a pattern of...", "processing my grief" |
| Organized delivery | 5 regex patterns | "First... Second... Third..." structured backstory |
| Word count stats | Heuristic | Average, std dev, consecutive long streaks |
| Short response ratio | Heuristic (threshold: 30 words) | Presence of genuinely brief answers |
| Emotional arc | LLM-scored (Gemini, temp=0.0) | Does the conversation oscillate between openness and retreat? |

Scoring: starts at 1.0, penalties for therapy-speak (-0.05 each), organized delivery (-0.10 each), high avg word count (>80), low std dev (<20), consecutive long streaks (>=4), no short responses. Emotional arc weighted at 30%.

## Results Summary

| Metric | Baseline (Elena) | After changes (mean of 3) |
|--------|-----------------|--------------------------|
| Score | 0.13 | 0.61 |
| Avg words/turn | 271 | 91 |
| Max long streak | 24 | 4.3 |
| Short response ratio | 0% | 17% |
| Arc score | 0.20 | 0.55 |

## Clinical Observations

- Marcus (anxious-preoccupied, oversharing/tangential) scored highest (0.90). His natural tendency to flood with detail then pull back maps well to the mode weights.
- Sarah (dismissive-avoidant, evasive/defensive) still tends monotonic (0.45). Avoidant clients in real sessions *do* give clipped answers, but they also have moments of unexpected disclosure. The prompt guidance captures this ("your arc is slower") but the model doesn't vary enough.
- The emotional arc phases ("early" = guarded, "middle" = opening up, "deep" = oscillating) create a natural progression, but the model doesn't pull back after vulnerable moments as much as a real client would.
