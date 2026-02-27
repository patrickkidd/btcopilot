# T7-4: "Build my diagram" button in QML

## Files Modified
- [personalappcontroller.py](../../../familydiagram/pkdiagram/personal/personalappcontroller.py) — simplified `responseReceived` signal (removed `pdp` arg), removed PDP handling from `_sendStatement`, added `extractStarted`/`extractCompleted`/`extractFailed` signals and `extractFull()` slot
- [DiscussView.qml](../../../familydiagram/pkdiagram/resources/qml/Personal/DiscussView.qml) — added "Build my diagram" button, extract signal handlers, replaced inline import overlay with reusable `LoadingOverlay`
- [discussions.py](../../btcopilot/personal/routes/discussions.py) — extract endpoint now returns `pdp` dict in response
- [test_personalappcontroller.py](../../../familydiagram/pkdiagram/tests/personal/test_personalappcontroller.py) — updated `Response` construction (no `pdp` field)
- [test_discussview.py](../../../familydiagram/pkdiagram/tests/personal/test_discussview.py) — updated `responseReceived.emit` call and `Response` construction
- [test_extract_endpoint.py](../../btcopilot/tests/personal/test_extract_endpoint.py) — added assertion for `pdp` in response

## Files Created
- [LoadingOverlay.qml](../../../familydiagram/pkdiagram/resources/qml/Personal/LoadingOverlay.qml) — reusable overlay with spinner, extracted from inline import overlay
- [qmldir](../../../familydiagram/pkdiagram/resources/qml/Personal/qmldir) — registered `LoadingOverlay`

## What Changed

`responseReceived` signal simplified from `(str, dict)` to `(str)` — chat no longer returns PDP data.

`_sendStatement()` `onSuccess` no longer processes PDP from the chat response (there is none).

New `extractFull()` slot POSTs to `/personal/discussions/<id>/extract`, updates local diagram data with returned PDP, emits `pdpChanged` and `extractCompleted`.

"Build my diagram" button appears below the chat ListView when messages exist. Clicking it calls `personalApp.extractFull()`. During extraction, a `LoadingOverlay` with "Building your diagram..." text blocks interaction. On success, the PDP sheet opens automatically.

The inline `importOverlay` Rectangle in DiscussView was replaced with the reusable `Personal.LoadingOverlay` component (DRY).

## Test Results
- Personal tests (btcopilot): **64 passed, 11 skipped, 0 failures**
- Personal tests (familydiagram): **125 passed, 1 skipped, 0 failures**
- Training tests: **309 passed, 3 skipped, 0 failures**

## Notes for Patrick
- The extract endpoint now returns `pdp` dict alongside the counts so the client can update its local state without a full diagram re-fetch.
- The "Build my diagram" button is always visible when chat messages exist. No logic to hide it after first extraction — user can re-extract any time.
- `extractCompleted` auto-opens the PDP sheet so the user immediately sees results.
- The `LoadingOverlay.qml` component is reusable — both journal import and extraction use it now.
