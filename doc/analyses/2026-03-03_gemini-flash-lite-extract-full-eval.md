# Gemini 3.1 Flash Lite vs 2.5 Flash — extract_full() F1 Evaluation

**Date:** 2026-03-03
**Task:** T7-20
**Method:** `pdp.extract_full()` (single-prompt full conversation extraction)
**Discussions:** 48, 50, 51 (3 of 6 requested had approved GT; 49/53 not found, 52 no GT)

## Results

### Per-Discussion Breakdown

| Discussion | Metric | gemini-3.1-flash-lite-preview | gemini-2.5-flash | Delta |
|------------|--------|-------------------------------|------------------|-------|
| 48 | People F1 | **0.692** | 0.385 | **+0.307** |
| 48 | Events F1 | 0.133 | **0.148** | -0.015 |
| 48 | PairBonds F1 | **0.286** | 0.250 | +0.036 |
| 48 | Aggregate F1 | **0.381** | 0.227 | **+0.154** |
| 50 | People F1 | 0.480 | 0.480 | 0.000 |
| 50 | Events F1 | **0.111** | 0.078 | +0.033 |
| 50 | PairBonds F1 | 1.000 | 1.000 | 0.000 |
| 50 | Aggregate F1 | **0.328** | 0.222 | **+0.106** |
| 51 | People F1 | 0.387 | 0.387 | 0.000 |
| 51 | Events F1 | **0.250** | 0.222 | +0.028 |
| 51 | PairBonds F1 | 0.750 | 0.750 | 0.000 |
| 51 | Aggregate F1 | **0.354** | 0.314 | +0.040 |

### Averages Across All Discussions

| Metric | gemini-3.1-flash-lite-preview | gemini-2.5-flash | Delta |
|--------|-------------------------------|------------------|-------|
| **People F1** | **0.520** | 0.417 | **+0.103** |
| **Events F1** | **0.165** | 0.149 | **+0.016** |
| **PairBonds F1** | **0.679** | 0.667 | **+0.012** |
| **Aggregate F1** | **0.355** | 0.254 | **+0.101** |
| Symptom F1 | 1.000 | 1.000 | 0.000 |
| Anxiety F1 | 1.000 | 0.821 | +0.179 |
| Relationship F1 | 1.000 | 0.778 | +0.222 |
| Functioning F1 | 1.000 | 0.810 | +0.190 |
| **Runtime** | **37s** | 69s | **-46%** |

### Entity Count Comparison (AI Extracted vs GT)

| Discussion | GT People | GT Events | GT Bonds | Flash-Lite People | Flash-Lite Events | Flash Events |
|------------|-----------|-----------|----------|--------------------|--------------------|--------------|
| 48 | 14 | 21 | 4 | 12 | 9 | 33 |
| 50 | 13 | 29 | 3 | 12 | 7 | 48 |
| 51 | 16 | 26 | 4 | 15 | 14 | 37 |

## Key Findings

### 1. Flash-lite outperforms 2.5-flash on extract_full()

**Surprising result.** Flash-lite scored higher than 2.5-flash on every aggregate metric. The primary reason: **2.5-flash massively over-generates events** (33-48 AI events vs 21-29 GT events), driving up false positives. Flash-lite produces fewer, more focused extractions.

### 2. Both models are much weaker on extract_full() than per-statement cumulative

The T7-7 cumulative baseline (per-statement `pdp.update()`) was:
- People F1 = 0.926, Events F1 = 0.387, PairBonds F1 = 0.590

Both models score **much lower** with `extract_full()`:
- Flash-lite: People 0.520, Events 0.165, PairBonds 0.679
- 2.5-flash: People 0.417, Events 0.149, PairBonds 0.667

This suggests the per-statement incremental approach (with cumulative context) is fundamentally better at extraction than single-prompt full-conversation extraction.

### 3. Flash-lite is ~2x faster

37s vs 69s for 3 discussions. Flash-lite's speed advantage compounds at scale.

### 4. Flash-lite is cheaper

- Input: $0.25/M tokens (flash-lite) vs $0.30/M tokens (2.5-flash) — 17% cheaper
- Output: $1.50/M tokens (flash-lite) vs $2.50/M tokens (2.5-flash) — 40% cheaper

### 5. SARF variable extraction is unreliable with few event matches

Flash-lite shows perfect 1.000 SARF scores but only had 2-5 matched events per discussion. The 2.5-flash SARF scores (0.78-0.82) are based on 4-7 matches. Neither sample is large enough for confidence.

### 6. Events F1 threshold check

Task asked: "If flash-lite Events F1 >= 0.3, it's a win." Result: Events F1 = 0.165 (below 0.3). However, 2.5-flash Events F1 = 0.149, so flash-lite is **still better** than the current production model on this metric.

## Recommendation

**For extract_full(): Use flash-lite.** It's faster, cheaper, and produces better results than 2.5-flash on single-prompt full-conversation extraction.

**For prompt-tuning (T7-8):** The bigger issue is that `extract_full()` scores much lower than cumulative extraction. The prompt-tuning effort should focus on improving the full-extraction prompt rather than switching models. Flash-lite is a fine model for this work since it's the stronger performer.

**Production model (`EXTRACTION_MODEL`):** Keep `gemini-2.5-flash` for per-statement extraction (`pdp.update()`) since T7-7 showed strong cumulative F1 with that model. Consider a separate model config for extract_full() if both paths are needed.

## Reproduction

```bash
export $(grep -v '^#' ~/.openclaw/.env | xargs)

# Flash-lite eval
uv run python -m btcopilot.training.eval_flash_lite --model gemini-3.1-flash-lite-preview --detailed

# 2.5-flash baseline
uv run python -m btcopilot.training.eval_flash_lite --model gemini-2.5-flash --detailed
```
