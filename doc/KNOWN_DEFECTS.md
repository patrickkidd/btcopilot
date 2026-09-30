# Known defects

Rulings the app does not meet yet. Each has a test that asserts the ruling. A visual test is skipped
with the reason "unbuilt ruling, needs a design: <what>", so the suite reports it as skipped, never as
passing; a unit test is marked as an expected failure (vitest `it.fails`, pytest `xfail(strict=True)`).
The mark comes off in the change that fixes it. Kept for the fast-follow PR.

| Ruling | What is wrong today | What it needs |
|---|---|---|
| R-0122 | The defined-self actor turns green while still shaking, before it is stable. | a design: when defined self turns green against the loop the other is battered on |
| R-0123 | The projection arrow carries dashes instead of a smooth gradient. | |
| R-0126 | The functioning move draws a second circle of its own. | |
| R-0127 | Move animations run 8, 10 and 12 seconds instead of one length. | a design: the one loop length every move animation runs |
| R-0187 | The board puts everyone on one ellipse; parents do not stand above their child. | a design: an automatic family arrangement on the board |
| R-0205 | A stored cluster also keeps a title, a summary and start and end dates. | |
| R-0213 | The page behind a cluster's (i) lists every moment in it. | a design: what the picture spot draws behind a cluster's i |
| R-0286 | Triangle views and the outside move carry conflict zigzags; the two-events-side-by-side view still exists. | |
| R-0288 | The triangle view spaces all three people evenly instead of two close and one apart. | |
| R-0291 | In the outside move the two who stay neither move toward each other nor end overlapped. | |
| R-0292 | Triangle positions on the board do not match the ratified drawing. | |
| R-0315 | The coding confirm sheet calls another coder's version a "take". | |
| R-0376 | The page behind a cluster's (i) counts events; the key shift and opening event are not drawn. | a design: what the picture spot draws behind a cluster's i |
| R-0378 | Behind a cluster's (i) the picture spot holds words only. | a design: what the picture spot draws behind a cluster's i |

## Found 2026-09-29 and 30, with no failing test yet

Each needs a test that fails before its fix, citing its ruling once the queued ids are in the store.

| Ruling | What is wrong today | What it needs |
|---|---|---|
| R-0267 | Every session in the meeting's "Put a session on the agenda" list is named "Free Diagram". | each session named by its family |
| — | The coding screen's title is clipped. | |
| — | The reports route's limit of 20 an hour per sender is held in the server's memory, so every restart resets it. | |
| R-0611 (queued) | Someone who joins a notice's audience after it was sent gets it in the app only, never by push or email, so a pricing notice sent by email misses them. | |
| R-0613 (queued) | The bug sheet's "Not a bug" is a live button in the beta and asks the person to decide what is a bug. | the not-send button disabled in the beta |
| R-0096 | The sessions sheet's plain-list ruling lost its only citing test when the session list was removed. | a test, or a supersession |
