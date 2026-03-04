# Extraction F1 Report — 2026-03-04

**Evaluation type**: Cumulative F1 (per-statement AI extractions vs approved GT)
**Discussions evaluated**: 36 (Sarah), 37 (Marcus), 39 (Jennifer), 48 (Arthur)
**Auditor**: patrick@alaskafamilysystems.com
**Model**: Gemini 2.0 Flash (per-statement extraction via `pdp.update()`)
**Script**: `uv run python -m btcopilot.training.validate_t7_f1 --ids 36 37 39 48 --detailed`

> **Note**: The single-prompt `extract_full()` CLI (`run_extract_full_f1.py`) could not be
> used due to an `aiohttp` connector assertion error (`google-genai` 1.65.0 + `aiohttp`
> 3.13.3). This works in the Flask server context but fails in standalone CLI mode.
> Filed as a known issue — see [Recommended Actions](#recommended-actions).

---

## 1. Overall F1 vs MVP Targets

| Entity Type | Avg F1 | MVP Target | Status | Gap |
|-------------|--------|------------|--------|-----|
| **People** | **0.808** | ≥ 0.72 | PASS | +0.088 |
| **Events** | **0.312** | ≥ 0.40 | FAIL | −0.088 |
| **PairBonds** | **0.426** | ≥ 0.50 | FAIL | −0.074 |
| Aggregate (micro) | 0.470 | — | — | — |

**Summary**: People extraction exceeds target comfortably. Events and PairBonds both fall short. The primary bottleneck is **event false positives** — the AI consistently over-extracts events (2.5–3.5x the GT count).

---

## 2. Per-Discussion Breakdown

### Discussion 36 — Synthetic: Sarah

| Metric | F1 | TP | FP | FN | AI Count | GT Count |
|--------|------|-----|-----|-----|----------|----------|
| People | 0.880 | 11 | 0 | 3 | 11 | 14 |
| Events | 0.431 | 11 | 26 | 3 | 37 | 14 |
| PairBonds | 0.000 | 0 | 0 | 3 | 0 | 3 |
| **Aggregate** | **0.557** | | | | | |

SARF: S=1.000, A=0.450, R=0.402, F=0.807

**Key issues**: Zero PairBond extraction (AI finds none). People under-extraction (3 FN). Events heavily over-extracted (26 FP).

---

### Discussion 37 — Synthetic: Marcus

| Metric | F1 | TP | FP | FN | AI Count | GT Count |
|--------|------|-----|-----|-----|----------|----------|
| People | 0.800 | 12 | 5 | 1 | 17 | 13 |
| Events | 0.274 | 13 | 58 | 11 | 71 | 24 |
| PairBonds | 0.286 | 1 | 2 | 3 | 3 | 4 |
| **Aggregate** | **0.394** | | | | | |

SARF: S=0.402, A=0.647, R=0.299, F=0.211

**Key issues**: Worst event over-extraction (71 AI vs 24 GT = 58 FP). SARF functioning score very low (0.211). People slightly over-extracted (5 FP).

---

### Discussion 39 — Synthetic: Jennifer

| Metric | F1 | TP | FP | FN | AI Count | GT Count |
|--------|------|-----|-----|-----|----------|----------|
| People | 0.848 | 14 | 2 | 3 | 16 | 17 |
| Events | 0.317 | 10 | 35 | 8 | 45 | 18 |
| PairBonds | 0.750 | 3 | 0 | 2 | 3 | 5 |
| **Aggregate** | **0.519** | | | | | |

SARF: S=1.000, A=0.474, R=0.533, F=0.474

**Key issues**: Strong PairBond performance (best of 4). Event over-extraction (35 FP). Balanced people extraction.

---

### Discussion 48 — Synthetic: Arthur

| Metric | F1 | TP | FP | FN | AI Count | GT Count |
|--------|------|-----|-----|-----|----------|----------|
| People | 0.703 | 13 | 10 | 1 | 23 | 14 |
| Events | 0.225 | 8 | 42 | 13 | 50 | 21 |
| PairBonds | 0.667 | 3 | 2 | 1 | 5 | 4 |
| **Aggregate** | **0.410** | | | | | |

SARF: S=0.222, A=0.333, R=0.500, F=0.222

**Key issues**: Worst people over-extraction (10 FP, nearly doubling GT count). Worst event FN count (13 missed). Lowest SARF scores across the board.

---

## 3. Top Error Categories

### 3.1 Event Over-Extraction (Critical — affects all discussions)

| Discussion | AI Events | GT Events | FP | FP Rate |
|------------|-----------|-----------|-----|---------|
| 36 (Sarah) | 37 | 14 | 26 | 1.86x GT |
| 37 (Marcus) | 71 | 24 | 58 | 2.42x GT |
| 39 (Jennifer) | 45 | 18 | 35 | 1.94x GT |
| 48 (Arthur) | 50 | 21 | 42 | 2.00x GT |
| **Total** | **203** | **77** | **161** | **2.09x GT** |

The AI extracts ~2x the number of events vs GT. This is the single largest F1 drag. Likely causes:
- Splitting single clinical events into multiple granular events
- Hallucinating events not stated in conversation
- Over-interpreting passing mentions as discrete events

### 3.2 PairBond Under-Extraction (Discussion 36)

Discussion 36 extracts zero PairBonds (0/3 GT). This is a known gap per `F1_METRICS.md`. The AI sometimes fails to infer relationship bonds that are implied but not explicitly stated.

### 3.3 People Over-Extraction (Discussion 48)

Discussion 48 has 10 FP people (23 AI vs 14 GT). The AI may be creating separate person entries for the same individual mentioned by different names/roles.

### 3.4 SARF Variable Accuracy

| SARF Variable | Avg Macro F1 | Range |
|---------------|-------------|-------|
| Symptom | 0.656 | 0.222–1.000 |
| Anxiety | 0.476 | 0.333–0.647 |
| Relationship | 0.434 | 0.299–0.533 |
| Functioning | 0.429 | 0.211–0.807 |

Functioning and Relationship variables are weakest. Discussion 48 (Arthur) drags all SARF scores down significantly.

---

## 4. Recommended Next GT Coding Priorities

### Priority 1: Event Precision Improvement (Highest Impact)

The 161 total FP events across 4 discussions destroy Events F1. Recommended actions:
1. **Analyze FP events in discussions 37 and 48** — the worst offenders (58 and 42 FP respectively). Categorize what types of spurious events the AI creates.
2. **Add negative examples to prompts** — show examples of mentions that should NOT become events.
3. **Consider raising the extraction threshold** — if the model is hallucinating events at low confidence, a confidence filter may help.

### Priority 2: PairBond Extraction Gap

- **Discussion 36** extracts zero PairBonds despite 3 in GT. Review conversation to understand why bonds aren't being inferred.
- PairBond avg F1 (0.426) is close to the 0.50 target — fixing the zero-extraction case in disc 36 alone would likely push past target.

### Priority 3: People Deduplication (Discussion 48)

- 10 FP people in disc 48 suggests name/role aliasing issues. Review whether the model creates duplicate entries for the same person referred to by different names.

### Priority 4: SARF Functioning Calibration

- Functioning macro F1 (0.429 avg) is weakest SARF variable. Discussion 48 (0.222) and 37 (0.211) are outliers.
- Review GT functioning annotations in these discussions for possible GT coding gaps or prompt gaps.

### Priority 5: Fix `extract_full()` CLI Bug

- The `run_extract_full_f1.py` script fails with `AssertionError` from `aiohttp` connector.
- Root cause: `google-genai` 1.65.0 async client creates an `aiohttp.ClientSession` whose connector becomes `None` when called from CLI.
- Fix options: (a) pin `aiohttp<3.13`, (b) use sync genai API in CLI scripts, (c) upgrade `google-genai` if a fix is available.

---

## 5. Historical Context

This evaluation uses the same per-statement extraction results stored in the database from prior extraction runs. For a true single-prompt `extract_full()` evaluation, the CLI async bug must be resolved first. The cumulative F1 from per-statement extraction is the canonical metric used by the admin/auditor dashboards.

**Measurement conditions**: PostgreSQL production database, all 4 discussions have approved GT coded by Patrick, F1 computed via `btcopilot.training.f1_metrics.calculate_cumulative_f1()`.
