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
