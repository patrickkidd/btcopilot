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
   through it" reply); remove the canned reply from the play fixture; prompt rule. OPEN
2. Play-by-play cursor: the semi-opaque green oval overlaps three dots; replace with an
   obvious indicator, e.g. a thin green ring around the selected dot. RULED: no oval;
   the selected dot is drawn on top in the ratified action green; the leader line from
   the dot to the summary is the indicator; no tick.
3. Up/down arrows (symptom/functioning up/down) must never disappear; the animation
   loop fades them; show movement another way. OPEN
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
    → 400; tokens now live as long as the session. OPEN
12. All text in the app is selectable and copyable; only controls keep user-select none.
    OPEN
13. Activity indicator (three animating dots) in the coach bubble from send until the
    first words arrive; never a blank bubble. OPEN
14. Reset: tapping blank wire, blank label band, or the "Family timeline" crumb clears
    the selection to the clusters view; label tap always selects its moment; the
    selected moment's label tap jumps to where it was coded in chat; dots never jump.
    FIXED @d7a9be9 / @5e5c583.
15. The 8890 review database is never seeded, wiped or recreated; backups before
    restarts; migrate only. RULED.
16. Typing indicator = three dots (owner ruling supersedes the mockup's caret). FIXED
    @df0f26c.
17. Symptom-up arrow height = cross height (owner ruling supersedes the ratified 32px).
    OPEN.
18. The agentic tool-call summaries and their formatting apart from the reply are liked
    and preserved; each tool-call line lights the created item on the picture as it
    appears (chatting visibly produces data in real time — "an innovation for
    behavioral health practice"). RULED/OPEN.
19. Invite URLs use hostname turin.local so he can open them from his phone. RULED.
20. First-session/sparse-data: options given (thresholds: stretch ≥3 moments, plain
    wire under 6; life line birth→now; family taking shape as people are named;
    chat-only hook). AWAITING OWNER.
21. People list under the ≡ menu mirroring the timeline list (name, birth year,
    relationship; ordered by birthdate; single-item editor) — proposed, AWAITING
    OWNER.
22. Timeline list discoverability: it lives behind the ≡ button; the owner did not find
    it. OPEN (note only).
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
