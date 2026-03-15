# 2026-03-14 18:30 — Quality Evaluator: Conversational Metrics

## What Changed

Extended `QualityEvaluator` in `synthetic.py` with five new computable metrics:

1. **`wordsPerResponse`** — word count distribution for AI turns (list, with derived mean/median/std/range)
2. **`questionOnlyRatio`** — fraction of AI responses that are a single bare question with no framing
3. **`responseTypes`** — heuristic classification of each AI turn as Question/Observation/Bridge/Normalization/Mixed
4. **`responseTypeEntropy`** — Shannon entropy over response type distribution (higher = more varied)
5. **`starterEntropy`** — Shannon entropy over 3-word opening phrases (higher = less repetitive)

Added `ResponseType` enum and `summary()` method to `QualityResult` for formatted comparison output.

## Why

Needed computable metrics to compare Opus vs Gemini conversational quality. The existing evaluator measured anti-patterns (cliches, echoing, repetition) but not positive qualities (response length, variety, warmth). The original plan called for an LLM-judged scoring framework; we opted for cheap deterministic metrics first to see if they discriminate between models before investing in LLM judges.

## Psychological Rationale

- **Word count distribution**: A good clinical interviewer varies response length — brief follow-ups ("What happened next?") alternate with longer reflections. Uniform short responses feel robotic; uniform long ones feel lecturing. Std dev matters more than mean.
- **Question-only ratio**: Real consultants don't just fire questions. They observe, normalize, bridge between topics. A high question-only ratio correlates with "checklist interviewer" feel.
- **Response type variety**: Maps directly to the Opus addendum's design — it explicitly encourages question/observation/bridge/normalization rotation. Entropy measures whether this is actually happening.

## Results

Ran Opus vs Gemini baseline (2 personas × 2 models × 12 turns):

| Metric | Opus (evasive) | Opus (oversharing) | Gemini (evasive) | Gemini (oversharing) |
|--------|---------------|-------------------|-----------------|---------------------|
| Avg words | 24 | 37 | 17 | 18 |
| Question-only | 33% | 0% | 33% | 33% |
| Type entropy | 0.00 | 0.41 | 0.00 | 0.00 |
| Echo rate | 0.08 | 0.58 | 0.42 | 0.00 |
| Quality score | 0.97 | 0.72 | 0.88 | 0.80 |

Key finding: Opus adapts to persona — longer/more varied responses with the oversharing persona, more concise with the evasive one. Gemini is uniformly terse regardless of persona.

## Clinical Observations

Opus produced responses a therapist would recognize as competent intake interviewing: staying in the story, making timeline connections ("Six months ago — so right around when the sleep trouble started"), normalizing without therapy-speak. Gemini's responses felt more like a medical questionnaire.

The response type classifier under-detects Mixed responses — many Opus responses contain both an observation and a question but are classified as Question because they end with `?`. Needs tuning.

## Limitations

- Response type classification is heuristic (regex-based), not semantic. It will miss subtle observations that don't match the keyword patterns.
- Starter entropy at 12 turns is near-maximum for all conditions — doesn't differentiate well at small N.
- Echo rate penalizes content overlap, which may be appropriate clinical behavior (reflecting back) with oversharing clients.
