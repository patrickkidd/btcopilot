# Single-Prompt Extraction Plan

**Decision:** 2026-02-24. See `decisions/log.md`.

## Summary

Replace delta-by-delta extraction (25 LLM calls per discussion) with single-prompt extraction (1 call). Full conversation → complete PDP.

## Implementation Tasks

### T7-1: `pdp.extract_full()` (CC, ~2 hr)

New async function in `btcopilot/pdp.py`:

```python
async def extract_full(discussion, diagram_data: DiagramData) -> tuple[PDP, PDPDeltas]:
```

- Builds full conversation via `discussion.conversation_history()` (no `up_to_order` cutoff)
- Assembles prompt: `DATA_EXTRACTION_PROMPT` + `DATA_EXTRACTION_EXAMPLES` + new `DATA_FULL_EXTRACTION_CONTEXT` template
- Calls `_extract_and_validate()` with `large=True`
- Returns complete PDP (deltas applied to empty PDP = the full PDP)

New prompt template `DATA_FULL_EXTRACTION_CONTEXT` in `btcopilot/personal/prompts.py` (and fdserver override):

```
**FULL DISCUSSION EXTRACTION MODE:**
Extract ALL people, events, pair_bonds from the complete transcript below.
This is NOT incremental — extract everything into a single complete result.

**Existing Diagram State:**
{diagram_data}

**FULL DISCUSSION TRANSCRIPT:**
{conversation_history}
```

The existing `DATA_EXTRACTION_PROMPT` (rules) and `DATA_EXTRACTION_EXAMPLES` are reused unchanged. Only the context template changes.

### T7-2: `/personal/discussions/<id>/extract` endpoint (CC, ~1 hr)

New route in `btcopilot/personal/routes.py` (or new file):

- `POST /personal/discussions/<id>/extract`
- Calls `pdp.extract_full(discussion, diagram_data)`
- Stores resulting PDP on `diagram_data.pdp`, saves via `diagram.set_diagram_data()`
- Returns JSON with PDP summary (people count, event count)
- No Celery — synchronous call (single gemini flash call takes ~10-15 sec)

### T7-3: Remove per-statement extraction from `chat.py` (CC, ~30 min)

In `btcopilot/personal/chat.py:ask()`:
- Remove `skip_extraction` parameter
- Remove the `pdp.update()` call block (lines 34-42)
- Remove `pdp_deltas` from Statement creation (line 62)
- `ask()` becomes purely: save user statement → generate AI response → save AI statement → return

### T7-4: "Build my diagram" button in QML (CC+H, ~2 hr)

In `familydiagram/pkdiagram/resources/qml/Personal/DiscussView.qml`:
- Add button (below chat, or in header bar)
- On click: POST to T7-2 endpoint
- On success: populate PDP sheet with returned data
- Loading state while extraction runs (~10-15 sec)

Patrick reviews QML placement and UX.

### T7-5: Generate 3 fresh synthetic discussions (CC, ~30 min)

Use existing `ConversationSimulator` with improved personas. Generate via Celery task or direct call. Target: 3 new discussions with `skip_extraction=True` (chat only, no delta extraction).

### T7-6: Code GT for 3 fresh discussions (H, ~3 hr)

Patrick codes in SARF editor. ~60 min each. Produces approved GT feedback for F1 comparison.

### T7-7: Validate single-prompt F1 on fresh GT (CC, ~30 min)

Run `extract_full()` on T7-5 discussions, compare via `calculate_cumulative_f1()`.

### T7-8: Prompt-tune on single-prompt path (CC+H, ~2 hr)

Iterate on `fdserver/prompts/private_prompts.py` using fresh GT. The single-prompt surface is stable (low variance across runs), so single-run comparisons are meaningful.

## Dependency Order

```
T7-1 → T7-2 → T7-3 (backend complete)
                 ↓
T7-5 → T7-6 → T7-7 → T7-8 (GT + validation, parallel with T7-4)
                 ↓
               T7-4 (QML, needs T7-2 endpoint)
```

**CC can do in parallel:** T7-1 + T7-5 (backend function + synthetic generation)

**Patrick blocks:** T7-6 (GT coding), T7-4 review (QML placement)

## What Stays

- `pdp.update()` — kept for training app batch re-extraction
- `Statement.pdp_deltas` — kept for training app GT coding/auditing
- Celery extraction chain — kept for training app only
- `import_text()` — kept for journal import feature
- All existing validation (`validate_pdp_deltas`, `reassign_delta_ids`) — reused by `extract_full()`

## What Goes (from Personal app path)

- Per-statement extraction during chat
- `skip_extraction` parameter
- Real-time PDP updates during conversation
- Celery dependency for Personal app extraction
