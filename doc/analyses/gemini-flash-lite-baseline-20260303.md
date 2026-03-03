# Gemini Flash Lite Extraction Baseline — 2026-03-03

## Summary

Evaluated `gemini-2.5-flash-lite` as a cheaper/faster alternative to `gemini-2.5-flash` for PDP extraction. Result: **significant quality degradation across all metrics**. Not viable as a drop-in replacement without prompt re-tuning.

**Note:** The originally requested model `gemini-2.0-flash-lite` returned `404 NOT_FOUND` ("no longer available to new users"). `gemini-2.5-flash-lite` was used instead as the closest available lite variant.

## Model Details

| Property | Value |
|----------|-------|
| Model tested | `gemini-2.5-flash-lite` |
| Baseline model | `gemini-2.5-flash` |
| Eval script | `uv run python -m btcopilot.training.run_prompts_live --model gemini-2.5-flash-lite --detailed` |
| Eval method | Per-statement live re-extraction via `pdp.update()` |
| GT cases | 95 total, 85 evaluated, 10 errors |
| Total runtime | 625 seconds (~10.4 min) |
| Date | 2026-03-03 |

## F1 Scores

| Metric | gemini-2.5-flash-lite | Baseline (gemini-2.5-flash, Feb 2026) | Delta |
|--------|-----------------------|---------------------------------------|-------|
| **People F1** | 0.622 | 0.72 | **-0.098** |
| **Events F1** | 0.103 | 0.29 | **-0.187** |
| **PairBond F1** | N/A (per-statement eval) | 0.33 | — |
| **Aggregate F1** | 0.216 | 0.45 | **-0.234** |
| Symptom F1 | 0.212 | — | — |
| Anxiety F1 | 0.235 | — | — |
| Relationship F1 | 0.235 | — | — |
| Functioning F1 | 0.212 | — | — |

### Methodology Note

The baseline metrics (People=0.72, Events=0.29, PairBond=0.33) were measured using cumulative F1 (`calculate_cumulative_f1()`) on discussion 48. This eval used per-statement F1 (`calculate_statement_f1()`) averaged across all 95 GT cases from 5 discussions. The metrics are not perfectly apples-to-apples but directionally comparable — the lite model is clearly worse on both People and Events extraction.

## Error Breakdown

| Error Type | Count | Details |
|------------|-------|---------|
| PDP validation failures | 7 | Person/Event references to non-existent PDP items (pair_bonds, relationship targets). Retried 4x before failing. |
| Deadline exceeded (504) | 2 | Timeouts on larger conversation contexts (~15K+ chars). |
| Output truncated | 1 | `MAX_TOKENS` hit — LLM response too large for token limit. |
| **Total errors** | **10** | **10.5% error rate** (vs near-0% for gemini-2.5-flash) |

### Key Observations

1. **ID collision warnings were frequent.** The lite model frequently produced negative IDs that collided with existing PDP items, requiring `reassign_delta_ids` fixups. This suggests weaker instruction-following for the negative-ID convention.

2. **Validation failures dominated errors.** 7/10 errors were the model referencing non-existent PDP items (pair_bonds, relationship targets) — the lite model doesn't reliably maintain referential integrity across the extraction schema.

3. **Events F1 collapsed to 0.103.** Most statements got Events F1 = 0.000, meaning the lite model either fails to extract events or extracts wrong ones. The few successful event extractions were on simpler, shorter conversations.

4. **People F1 held up relatively better (0.622 vs 0.72).** The lite model can still identify people mentioned in conversation but struggles with the more complex structured extraction (events, SARF variables, relationships).

5. **Two timeouts on longer conversations.** The lite model may have higher latency on complex prompts or smaller context windows in practice.

## Conclusion

`gemini-2.5-flash-lite` is **not suitable** for PDP extraction at current prompt complexity. The 52% drop in aggregate F1 (0.216 vs 0.45) and 65% drop in Events F1 (0.103 vs 0.29) make it unusable for MVP. Stick with `gemini-2.5-flash` for extraction.

If cost reduction is needed, consider:
- Prompt simplification specifically for the lite model
- Using lite only for People extraction (acceptable F1) and full model for Events
- Waiting for future lite model improvements

## Raw Output

Full per-statement breakdown available by re-running:
```bash
export $(grep -v '^#' ~/.openclaw/.env | xargs)
uv run python -m btcopilot.training.run_prompts_live --model gemini-2.5-flash-lite --detailed
```
