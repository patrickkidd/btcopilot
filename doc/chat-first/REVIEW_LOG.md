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
