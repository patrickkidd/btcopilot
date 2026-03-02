# T7-1: Implement pdp.extract_full()

## Files Modified
- [pdp.py](../../btcopilot/pdp.py) — added `extract_full()` function (lines 562-596)
- [prompts.py](../../btcopilot/personal/prompts.py) — added `DATA_FULL_EXTRACTION_CONTEXT` template, added override in prompt mechanism
- [private_prompts.py](../../../fdserver/prompts/private_prompts.py) — added matching `DATA_FULL_EXTRACTION_CONTEXT` override

## Files Created
- [test_extract_full.py](../../btcopilot/tests/personal/test_extract_full.py) — 3 unit tests

## What Changed

Added `extract_full(discussion, diagram_data)` async function to `pdp.py`. It:
1. Gets full conversation history via `discussion.conversation_history()` (no `up_to_order` cutoff)
2. Assembles prompt using `DATA_EXTRACTION_PROMPT` + `DATA_EXTRACTION_EXAMPLES` + new `DATA_FULL_EXTRACTION_CONTEXT`
3. Calls `_extract_and_validate(prompt, diagram_data, "extract_full", large=True)` — reuses all existing validation/retry logic
4. Returns `(PDP, PDPDeltas)` tuple

The new `DATA_FULL_EXTRACTION_CONTEXT` template tells the model to extract ALL data from the complete transcript (not incremental). It includes `{diagram_data}` for dedup against committed items and `{conversation_history}` for the full transcript.

Both btcopilot default and fdserver override files include the new template. The prompt override mechanism in `prompts.py` was updated to load `DATA_FULL_EXTRACTION_CONTEXT` from private prompts.

## Test Results
- `uv run pytest btcopilot/btcopilot/tests/personal/test_extract_full.py -x -q`: **3 passed**
- `uv run pytest btcopilot/btcopilot/tests/personal/ -x -q`: **62 passed, 11 skipped, 0 failures**

## Smoke Test
Not run yet — requires DB access with discussion 48. The function is structurally identical to the working `/tmp/full_discussion_extract.py` script, just using `_extract_and_validate()` for proper validation/retry.

## Notes for Patrick
- The prompt template is intentionally minimal — same structure as the working `/tmp/full_discussion_extract.py`. Production tuning can happen in fdserver's override.
- `extract_full()` reuses 100% of existing validation (`reassign_delta_ids`, `validate_pdp_deltas`, retry logic).
- The `large=True` flag routes to the larger Gemini model as intended.
