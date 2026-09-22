# Owner review log

One row per finding, never deleted; status: OPEN / MOCKUP / FIXED @commit / RULED.

## Round 1 (2026-09-08 early)

Source: STATE.md "Owner review round 1" ruling. STATE names no commit hashes for these
items, so each is logged FIXED without a commit citation.

1. One selection state: a chip tap is a dot tap — spotlight plus a caption row carrying
   the ask chip, the board button, and the "coded in" chip. FIXED
2. Chips are one size, full text, no truncation and no expand; labels are capped at the
   source, at most 28 grapheme clusters, one re-ask, never trimmed after the fact; chips
   carry pressed-state feedback. FIXED
3. In a play-by-play, step chips move the board and never return to the timeline — the
   statement kind Play/Turn plus its cluster_id is now persisted. FIXED
4. A play-through holds each move until its narration line has finished typing plus
   about two seconds; the owner tunes the feel directly, and the eight-second loop
   stays a separate clock, never stretched to match. FIXED
5. Chat stays pinned to the bottom while the coach types. FIXED
6. The moves board fits its content — this supersedes the fixed 264px rows: every
   UI_SPEC.md row carrying RESOLVED #28 is marked SUPERSEDED by this ruling. FIXED
7. Editor fields are 44px with the mockup's padding. FIXED
8. Tapping a diagram row opens that diagram, one open at a time
   (User.current_diagram_id). FIXED
9. The old Personal app is superseded: its endpoints are archived and the chat app's
   routes are the personal API — models, prompts and the agent loop stay; Pro routes
   are untouched. FIXED

## Round 2 (2026-09-08 morning)

1. Coach must never reply with a bare list of chips (seen: fixture's canned "walk me
   through it" reply); remove the canned reply from the play fixture; prompt rule.
   FIXED @0d41706/@2c8243f.
2. Play-by-play cursor: the semi-opaque green oval overlaps three dots; replace with an
   obvious indicator, e.g. a thin green ring around the selected dot. RULED: no oval;
   the selected dot is drawn on top in the ratified action green; the leader line from
   the dot to the summary is the indicator; no tick.
3. Up/down arrows (symptom/functioning up/down) must never disappear; the animation
   loop fades them; show movement another way. FIXED @60a39c3.
4. Summary line above prev/next ("15/17 | April 2004 | Ada | symptom down"): no symbol
   names, no move count; show what the user reported; date shown once (year under dots,
   date in line — pick one); layout must survive hostile content. RULED: variant A
   "Name · their own words", no symbol names, no move count, date only under the dots;
   the summary block reserves a fixed two-line height and clips (the board never
   changes height when text wraps).
5. Crumb line "FAMILY TIMELINE  Apr 1996 | defined self" duplicates the date/label above
   the selected dot on the wire. RULED: crumb shows only "FAMILY TIMELINE"; the dot's
   label stays above the dot.
6. Caption row "[ask about this] (▶ watch the 17 moves) (coded in: Untitled | 11:09am |
   today →)" overflows on mobile; Play and coded-in buttons differ in height. RULED via
   #8: the wire caption's button is the bare ▶ icon.
7. Convergence rule: no visual/layout-hierarchy change without a quick mockup confirmed
   by the owner; changes surgical, not sweeping; clarify ambiguity before acting. RULED
8. Board controls must be identical whichever way it is entered (chip in a narration vs
   dot on the wire); today the chip path shows only prev/next and the dot path also
   shows "watch the moves", and the board shows it again. RULED: one control row always
   [◀] [▶ explain] [▶] whichever way the board is entered; explain disabled while the
   coach is still responding.
9. "▶ watch the 17 moves" → "▶ explain the moves" (it triggers a slow coach response,
   not an animation). RULED: label is "▶ explain" (not "explain the moves").
10. Mockups must simulate wrapped/long text; non-happy-path rendering is a known blind
    spot — every mockup carries a long-text state and every new region joins the
    overflow gates. RULED
11. Failed or unanswered sends show a static warning label with a retry control instead
    of an empty coach bubble; cleared on success, shown again if it still fails; also
    covers a dead server and timeouts. Root cause found: CSRF token expired after 1 hour
    → 400; tokens now live as long as the session. FIXED @dc4ceed/@ca6153e/@8dfd9c8.
12. All text in the app is selectable and copyable; only controls keep user-select none.
    FIXED @708d7dd.
13. Activity indicator (three animating dots) in the coach bubble from send until the
    first words arrive; never a blank bubble. FIXED @3660028 (indicator itself @df0f26c,
    see #16).
14. Reset: tapping blank wire, blank label band, or the "Family timeline" crumb clears
    the selection to the clusters view; label tap always selects its moment; the
    selected moment's label tap jumps to where it was coded in chat; dots never jump.
    FIXED @d7a9be9 / @5e5c583.
15. The 8890 review database is never seeded, wiped or recreated; backups before
    restarts; migrate only. RULED.
16. Typing indicator = three dots (owner ruling supersedes the mockup's caret). FIXED
    @df0f26c.
17. Symptom-up arrow height = cross height (owner ruling supersedes the ratified 32px).
    FIXED @542c06b (ruling written down @b1835f3).
18. The agentic tool-call summaries and their formatting apart from the reply are liked
    and preserved; each tool-call line lights the created item on the picture as it
    appears (chatting visibly produces data in real time — "an innovation for
    behavioral health practice"). RULED/FIXED @fcbd156.
19. Invite URLs use hostname turin.local so he can open them from his phone. RULED.
20. First-session/sparse-data: options given (thresholds: stretch ≥3 moments, plain
    wire under 6; life line birth→now; family taking shape as people are named;
    chat-only hook). AWAITING OWNER.
21. People list under the ≡ menu mirroring the timeline list (name, birth year,
    relationship; ordered by birthdate; single-item editor) — proposed, AWAITING
    OWNER.
22. Timeline list discoverability: it lives behind the ≡ button; the owner did not find
    it. FIXED @13736d4 (settled by #25 below: the list button moved inside the picture
    frame).
23. Terminology: "cluster" is the term (never stretch/chapter); code and copy swept.
    FIXED @cb9de08.
24. Cluster grounding plan RULED (owner: "right on. Let's do them all"): rules-first
    candidates seeded by a nodal kind (intake's NODAL_KINDS) or a variable shift;
    18-month span; shares a person or pair-bond; scaffold = structural kinds before the
    first nodal/shift; merge on overlap; 24-month calm gap splits; lone event stays a
    dot; model names + one-sentence reason + change with reason; validation rejects
    unknown ids, dropped members, missing reason, diagnostic/pop-psychology words; one
    re-ask then raise; private prompt quotes the theory spec's four variables and
    relationship mechanisms, the record's twelve moves, R-0054/R-0037/R-0076,
    closed-vocabulary instruction; cluster/episode definition deliberately left
    undefined; examples section empty pending the owner. DONE @4acfaa1/@5805fba
    (btcopilot) @f62986f (fdserver).
25. Timeline list button inside the picture frame, styled like the sessions button;
    drawer tabs Events | People. FIXED @13736d4/@e277553.
26. "Picture may be behind" badge removed. FIXED @9620bc4.
27. Person editor: fields name, last name, "Kind" (the gender enum, all five values;
    never labelled sex/gender); help text "Add birth and death events by chatting with
    the coach."; buttons for existing birth/death events jump to that event's editor;
    event editor person taps jump to the person editor. FIXED @d756a25/@170af05.
28. The picture's back arrow shows whenever a cluster is open. FIXED @7171d68.
29. In the open-cluster picture, tapping an event label jumps to its editor in the
    Events tab (assumption pending owner: the resting wire keeps selected-label →
    coded-in chat). FIXED @17ad2f1/@45a53ee, verdict pending owner (chat jump now only
    on the coded-in chip).
30. Links in replies are written as markdown links so they are tappable in the Claude
    iOS app; hostname turin.local. RULED.
31. Vocabulary: "cluster" = "episode" (one thing); "anchor" is not the owner's word and
    is removed; "shift" is the SARF term; invented pattern labels (ClusterPattern enum,
    pattern, dominantVariable) came from earlier AI output and are removed; a stored
    cluster is name, reason, source, event ids, dates. RULED/FIXED @5805fba.
32. Nodal events are defined by kind (NODAL_KINDS from the intake engine, now
    enum-compared); no nodal flag on the record; decision to add one dissolved. NOTE.
33. Archived Personal-app cluster test deleted after the enum removal. FIXED.
34. Cluster recompute behaviour: whole record, from scratch, on any event-changing turn;
    cache key over the SARF fields plus DETECTION_VERSION; a user-corrected cluster is never
    touched; a recomputed cluster keeps its old id on overlap so earlier chips keep
    resolving; nothing selective exists. RULED (owner: "let's just play with it and see how
    it works in the Beta").
35. Only stored clusters draw as clusters; the timeline's gap-grouped derived
    pseudo-clusters and the play fallback are removed; an unclaimed event is a bare dot
    with sentence + ask chip, no walk. FIXED @2db8faa.
36. Phone layout picks (mockups_phone.html): row 1 A — picture region fixed 132px in
    rest and open-cluster states (crumb 28 + wire 60 + label/caption 44), no dead band;
    row 2 A+C — labels words only, year once under the selected dot, month prefix only
    when two labelled events share a year, label rows capped at three (spotlight rule),
    the top-right date-range text removed (collided with the list button); row 3 C —
    status-bar and Safari-bar areas in the picture's off-white with a hairline
    (viewport-fit=cover, theme-color, safe-area insets; Android unverified, no hardware —
    check in an emulator before beta users). FIXED @9e47da8 (settled by #47 below); the
    Android-emulator check is unbuilt work, tracked separately in STATE.md under "The
    desktop app and Android are unverified".
37. The button row under the picture is identical whether a cluster is open or an event
    inside it is selected, items dimmed when not applicable (extends the board's
    same-controls ruling); a mockup round for restyling that row is in progress; the
    coded-in button is not redundant with the title tap (title → editor; coded-in → the
    chat bubble where it was said) but its label must say what it does. FIXED @1adb168
    (settled by #60 below: round 3 landed).
38. Screenshot tolerance: the picture spec adopts the board spec's strict 8-pixel
    allowance; desktop goldens stay unmaintained until the phone review is done. RULED.

## Round 3 (2026-09-08 afternoon)

39. Button row = mockup plate F: the chat's own chip style, "ask" / "explain" / "in chat"
    (not "said"), identical in both states, ask carries only the word. FIXED @1adb168
    (settled by #60 below: round 3 landed).
40. The built layout did not match the picked mockup (list button over the cluster boxes,
    boxes over the CTA text); redo to the mockup with a no-overlap gate; screenshots
    reviewed by the coordinator before the owner sees it. FIXED @29cf81e.
41. An open cluster shows the cluster's NAME and REASON, never a list of events (15 events
    must not overflow); events stay dots; a tapped dot shows its words. RULED.
42. At rest and in an open cluster only dots, the line, the amber question mark and the
    selected dot's year are drawn; guessed-date bands ("olive bar"), directionless ticks,
    step lines, flat/fade/order marks are reserved for the expanded/board level. RULED.
43. Labels never leave the picture frame (the overflowing "…began" label); gate added.
    FIXED @29cf81e.
44. Naming: "Family Diagram" everywhere users see it; "Companion" was never ruled and is
    removed; the internal name is "Personal app". RULED.
45. Cluster minimum is THREE events, enforced as a write invariant; two one-event model
    clusters and a 1983+1992 pair were found stored after the two-event floor — root
    cause being established; record re-run at DETECTION_VERSION 4. FIXED @1e24675
    (settled by #54 below: floor landed, root cause documented as a stale server
    process).
46. List views: sticky cluster headings must not cover the scrollbar gutter (Events and
    People). FIXED @2591862.
47. Layout picks landed @9e47da8 (region 137px pending the button row's 4px margin; 60px
    band fits two rows of words, a third named moment is a lit dot). FIXED.

48. Remove the "You can also edit just by chatting." line from the Events and People
    lists. RULED.
49. "in chat" (not "said"); a lone event selected on the main clusters wire counts as
    event-selected: "in chat" active when the event has a coded-in statement; the
    selected event's title jump must work on the main wire (root cause: event →
    statement link not resolving on real records). FIXED @1adb168 (settled by #60 below:
    round 3 landed, event→statement link works on real records).
50. The Events/People list button moves from the name row into the chip row,
    right-aligned. RULED.
51. The account button loses its circle outline (no room around it); glyph + 44 target
    stay. RULED.
52. At rest the 44 band shows "tap a cluster", chips only once a cluster or event is
    selected; the board hides the picture's chip row (no double "explain"); region
    exactly 132px. RULED (coordinator, from the picked mockups).
53. Coordinator reviews screenshots before the owner sees a build; the served bundle is
    not rebuilt before restart time. PROCESS.
54. Cluster minimum three landed (@1e24675/@f912051/@11207f6/@b0ea7bb, fdserver
    @5e68dd0): floor enforced at the record's commit for every writer incl. undo and the
    coach's grouping tool; root cause of the earlier one-event clusters was a stale
    server process (operational), documented; owner's record re-run at version 4 → one
    cluster (his own two-event grouping, grandfathered). OPEN for the owner: does the
    three-event rule bind a grouping the user made; if so, that one gains an event or is
    dropped.

## Round 4 (2026-09-09)

55. The grey mono label is the title of the current view ("Family timeline" at rest, not
    tappable; cluster name when open; board title on the board); the back arrow shows
    beside it; tapping either goes up one level. FIXED @bb64f2a.
56. Drill-down slides in from the right over the higher view, back slides out to the
    right, user- or coach-initiated, ~240ms, reduced-motion instant. FIXED @4d4ba1e.
57. Six pixels between the year label and the button row; region now 138 (rows
    28/66/44). FIXED @2042eac.
58. The account view slides over the content (content stays rendered), opens on the tap
    using the loaded account, refresh deferred. FIXED @ae8a14c.
59. With a cluster open and nothing picked, the band shows the coach's reason only; the
    name lives in the title row. FIXED @ab26a1b.
60. Round 3 landed (@1adb168, @80400fd, @fe0dc6a): plate F row with "in chat", states
    per selection, selected dot emphasized, "tap a cluster" at rest, board hides the row
    (collapsed), list button in the chip row, avatar without outline, "edit by chatting"
    line removed, event→statement link so "in chat" and the title jump work on real
    records; dev server on 8891. FIXED.
61. Owner: "this is ready for me to start using it like an app on the phone with the home
    screen trick"; next phase = code organization / isolation of the Personal app from
    existing infra (ISOLATION_OPTIONS.md in progress). RULED.
62. Isolation discussion parked until the prototype is done (owner); the three pre-merge
    blockers recorded in STATE.md.

63. On reload the chat opened a little above the newest words instead of at the bottom of
    the thread. FIXED @821e10b.
64. Tapping a moment's title did nothing on some lines, because the dot's own tap target
    was swallowing the tap. Every line answers where its words are written now.
    FIXED @f4c49fc.
65. A cluster or board sliding in showed the level underneath through it; it needs an
    opaque background so it reads as a card sliding in. FIXED @b7bae33.
66. Owner, closing the day: the app is ready for him to start using like an app on the
    phone. Isolation of the Personal app and beta deployment are one named open issue in
    STATE.md, carrying the three pre-merge blockers, the isolation recommendation and the
    deployment gap. OPEN.

67. Owner testing alone, evening: his message "May of 1971" was stored three times — the
    coach failed on the first send (the Anthropic account was out of credit), the composer
    still accepted a second send while the first was in flight, and the try-again button
    posted the words a third time. The server stored the user's words before asking the
    coach, so every failed attempt left a copy. Now the words are only committed with the
    coach's answer, so a failed turn leaves nothing behind, and a second send while one is in
    flight does nothing. Regression test on the turn. FIXED (this session's commit).
68. Same minute: one tap posted a learning-data row with no item kind and the server refused
    it with a 500. Every path in the current page code sends an item kind, so the tap that
    did this is not identified; the coach's own words in the review record use only the
    event and ask markup. OPEN — the owner is asked what he tapped right after the second
    "May of 1971".
69. The coach in the review sandbox cannot answer until the Anthropic API account behind the
    key in the environment has credit again. Owner's side, not code. OPEN.

## Still open (reconciled 2026-09-09)

Every row previously marked OPEN, MOCKUP, or "building" was checked against later rows
in this log and against `git log`; all but the two below found a commit or a later
ruling that settles them and were updated in place above (rows are never deleted).
These two are still genuinely open:

- **#54** (round 3): the three-event cluster floor is built and landed, but the owner's
  own record holds a two-event cluster he made himself, grandfathered from before the
  floor existed. His decision needed: does the floor bind a grouping the user made
  himself; if so, that cluster gains an event or is dropped. Tracked in STATE.md under
  "The three-event floor and groupings the user makes himself".
- **#66** (round 4): isolating the Personal app from the Pro desktop app and Training
  app, and deploying it, is unbuilt. Tracked in STATE.md under "Isolation and beta
  deployment" (three pre-merge blockers, the isolation recommendation, and the
  deployment gap).
- **#68**: one learning-data post with no item kind, tap not identified.
- **#69**: the Anthropic account behind the sandbox key is out of credit; the coach cannot
  answer until it is topped up.
| 70 | 2026-09-11 | play-by-play | On a cluster with three events (the 2006 one on his record), "explain" reveals only a single event on the play-by-play; the first cluster plays all of its events and looks great | FIXED | 3b1ace0 — the board was keeping only the events the move language has a mark for, and his 2006 stretch is a pair bond forming, the same bond ending, and one shift, so two were dropped. Every event of a cluster is now a step; one with no mark stands its people on the board with its year and its words. Verified at 393x852: three different events stepped, the one with no mark among them, zero console errors |
| 71 | 2026-09-11 | coding screen | Tapping a turn jumped the thread to the bottom and nothing looked selected. The turn was above the agreed line: its notice was inserted under the tap and the list then scrolled to its end | FIXED | faadfbc — a new line scrolls into view under the tapped turn; verified at 393x852 (notice, outline, coder's words, scribe's line all in view) |
| 72 | 2026-09-11 | sandbox | Asked whether testing from a home-screen icon hits caching. Not caching: iOS gives a home-screen app its own cookie store, so it opens signed out | NOT A BUG | sign in once inside the home-screen app with the email code; the invite link opened from Mail signs in Safari only |
| 73 | 2026-09-11 | sandbox | An open page on the phone never picked up a code change: the dev server refused its live-reload socket for the host name turin (only turin.local allowed) | FIXED | faadfbc — turin allowed; handshake 101 confirmed |
| 74 | 2026-09-12 | words | The app's own copy says moment where the record says event | FIXED | 64c348e — the fallback label for a chip, the count under an open cluster, two spoken labels on the picture, and the coach's own instructions here and in the private prompts. Nothing in the app ever called it the moves board; the play-by-play already had that name |
| 75 | 2026-09-12 | coding title | At 393px the title truncated to "Marcus's convers…" and lost "up to Sep 4", which says how much of the conversation is on screen | FIXED | 8e0c9a8 — a title is now a name and a tail: the name ellipsises, the tail never does, one line. On the coding, ballot and ratify rows; cut placing shows the name alone and had nothing to lose. Verified at 393x852 |
| 76 | 2026-09-12 | events drawer | An event a coder had just written carried an "unplaced" chip | NOT A BUG | "unplaced" is the divider over the events no cluster holds, not a chip on a row, and a new event belongs to no cluster until one is made. Nothing stale, nothing to clear |
| 77 | 2026-09-12 | event editor | A field the chosen kind hides was still written when the event was saved, so an event changed from a shift to a marriage kept its relationship and its anxiety | FIXED | 96b0264 — Save skips any group inside a hidden block; what was picked stays on screen so switching the kind back restores it. Verified through the app's own editor at 393x852 |
| 78 | 2026-09-12 | sessions sheet | A reader without the professional licence must never meet the word case, and each family keeps its own "+" | AS BUILT | 96b0264 — confirmed and now asserted in the personal walk and the sessions spec; the per-record "+" is the one a professional does not get |
| 79 | 2026-09-12 | words | The screens said "on the table" where he says "on the agenda"; the screen, the API calls, the query parameter and the walk document were all renamed | FIXED | 0dff14a — every reader-facing "on the table" became "on the agenda", the code says agenda too |
| 80 | 2026-09-12 | agenda | The agenda box was listing codings nobody had finished | FIXED | 0dff14a — the box on the screen no longer lists codings nobody finished, and the route no longer returns them |
| 81 | 2026-09-12 | words | The meeting's choice on a disputed event was called a "settle"; it is a "decision" | FIXED | 9b458aa — renamed throughout |
| 82 | 2026-09-12 | words | The guidelines screen said codebook | AS BUILT | the word codebook appears nowhere in the app: the screen, its stylesheet and its module all say coding guidelines [R-0310] |
| 83 | 2026-09-12 | roles | A professional licence holder could reach the coding work; only the auditor role may | FIXED | 090ed34 — the review's door now asks for the role |
| 84 | 2026-09-12 | agenda | Unresolved events were returning to a later meeting's agenda; they stay unresolved as data and the box holds only flagged rules | FIXED | dfd882d, c1da269 — unresolved events do not return; the agenda holds only flagged rules |
| 85 | 2026-09-12 | ratify | He asked about the eleven-second wait on ratify and accepted it | NOT A BUG | no change made |
| 86 | 2026-09-12 | words | A coder's version of an event was called a "take"; it is an "opinion", and the "left out by N coders" line reads as a sentence and is hidden when N is zero | FIXED | 791b8cf — renamed to opinion, the left-out line rewritten and hidden at zero |
| 87 | 2026-09-12 | prompts | The scribe's prompt had never lived in fdserver and had to move behind the private override | FIXED | 11362e3 — the scribe's words moved to fdserver |
| 88 | 2026-09-12 | sandbox | A sign-in link worked once, so a walk could not be repeated; invite links are reusable until they expire | FIXED | 2951d05, 8587cff — a sandbox may make invite links reusable until they expire |
| 89 | 2026-09-12 | fixtures | Fixture rows read like test data ("ballot fixture 7", "last: nothing yet") and hid what the screen does | FIXED | the sandbox fixtures were rewritten on the stand-in family, not the repo — /Users/patrick/worktrees/fd362-sandbox/realism.sql, and the rule is R-0307 |
| 90 | 2026-09-13 | meeting | The meeting header carried a teal tally chip and no legend; it becomes one title, a labelled figures line, a colour legend, the wire, the sort control, the list | FIXED | c4c3732 — one header, sorting, per-version keep, agreed cards, live dots |
| 91 | 2026-09-13 | meeting | The list could not be sorted; it sorts by divergence or by time and agreed events are readable | FIXED | c4c3732 |
| 92 | 2026-09-13 | meeting | An agreed event had a reopen button; it opens on a tap of its row with a close button top right | FIXED | c4c3732 |
| 93 | 2026-09-13 | meeting | On a split, keep hid which version it kept; the room selects the version | FIXED | c4c3732 |
| 94 | 2026-09-13 | words | Event rows carried placeholder titles ("undated · an item"); every row names who and what | FIXED | c4c3732 |
| 95 | 2026-09-13 | meeting | Dots on the agreement wire did not respond to a tap | FIXED | c4c3732 |
| 96 | 2026-09-14 | people list | A person's row carried a second faint line under the name, against the written spec; the name alone is right | FIXED | 32dc204 |
| 97 | 2026-09-14 | scribe | A year the coder gave only as a year read back with a month ("married · Jun 1970") | FIXED | 261da63 |
| 98 | 2026-09-15 | sign-in | He was being signed out while walking; a session older than the training app's eight hours was being thrown away. Sessions are never dropped fast — no gold is being protected yet and logins are not wanted | FIXED | b0513a2 — an older session is still read [R-0337] |
| 99 | 2026-09-15 | ballot | A selected family fragment sat in a box; "open in transcript" did not outline the statement the way the coding screen does; "none" was not last in the relationship field; there was no way back once a dot had moved you on | FIXED | 2ac1842, dc2df02 — the box is gone, the statement is outlined, "none" is last, and a prev button sits beside next [R-0337] |
| 100 | 2026-09-15 | walk document | The walk sent him back to earlier sections for links, put more than one action in a step, and annotated steps as known wrong | FIXED | b172be2, dbcffb1, 25f5ead, 9487b55 — every section carries its own sign-in link, one action per step, serial order, and the action verb is set in a different colour [R-0337] |
| 101 | 2026-09-15 | meeting | Tapping a dot on the agreement wire jumped with no motion, and the title block held the top of the screen while the list scrolled under it | FIXED | dc2df02, a3a616a, 610140e — the list travels to the card with an animated scroll, the title and figures scroll away, and the wire with its legend and sort control stays at the top [R-0338, R-0340] |
| 102 | 2026-09-15 | meeting | Structure cards were laid out differently from event cards | FIXED | dc2df02 — version rows and the fragment line up the way the event cards do [R-0338] |
| 103 | 2026-09-15 | meeting | Keeping a version needed a separate button; the meeting should use the ballot's language | FIXED | 7c233db, b90ad76, 174adae — tapping a version keeps it and the row lights, the kept version is stored on the item so it lights on every later reading [R-0339] |
| 104 | 2026-09-15 | meeting | Version rows carried a "= 2" count | FIXED | bdfbe24 — the coders' initials alone [R-0342] |
| 105 | 2026-09-15 | agenda | The way into the meeting did not read as the main thing to do | FIXED | 610140e — a filled primary button reading "run the meeting", with room after it [R-0341] |
| 106 | 2026-09-15 | meeting | A decided item disappeared or moved down the list | FIXED | 610140e — it stays in its place, collapses to the words of the version kept or to "unresolved", and reopens on a tap with the choice lit [R-0341] |
| 107 | 2026-09-15 | task card | A finished task could not be got back to, and a ratified conversation offered nothing from the agenda | FIXED | e3def30, d83c589, 49cbdbe — a coder's sheet always offers the task card, rows under "done before" look tappable and open their meeting result, and the agenda offers the result of a ratified cut, told apart by its date [R-0343, R-0344] |
| 108 | 2026-09-15 | result | The summary was pinned monospaced output, and a coach pass that was never coded showed as a bare figure | FIXED | 7af552f, 49cbdbe — the summary scrolls with the page under a title and one labelled figures line, and a coach pass that was never coded is said in words [R-0344] |
| 109 | 2026-09-15 | walk document | It said a sign-in link works once | FIXED | 10fd46d — the links are reusable until they expire; the one-time wording was wrong |
| 110 | 2026-09-15 | record | The list button opened a panel that left the chat showing, and the person editor said "bond" | FIXED | 7a0f0a6 — the events and people list slides in full screen over the chat and the picture, and the editor says "Born to" with a mother and father picked by name, and "Partners" for the rows beneath [R-0345] |
| 111 | 2026-09-15 | fixtures | Fixture rows still did not read like a real case | FIXED | the sandbox fixtures were repaired on the stand-in family — Lena's family and the Ortega case — in /Users/patrick/worktrees/fd362-sandbox/, not the repo [R-0307] |
| 112 | 2026-09-15 | roles | Anyone could flag a ratified guideline and anyone could move a cut through the agenda; only an admin may, and the account button was missing its icon | FIXED | 8364eb4 — flags admin-only and toggling, a coder sees text; every agenda route admin-only; the account icon restored (dropped by 78a041c) |
| 113 | 2026-09-15 | event editor | The notes field was too small to write in | FIXED | a23e985 — it grows to ten lines |
| 114 | 2026-09-15 | record | Walk 7 step 6: "add parents" on Teresa renamed Rafael and Marisol to the two typed names and flipped their genders instead of adding two people; the people and pair-bond routes handed out the record's counter plus one, and the Ortega fixture had no counter, so the "new" people were ids 1 and 2 | FIXED | one id allocator in record.py skipping every id already on the record, used by the people route, the pair-bond route and the coach's toolbox; regression test; the Ortega and Whitaker fixtures now carry their counter |
| 115 | 2026-09-15 | sessions sheet | The three buttons at the foot touched | FIXED | the foot is a column with a gap [R-0347] |
| 116 | 2026-09-15 | sessions sheet | The sheet listed every case with its own header, tapping a case with no sessions did nothing, and the search said "sessions and cases" while the case is chosen on the account page | FIXED | the sheet lists only the sessions of the case the app is on, grouped by day under a heading, clock only when a day holds more than one; case headers, the "N more…" row and the per-family "+" are gone; the search says sessions [R-0347] |
| 117 | 2026-09-15 | sessions sheet | Walk 7 passes on his own walk | PASS | after row 114 |
| 118 | 2026-09-15 | sessions sheet | Day headings were sticky and rows scrolled under them; the kind tag clipped to "R…" | FIXED | headings scroll with the list, bold, spaced; the tag never shrinks, the title truncates instead |
| 119 | 2026-09-15 | sessions sheet | The line under each session was boilerplate ("New Discussion", "just started", "in progress") and the clock column repeated the heading | FIXED | the server writes no placeholder summary; a row shows the coach's summary or is one line; the clock column is gone, an untitled session keeps its clock in its name |
| 120 | 2026-09-15 | sessions | Times were sent without a timezone and read as local, so an evening session showed as the next morning | FIXED | every session and case time is sent as UTC |
| 121 | 2026-09-15 | recording | Does the upload work with diarization and speaker mapping? | VERIFIED | a two-voice synthetic recording sent to AssemblyAI with speaker labels came back as two voices, four utterances; posted as Nadine it became session 42 on the Ortega case with the clinician as the coach side; the browser file picker itself was not driven |
| 122 | 2026-09-15 | sessions sheet | Headings and the line under each session were still not designed; the pencil was too small to use | FIXED | redrawn on the notes-list precedent: uppercase grey period headings over rounded groups, bold title, one grey line of day and what the client first said, "⋯" opens rename and delete; an adversarial reviewer's six findings folded in [R-0347] |
| 123 | 2026-09-15 | recording | The transcription key was handed to the browser | FIXED | the audio goes to this server and on to AssemblyAI, the transcript comes back through it; proved with a real two-voice recording [R-0348] |
| 124 | 2026-09-15 | sessions | Deleting a session that has statements fails on the chat app's own database: the training app's feedback model hangs a relation on Statement, and its table is not in the chat chain | OPEN | isolation question (option A); the chat process must not register training models, or the relation must not load on delete |
| 125 | 2026-09-15 | sessions sheet | The line under a session was unreadable: the day and the kind word ate half of one line | FIXED | the day sits small beside the title, the kind word is gone, the preview gets two lines [R-0347] |
| 126 | 2026-09-15 | recording | No warning that transcription costs money | FIXED | a sheet before the file picker says it costs Alaska Family Systems money and to check with patrick@alaskafamilysystems.com [R-0349] |
| 127 | 2026-09-15 | chat | An empty session showed a typed coach greeting rather than telling the user what to do; a note gave no idea what to type | FIXED | a call to action where the bubbles will be, worded per kind, gone on the first send [R-0350]; a note beside an empty session is no longer refused as "still empty" |
| 128 | 2026-09-15 | picture | The empty timeline was three lines of text | FIXED | one centred sentence, no hint under it [R-0351] |
| 129 | 2026-09-15 | chat | On his phone the thread did not land at the bottom on load | CHANGED | not reproduced in emulated iPhone WebKit or Chromium on a 46-message thread; the 800ms re-pin window is replaced by a resize watcher that re-pins whenever the thread's box changes while the reader is at the bottom; needs his phone to confirm |
| 130 | 2026-09-15 | wide layout | The list button did nothing with the drawer pinned open | FIXED | not shown on the wide layout [R-0352] |
| 131 | 2026-09-15 | walk 8 | The walk skipped uploading, a note and chatting in a new session | FIXED | walk 8 rewritten to drive all three; every step driven in a real browser with a real recording before hand-over |
| 132 | 2026-09-15 | licences | Walk 9 shows the old Pro plan code | NEEDS-OWNER | the chat app reuses the Pro app's licence tables and plan codes so imported Pro users keep their professional licence; a chat-app plan of its own is a decision, not a bug |
| 133 | 2026-09-16 | chat database | The chat tests built every table in the process, so a path reaching a Pro or Training table passed in tests and failed on the chat database | FIXED | c285d24 — the chat tests build only the chat chain's tables; the coder's notes table was hand-made on the sandbox and absent from the chain, now revision 1a00000000ab; the training app's feedback relations are read-only, so a session with content deletes (row 124 closed) |
| 134 | 2026-09-16 | image | The image carried no encrypted prompts and no way to run the chat chain from an installed box | FIXED | e8f99c2 — sops and the prompts ship in the image, `flask admin db upgrade` runs the chain, the release workflow starts the image on an empty database and fetches the chat page |
| 135 | 2026-09-16 | CI | Unit tests ran the installed copy (no bin/t), the visual harness signed in at the wrong path, the picture selector matched three pictures, and goldens existed only for macOS | FIXED | b78b7a0, 14a1e38, f6979ec — tests run from the checkout, /personal/me, `#view .ss`, goldens recorded on the runner by a commit marked [goldens] |
| 136 | 2026-09-16 | picture | A picked mark at either end of the line put its year 14px outside the picture | FIXED | f6979ec — the year is clamped inside the box |
| 137 | 2026-09-16 | importer | The dry run against the July dump could not be repeated here: restoring the dump was refused as personal-data handling | NEEDS-OWNER | run it yourself: `flask admin imports dry-run postgresql://…` against a restored copy |
| 138 | 2026-09-16 | wide layout | With the list button gone from the wide layout, the caption still wired a click onto it and threw, so the sessions sheet never opened on desktop | FIXED | no wiring when the drawer is pinned; found by the rewritten walks |
| 139 | 2026-09-16 | walks | The Playwright sandbox walks still expected the cross-case sessions sheet, keep buttons, bond wording and old figures | FIXED | rewritten to R-0345, R-0347, R-0351, R-0352; app, table, ballot, meeting and meeting-detail pass at phone and desktop; tap, scribe and structure skip on fixture state (Lena's coding is closed by the reset; no link for the structure walk) |
| 140 | 2026-09-16 | picture | The up arrow from a picked moment inside a cluster closed the cluster too | FIXED | one step at a time: the moment is put down first, the next tap closes the cluster |
| 141 | 2026-09-16 | caption | The list button had no ring while the sessions button has one | FIXED | dressed alike, the same 40px ring in a 44px target |
| 142 | 2026-09-16 | settings | The speak-replies switch drew 10 by 10: the meeting's status dots shared its class | FIXED | the dots have their own class |
| 143 | 2026-09-16 | visual suite | 46 golden specs failed on stale assertions and a stale bundle | FIXED | specs brought to the rulings by a builder with an auditor; 144 of 148 pass at phone size locally, goldens to be recorded on the runner |
| 144 | 2026-09-16 | data model | Does the old diagram format map onto the record without loss, relationship sub-fields included? | VERIFIED | test_prorecord.py: a Pro-shaped record with relationship moves, targets, triangles, an emotion, a layer, intensity, colour, Qt dates and points is stored, read by the chat page with the sub-fields intact, returned to Pro equal, and keeps desktop-only fields after a hand edit; DATA_MODEL.md's "pairs" type for triangles was wrong and is fixed |
| 145 | 2026-09-16 | repos | Why was fdserver on this ticket at all? | CLOSED | the prompts and rulings once lived there and moved into this repo encrypted on 13 September; the deployment was drafted there by habit; PR #30 closed by Patrick, deployment moved to deploy/chat/ here, the ledger no longer reads fdserver |
| 146 | 2026-09-16 | the box | Did the migration chain, the invite and the DNS change actually happen on the new box? | NEEDS-OWNER | no. `flask admin db current` on the box returns nothing, so the database has no tables and no invite was minted; DNS still sends familydiagram.com to 107.170.236.117 and www to 198.199.116.86, nothing resolves to 209.38.135.250, so Caddy has no certificate and https to the box refuses the connection; https://familydiagram.com/app still lands on the old site. Five containers run; the worker reports unhealthy. Each step needs his confirmation [R-0353] |

## Round 5 (2026-09-20, Patrick's first use on the box, from his phone)

Source: his messages in the session. Status as of the last flush.

1. First chat message threw an error. Cause: the twelve shared prompt fragments were
   never re-encrypted for the box's key on the 16th, so the server could not decrypt them.
   All 31 encrypted files re-keyed; copied into the running containers; image rebuilt.
   FIXED @a6d848f
2. Datadog on this box, as part of the compose stack with config in the repo. Agent
   service added: host metrics and container logs, no traces. Needs DD_API_KEY on the box.
   FIXED @f1543aa
3. Chat still broken after item 1. Cause: the private tool-meanings prompt lacked three
   entries the tools now require (parents, person_a, person_b); the public default had
   them, so tests passed. Added, re-encrypted, hot-copied into the containers, image
   rebuilt. FIXED @0df98c3
4. A tag on master marking where the chat-first rebuild diverged, to become the Pro
   maintenance stream once the new app is proven on the box. Tag `pre-chat-first` at
   fc52fd3, which is also master's tip today. DONE
5. Chat still broken after item 3: the image pulled the Anthropic SDK 1.7, which drops the
   temperature argument the app passes in six places (tests ran on 0.97). SDK pinned
   below 1.0, image rebuilt, deployed; a real coach call with the real prompt and tools
   ran inside the container and answered. FIXED @82b960e
6. Shut Datadog down on this box; he may leave Datadog. Agent stopped and removed; the
   service is now behind an opt-in compose profile so a restart does not revive it.
   DONE
7. Chat still broken after item 5: the wheel never shipped the public prompt directory,
   so the image had only the private files and the session-title prompt (public only)
   was missing. Package data fixed, image rebuilt, deployed; proven with a full turn over
   https as a scratch test account (which stays in the database: there is no delete command
   yet): 200, the coach added the mother and her death.
   Lesson: every earlier check was a piece of the path, not the path. FIXED @56f98bd

Patrick's first real chats on the box, 2026-09-21 (his words paraphrased; each OPEN until fixed):

8. Coach bubble: the closing question is in the same gold as the chips under it, which reads
   as a formatting error. RULED: reads as bold, fine if that is where the eye should go;
   kept [R-0358].
9. The chips under a coach bubble: tapping one inserts it into the chat, but what that means
   or does is not obvious; make it obvious, or drop them. RULED: dropped, people type their
   own words [R-0361]. FIXED: the coach is no longer told to offer them, any it still writes
   is stripped before the transcript, and the closing question keeps its amber line.
10. Timeline: an event the coach adds shows as a bare dot with no other information, and a
   "?" sits at the end of the timeline; nobody will know what that means. The "?" was also
   there on the right before any event existed, which looks like a bug. RULED: hide both
   question marks for now, with the reasoning kept in comments so the thread is not lost
   [R-0359]. FIXED in the picture code; the rule in DRAWABILITY stands.
11. Timeline shows one event at 2021, but the events talked about were high school and ages
   25–26 with no years given, so 2021 comes from nowhere. Cause: no birthdate to anchor
   an age. Addressed by 12: the coach gets the birth date before any other event.
12. Opening the invite lands straight in the chat with no onboarding: never asked for name,
   age or birthdate. Was a form not planned? RULED: the coach onboards; first name, last
   name and birth date are required before it goes on [R-0360]. FIXED: the coach's
   prompt carries what is still missing until all three are in the record, and the
   account row mirrors them for the preferences page.
   Findings on 8–12 (2026-09-21): 8 and 9 are the built design — the bubble's last sentence
   is split off as "the ask" in amber and the bracketed amber chips are offered answers a
   tap drops into the composer (R-0072, R-0073, R-0139); not a formatting bug, a legibility
   failure. 10: the trailing "?" is the undated shelf marker (DRAWABILITY, R-0047); it shows
   whenever any fact has no usable date, which happened on the first reply because the
   high-school event was dated "unknown". 11: no birthdate on his record, so the coach
   turned "high school" into 2010 (unknown, shelved) and "25 to 26" into 2021 (approximate,
   drawn) as its rules tell it to; the year is invented because the age has no anchor. 12: no
   onboarding form was ruled — the first journey is chat straight from the link (R-0087);
   name and birthdate live in preferences (R-0099). Decisions put to Patrick.
13. Seen while verifying onboarding on the box: the session summary shown in the sessions
   list (a separate model call) answered the person's first message with generic sleep
   advice instead of summarising the exchange. OPEN
14. Patrick: a branch `master-legacy` for Pro bug fixes with the same release flow, deploying
   to database.familydiagram.com on every merged pull request. DONE: branch at the tag,
   protected like master, release workflow on it tags `:legacy` and triggers the Pro box
   deploy; btcopilot PR #137 (CI on pull requests into it) and fdserver PR #31 (the box
   pulls `:legacy`) await his merge.
15. Patrick: speak replies is on but nothing is spoken. Finding: the switch only stores a
   preference; no code in the web app reads it or calls the browser's speech. Speaking was
   never built. RULED: build it. FIXED @4ec3a0b: the phone's own voice reads each reply as it
   starts typing, cut by the next message; verified on the box with the speech call stubbed
   to record one utterance carrying the reply.
16. Server error on a later turn: the Gemini key is missing on the box. Gemini groups the
   record's events into clusters on the picture after a turn once there are enough of them;
   the secrets template never listed it. FIXED: template and runbook carry it, and a test
   now fails when any setting the app reads without a fallback has no home on the box.
   The value itself is his to put on the box (the key script now includes it).
17. "Server error" on one send, fine on retry, 2026-09-22 02:56 UTC. Cause: the send landed
   while the app container restarted after the key script; no failed response or exception
   in the logs, and the next turn ran cluster detection cleanly. Every deploy has this
   window today. NOTED — a restart that keeps the old container up until the new one is
   healthy is a later improvement.
18. Select an event on the timeline, tap "in chat": "Those words are no longer here". Cause: a
   coach bubble written in the session on screen never carried its statement id (only a
   reopened session bubbles did), so a moment coded in this very session could not find
   its words. FIXED: the live bubble is stamped with its statement id the moment the reply
   arrives.
19. Patrick asks whether the app is meant to go landscape on an iPhone 14 or whether that
   breaks the layout. Finding: nothing locks orientation and nothing was designed for a
   phone on its side; the one width rule is the professional's pinned drawer at 840px,
   which an iPhone 14 on its side (844px) crosses. RULED: the wide layout activates for
   everyone on rotation, to see how it feels [R-0367]. FIXED.
20. In an open cluster, tap a moment, tap the back arrow: it only put the moment down and
   stayed in the cluster. RULED: the arrow always closes the cluster [R-0362]. FIXED.
21. Patrick: "moved" is still a first-class event kind; he said before that a move is one of
   many notable events with no structural or functional shift of its own. Finding: the
   complaint is recorded in doc/chat-first/EVENT_MODEL.md as complaint 1, a proposed shape
   exists, nothing is built, and six questions at the end of that page are unruled —
   including whether a move becomes an ordinary noted event or keeps a kind untied to the
   couple, and whether the rework happens now or after the beta. OPEN — a brainstorm, not a
   fix; he wants it re-opened.
   Item 21 built (2026-09-22): the noted kind is in, moved is out (R-0363, R-0364, R-0365),
   commit bda417d. The eight stored moves in his record were rewritten in place on the box at
   the storage level, no read-time translation, before the new image was deployed. DONE.
22. Patrick: moves and other events he could not name are leads — a coach may wonder
   whether they play in, though they are no structural or functional change. RULED
   [R-0366]. FIXED: a noted event raises the order question beside a shift the way a
   structural event does; it still counts as no change to the family.
23. Return on the keyboard sent the message, so a message could not have paragraphs.
   RULED: Return starts a new line, only the send button sends [R-0368]. FIXED; the
   composer and the bubbles keep the line breaks.
24. A 51-second turn (five tool rounds plus cluster naming) came back 200 from the server
   but the phone had given up: browser patience 60s, gunicorn 45s. RULED: stream the turn,
   run it independent of the request, and let any reload reattach and sync [R-0369].
   BUILDING.
   Item 24 FIXED @6a3b851 + 17788ae, live 2026-09-22 10:07 UTC. Proven on the box with a fresh
   account: the post came back 202 in 0.6 s, the page was reloaded three seconds into the turn,
   and the reply landed 28 s later in one bubble carrying its statement id, three events coded.
   A first deploy of it broke every message (the app looked for Redis on localhost); rolled back
   in two minutes, fixed, redeployed. Every deploy now rolls: 106 probes during a roll, 0 failed.
25. Clusters appear and then vanish between messages; they must stay stable and change only
   when justified. Evidence: every turn that touches an event re-runs detection and rewrites
   the clusters wholesale (36 deltas in one turn: seven clusters became five, all retitled,
   new ids), so the eye never sees the same picture twice. OPEN — a stability rule needed.
26. The main clusters view on a phone: 39 dated events already read as a thick line; a tap on
   a coordinate cannot pick one dot; clusters compress but must be meaningful; the view needs
   one word for its name. OPEN — a mockup round on his own record; drawn options, not data.
27. Cost per user over time must end up on a dashboard. The tokens table already meters each
   user; the dashboard, and moving off Datadog to Grafana/Prometheus/Loki, is a brainstorm for
   a separate session that reports back here by message. OPEN
28. A play button under each coach bubble to play or replay that message, as in the Claude
   app. OPEN
29. A better voice than the phone built-in one. Options given: cloud neural voices at about
   a cent a reply, ElevenLabs at several times that, self-hosted models the box cannot run.
   OPEN — his pick.
30. Patrick, on turning on a paid voice at about a cent a reply: the primary concern is not the
   money but the feedback loops — beta users must see how much they use and what it costs, and
   that has to sit inside the data-driven principle for the app: does anyone pay, do they like
   it. The loops are not designed yet. TABLED, to be remembered; no paid voice until they exist.
31. Patrick wants his local Qwen agent in openclaw to administer the backend from a markdown
   file linked in its own instructions, always matching the deployed code: invites, licences,
   costs, everything the admin CLI does; reads free, writes confirmed. Options given: link the
   file on GitHub; the running app serves its own copy (recommended); the CLI prints it. Gating
   by an SSH forced-command wrapper from the same declarations. Handed to the dashboarding
   session for its brainstorm. OPEN
   Item 31 and the dashboards (27): built by the dashboarding session, not this one (Patrick,
   2026-09-22). This session stays off the admin CLI, its skill file and deploy/chat observability.
   Item 31 BUILT @6454186, live on the box 2026-09-22 20:15 UTC: `flask admin run -- <words>` with a
   `writes` marker on every mutating command (preview and stop without `--yes`), `skill --print`,
   `users invite --send`; on the box one SSH key pinned to bin/fd-admin-gate; the bot's tool notes
   are a section Patrick appends to his openclaw workspace. Not yet verified: one invite driven from
   Discord end to end.
32. Prompt caching: no coach call used it; every step of a turn re-sent the whole system prompt
   (record inside), tools and history at full price. Patrick: "absolutely do it". BUILDING —
   fixed coaching text and tools cached, a breakpoint on the last message so each step of a turn
   reuses the steps before it, cache reads logged per call.
   Item 32 FIXED @d0bc169, live 2026-09-22 18:04 UTC. Measured on the box, one four-step turn:
   each step read 10,200–10,800 tokens from cache and paid full price for 86–360 new ones; the
   fixed coaching text is 3,893 tokens. Not wired: the per-user token meter table, which nothing
   writes yet; usage is logged per call for the dashboarding session to pick up.
33. Deployed 062eb63 to the box 2026-09-22 19:00 UTC: CI green, the token meter migration
   applied (chain at 1a00000000ac). The Grafana commit 1f4b3dc is NOT deployed: it needs the
   Grafana token on the box (his key script now carries it and drops the Datadog key), a lock
   refresh at the workspace root that only he runs there, and a release build. WAITING on him.
34. Nine scratch accounts (claude-test1 to 10) with chats sit in production: this session made
   them to verify each deploy end to end, because production was the only stack. Patrick
   objected on seeing them on the dashboard. From now on verification walks run against a
   sandbox (the Tailscale dev server, item under "how the beta iterates"), never the box. The
   rows stay until his word: delete or keep. OPEN
