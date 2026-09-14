# Walks

Deterministic browser walks over the review screens. Each one signs in with an
invite URL, drives one screen end to end, and fails on a console error, a failed
request, a horizontal scroll, a box past the viewport edge, or a click that did
not change the page.

    node tablewalk.cjs <invite-url> <width> <height> <tag>
    node ballotwalk.cjs <invite-url> <width> <height> <tag>
    node meetingwalk.cjs <invite-url> <width> <height> <tag>
    node structurewalk.cjs <editor-invite> <coder-invite> <admin-invite> <width> <height> <tag>

`WALK_BROWSER` picks the engine (`chromium`, the default, or `webkit`).
`WALK_SHOTS` picks where the screenshots land (default `/tmp/fd362-walks`).

The fixtures each walk expects are set up by the sandbox scripts in
`~/worktrees/fd362-sandbox`, which call these files.
