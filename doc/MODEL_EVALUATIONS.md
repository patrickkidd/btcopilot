# Model Evaluations Catalog

**Purpose**: Single index of every extraction-model evaluation, so any session can
compare options without mining induction reports. One row per model/config.

**⚠️ THE COMPARABILITY RULE**: F1 numbers are only comparable WITHIN a benchmark
era. The matching logic and deterministic repairs changed between eras — a March
number and a June number for the same model are different rulers. When comparing
an experiment to production, use the **same-day production baseline** row listed
with that experiment, never a number from another era.

**Benchmark**: 6 synthetic GT discussions (36, 37, 39, 48, 50, 51) via
`btcopilot.training.run_extract_full_f1`. Noise: Gemini Events F1 varies 10–15%
run-to-run (3-run means required); claude-fable-5 is near-deterministic.

## Benchmark eras

| Era | Dates | Pipeline | Comparable to |
|---|---|---|---|
| E1 | ≤2026-02 | Per-statement extraction; description-gated matching | Nothing current |
| E2 | 2026-03 | 2-pass split; description-free matching; thinking=1024; 3-pass R-review added late in era | E2 only |
| E3 | 2026-05 → current | E2 + committed-dup carve-out, re-extraction cursor, parent-inference repair (FD-319/FD-324) | E3 only |

## E3 — current pipeline era

### claude-fable-5 experiment (2026-06-09) — [report](induction-reports/2026-06-09_16-10-00--fable-5-extraction/2026-06-09_16-10-00.md)

| Config (extraction / SARF review) | Runs | Agg | Events | People | Bonds | SARF macro | Latency/disc | $/disc | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite / gemini-3-flash (**prod, same-day baseline**) | 3 | 0.658 | 0.427 | 0.926 | 0.824 | 0.375 | ~25–60s | ~$0.003 | Production |
| flash-lite / **claude-fable-5** (hybrid) | 2 | 0.657 | 0.442 | 0.907–0.926 | — | **0.535** | +30–60s on P3 | $0.20 | **Best SARF $/lift**; SARF S+F cross Stage 4 |
| **claude-fable-5** / gemini-3-flash | 5 | 0.721 | **0.592** | 0.930 | 0.785 | 0.367 | 71–179s | $0.83 | Best Events; async-only |
| claude-fable-5 / claude-fable-5 | 1 | **0.731** | **0.617** | 0.922 | 0.775 | **0.621** | 71–179s | $1.30 | Record on all metrics; async-only; SARF single-run |

Experiment facts: prompt induction converged at cold baseline (gains are
model-native; Gemini-tuned prompts transfer unchanged). Anthropic constrained
decoding rejects the PDPDeltas schema — adapter uses schema-in-prompt
(`llmutil.claude_structured`). Run variance 3–5× lower than Gemini. Events and
SARF gains are independent levers (extraction pass vs review pass).

### FD-319 / FD-324 measurements (2026-05-16/20) — same era, different days

| Config | Runs | Agg | Events | Notes |
|---|---|---|---|---|
| gemini-3-flash-preview (FD-319 prompt-idempotency check) | 2 | 0.687 | 0.518 | [report](induction-reports/2026-05-16_08-40-13--fd319-prompt-idempotency/) |
| flash + parent-inference repair (FD-324) | — | 0.651 | — | ParentChild 0.366→0.782; LCC 51→89.5% |

## E2 — 2-pass era (2026-03-03/04) — numbers NOT comparable to E3

### Frontier model evaluation (2026-03-04) — [report](induction-reports/2026-03-04_15-36-39--model-evaluation-frontier/2026-03-04_15-36-39.md)

| Model | N | Agg | Events | Bonds | Latency | $/extract | Verdict |
|---|---|---|---|---|---|---|---|
| gemini-3-flash-preview (t=1024) | 6/6 | 0.654 | 0.397 | 0.803 | 74s | $0.016 | Recommended upgrade (then) |
| gpt-5-mini | 5/6 | 0.645 | 0.410 | 0.650 | 460s | $0.009 | Quality yes, latency no |
| gpt-5.2 | 6/6 | 0.620 | 0.397 | 0.514 | 196s | $0.065 | Bonds collapse |
| o4-mini | 6/6 | 0.615 | 0.345 | 0.581 | 289s | $0.028 | Baseline-tier, slow |
| gemini-2.5-flash (t=1024) | 6/6 | 0.613 | 0.364 | 0.819 | 96s | $0.012 | Prod at the time |
| grok-4-1-fast-reasoning | 4/6 | 0.606 | 0.309 | 0.825 | 513s | $0.004 | Weak events, failures |
| grok-4-fast-reasoning | 6/6 | 0.559 | 0.255 | — | 356s | — | Dropped |
| gpt-5-nano | 6/6 | 0.554 | 0.235 | — | 831s | — | Dropped (rate limits) |
| gpt-4.1 | 4/6 | 0.537 | 0.259 | — | — | — | Dropped (failures) |
| gemini-2.5-pro (t=1024) | 6/6 | 0.632 | 0.348 | — | 216s | — | Slower AND worse events |
| gemini-3-pro-preview | 0/6 | — | — | — | 504 timeouts | — | Unusable |
| gpt-4o *(deprecated)* | — | 0.552 | 0.276 | 0.290 | — | — | Bonds catastrophic |
| grok-3 *(deprecated)* | — | 0.607 | — | — | 279s | — | SARF near-zero |

### Other E2 findings

| Config | Result | Source |
|---|---|---|
| gemini-3.1-flash-lite (t=1024) | Agg 0.600, Events 0.368 — matches 2.5-flash at ~6× lower cost | [flash-lite eval](induction-reports/2026-03-04_13-15-00--model-evaluation-flash-lite/) |
| thinking_budget sweep | 1024 is the optimum (bell curve 0→4096); without thinking, lite models drop whole event categories | same |
| 3-pass R-review architecture | R +103% (0.240→0.487), SARF macro +39% (0.341→0.473) on gemini-3-flash | [sarf-gemini3-flash](induction-reports/2026-03-04_19-22-28--sarf-gemini3-flash/) |
| Hybrid per-pass (flash-lite P1, 2.5-flash P2) | No benefit — bottleneck was thinking budget, not model tier. **Overturned 2026-06-09 for cross-provider review-pass swaps** (fable-5 P3 lifts SARF +43%) | strategy doc |

## E1 — per-statement era (≤2026-02) — historical only

gemini-2.5-flash per-statement: Aggregate ~0.24, Events ~0.14 (45 GT cases).
Superseded by the 2-pass split; no current relevance beyond "don't go back".

## Maintenance

- Every model experiment adds its rows here (config, N, metrics, $/disc, latency,
  verdict, report link) alongside the same-day production baseline it was
  measured against.
- New matching-logic or repair changes start a new era section.
- Detailed lessons stay in [PROMPT_ENG_EXTRACTION_STRATEGY.md](PROMPT_ENG_EXTRACTION_STRATEGY.md);
  decisions in [../decisions/log.md](../decisions/log.md). This file is the index,
  not the narrative.
