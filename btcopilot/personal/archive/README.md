# Archived native Personal app routes

These are the HTTP routes the old Qt Personal app called: signature-authenticated
`/personal/` endpoints for diagrams (base64 pickle get/put, text import, clusters),
discussions (chat, extract, commit-pdp, deep re-extract) and interactions. The Qt
Personal app is superseded by the chat-first browser app (ruling 2026-09-08), so
this blueprint is no longer registered and these routes answer nothing.

Nothing in the running app depends on anything here. The pieces other code did
need were moved out first and are live: discussion creation and chat-speaker sync
in `btcopilot/personal/discussions.py`, interaction reading and writing in
`btcopilot/personal/interactions.py`. The training app imports only models, chat
and prompts from `btcopilot.personal`, never these routes. Extraction itself
(`btcopilot/pdp.py`) is untouched and still reachable from the training app's own
`/training/discussions/<id>/extract`.

Kept for reference while the browser app grows the equivalent surfaces; delete
once nothing is still being read out of it.
