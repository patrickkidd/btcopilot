# T7-2: Add /personal/discussions/<id>/extract endpoint

## Files Modified
- [discussions.py](../../btcopilot/personal/routes/discussions.py) — added `extract()` route, added `pdp` and `one_result` imports

## Files Created
- [test_extract_endpoint.py](../../btcopilot/tests/personal/test_extract_endpoint.py) — 3 tests

## What Changed

Added `POST /personal/discussions/<id>/extract` endpoint that:
1. Validates ownership and diagram existence
2. Calls `pdp.extract_full(discussion, diagram_data)`
3. Saves resulting PDP via `diagram.set_diagram_data()`
4. Returns `{"success": true, "people_count": N, "events_count": N, "pair_bonds_count": N}`

Synchronous — no Celery. Single gemini call takes ~10-15 sec.

## Test Results
- `uv run pytest btcopilot/btcopilot/tests/personal/test_extract_endpoint.py -x -q`: **3 passed**
- `uv run pytest btcopilot/btcopilot/tests/personal/ -x -q`: **65 passed, 11 skipped, 0 failures**

## Notes for Patrick
- Flask dev server not running, so no live `curl` test. To test: `curl -X POST http://127.0.0.1:8888/personal/discussions/48/extract`
- Returns 404 if discussion not found, 401 if not owned, 400 if no diagram attached.
