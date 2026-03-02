# T7-3: Remove per-statement extraction from chat.py:ask()

## Files Modified
- [chat.py](../../btcopilot/personal/chat.py) — removed `skip_extraction`, `pdp.update()` call, `pdp_deltas` from Statement, `Response.pdp` field
- [discussions.py](../../btcopilot/personal/routes/discussions.py) — removed `response.pdp` from route responses, cleaned imports
- [prompts.py](../../btcopilot/training/routes/prompts.py) — removed `response.pdp` from test endpoint response
- [synthetic.py](../../btcopilot/tests/personal/synthetic.py) — removed `skip_extraction` kwarg from `ask_fn` call
- [conftest.py](../../btcopilot/tests/personal/conftest.py) — removed `pdp.update` mock from `chat_flow` fixture
- [test_ask.py](../../btcopilot/tests/personal/test_ask.py) — removed PDP assertions, simplified `chat_flow` marker
- [test_e2e_synthetic.py](../../btcopilot/tests/personal/test_e2e_synthetic.py) — rewrote to test new flow: chat -> extract_full -> accept

## What Changed

`ask()` is now purely conversational: save user statement -> generate AI response -> save AI statement -> return. No extraction, no PDP updates, no `pdp_deltas` on statements.

`Response` dataclass now only has `statement: str` (removed `pdp: PDP | None`).

Routes that returned `response.pdp` now only return the statement text.

The `ConversationSimulator` still has a `skip_extraction` field but it's a dead parameter — `ask()` no longer accepts it.

## What Stays
- `pdp.update()` function — still in `pdp.py` for training app batch re-extraction
- `Statement.pdp_deltas` column — still in DB for training app GT coding/auditing
- `ConversationSimulator.skip_extraction` field — dead but harmless, can be cleaned up later

## Test Results
- Personal tests: **64 passed, 11 skipped, 0 failures**
- Training tests: **309 passed, 3 skipped, 0 failures**

## Notes for Patrick
- The chat endpoint no longer returns PDP data. The QML client will need to get PDP data via the T7-2 extract endpoint instead.
- Existing discussions with `pdp_deltas` on statements are unaffected — the data stays in the DB for training.
- `ConversationSimulator.skip_extraction` and `generate_synthetic_discussion.skip_extraction` are now no-ops. Could clean up later but they're harmless.
