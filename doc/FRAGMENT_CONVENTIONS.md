# Fragment drawing conventions

How the chat app draws a **family fragment**: one person in the middle, the bond between
their parents above them, their own bond or bonds beside them, the children under each
bond. Never a whole diagram, never a third generation out to the sides.

Ground truth is the desktop app's drawing code under
`/Users/patrick/theapp/familydiagram/pkdiagram/`. The written specification
`btcopilot/doc/FAMILY_DIAGRAM_VISUAL_SPEC.md` is second. **Where they disagree the code
wins**, and the line says so. One line per convention, each with its source.

Everywhere this sheet once said a rule was open, Patrick has now ruled (R-0325) and the
renderer draws that one way only — there are no drawing options left in the code, only the
size the picture is drawn at. `doc/mockups/fragment.html` is the record of the
twelve rulings; each row there names what was ruled.

## Base unit and phone size

- The desktop person box is 100 x 100 units, centred on the person's own origin
  (`util.py:326`, `PERSON_RECT = QRectF(-50, -50, 100, 100)`).
- Everything else in the code is a fraction of that box, so **one base unit `u` = the
  person box**, and every measure below is given as a fraction of `u`.
- On a 393-wide phone, draw at **`u` = 44px**. Three boxes plus two sibling gaps is 308px,
  which leaves a 42px margin each side; three stacked generations is also 308px tall.
- Default person size is "Large" = scale 1.25 on the desktop (`util.py:327-334`,
  `util.py:651-657`). The fragment ignores the five person sizes and draws everyone at
  one size; size on the desktop means emphasis, not fact.
- Stroke is 3 desktop units at scale 1.0 (`util.py:401`, `PEN`), i.e. 0.03 `u` → **1.5px**
  on the phone, round cap, round join. Child lines use a flat cap
  (`scene/childof.py:70`).

## Colour tokens (the chat app's `web/src/theme.css`)

- Every person shape and every structural line is `var(--ink)`. The desktop pen is plain
  black (`util.py:401`); `--ink` is the app's near-black and its dark-mode inverse.
- A person or bond the record is unsure about is `var(--faint)`.
- A question mark on the fragment is `var(--ask)`, matching the timeline's one question
  colour (`doc/DRAWABILITY.md`, "the question language").
- Fragment background is `var(--panel)`; no fills inside shapes (the desktop sets a
  transparent brush, `scene/marriage.py:457`).

## People

- **Male: a square**, the full box (`scene/person.py:226`, `path.addRect(rect)`).
- **Female: a circle** inscribed in the same box, so a square and a circle have the same
  bounding box (`scene/person.py:250`, `path.addEllipse(rect)`).
- **Unknown or unrecorded gender: the box with fully rounded corners**, 40% relative
  radius (`scene/person.py:264`, `path.addRoundedRect(rect, 40, 40, Qt.RelativeSize)`).
  **Code vs spec**: the spec says a "?" is shown inside this shape (spec §1, Basic
  Shapes); the code draws no "?" at all. **Ruled**: no "?" inside the shape. The amber
  question mark of the drawability rules keeps its single meaning — the fragment is asking
  you something.
- **Miscarriage and abortion: one triangle, and the same triangle for both**
  (`scene/person.py:255-261`, both kinds take the identical path). **Code vs spec**: the
  spec says the triangle points *down* (spec §1); the code draws apex at top centre, base
  along the bottom, i.e. pointing **up**. **Ruled**: point at the top.
- Nothing in the code distinguishes a miscarriage from an abortion visually; the
  difference lives in the record's wording only. `doc/plans/REPRODUCTIVE_SCENARIOS.md`
  asks for a number of weeks inside the triangle and for separate stillbirth and
  failed-fertility marks — none of that is built, so the fragment does not draw it.
- **The person in the middle of the fragment is drawn twice**: the shape, plus a second
  shape of the same kind 10 desktop units larger on every side, i.e. 0.1 `u`
  (`scene/person.py:228-231` and `252-256`, the `primary` branch). The spec calls this the
  index person and says roughly 10% larger (spec §1) — the same thing.
- **Deceased: an X through the shape**, corner to corner
  (`scene/person.py:1255-1259`). When an age is shown inside, the X becomes four short
  corner ticks each 30% of the box width, so the number stays readable
  (`scene/person.py:1262-1270`). Death also hard-stops everything else about that person
  (`doc/DRAWABILITY.md`, rule 5).
- **Age**, when known, is a number centred inside the shape (spec §1); the desktop uses
  age at death for a deceased person (`scene/person.py:517`).
- The name sits under the shape. **Ruled**: the given name only, on one line, cut with a
  trailing ellipsis at the box width plus one sibling gap; the desktop has no rule for this
  and the phone width forces one.

## The bond between two partners

- **A pair bond is a squared U**: straight down from the bottom centre of one partner,
  across, and straight back up to the bottom centre of the other
  (`scene/marriage.py:107-121`, `Marriage.pathFor`). Every corner is a right angle.
- **Depth of the U** is the person box height ÷ 2.2 = **0.45 `u`** below the lower of the
  two partners (`scene/marriage.py:113-115`). On the phone that is 20px.
- **Width of the U** is whatever the two partners' spacing is; the fragment places
  partners two box widths apart, centre to centre, so the U is **2 `u`** wide.
- When the two partners sit at different heights, the crossbar takes the **lower**
  partner's level plus the depth (`scene/marriage.py:114`, the `max` of the two).
- **Which partner takes which side**: **ruled** male on the left, female on the right; with
  no man in the bond, the older person on the left, then the order the record holds them in.
  The code has no such rule — the bond is drawn between wherever the two people already sit —
  so this is the fragment's own.
- **A bond that is married is a solid crossbar; a bond that is only bonded, or has no
  recorded marriage, is dashed** (`scene/marriage.py:288-300`). Matches spec §2.
- **A divorce makes the line solid again**, not dashed (`scene/marriage.py:291-292`): once
  divorced, the bond reads as a marriage that ended. This is in the code only; the spec
  does not mention it.
- **Separation: one slash. Divorce: two.** (`scene/marriage.py:58-66`.) The slashes are a
  separate movable mark, sitting by default 75 desktop units — **0.75 `u`** — to the right
  of the bond's centre (`scene/marriage.py:30`), not at the middle of the bar.
- Each slash rises 40% of the box height (0.4 `u`) from a point 15% of the box height
  below the bar (`scene/marriage.py:53-55`). The second slash of a divorce starts 10% of a
  box width to the right of the first (`scene/marriage.py:63`).
- **Code vs spec on the slash angle**: the spec says the slashes are diagonal and lean
  toward the parent with custody (spec §2). In the code the lean is 20% of a box width
  **only when custody is recorded**; with no custody the run is zero and the slashes are
  **vertical** (`scene/marriage.py:41-54`). **Ruled**: straight up-and-down marks. The
  fragment never leans them, because nothing about custody was recorded.
- **A bond that ended vs one that continues**: nothing in the geometry says "ended" beyond
  the slashes. Separation and divorce marks appear only once their date has passed
  (`scene/marriage.py:303-320`), so a bond with no slashes and no end date reads as
  continuing.
- Dates go beside the crossbar, prefixed `b.` bonded, `m.` married, `s.` separated,
  `d.` divorced (`scene/marriage.py:554-562`). The fragment shows at most the two that
  matter — the start and the end — because there is no room for four.

## Children

- **A child hangs from the crossbar, not from the sides of the U**
  (`scene/childof.py:26-46`): the line runs from the **top centre** of the child's shape
  (`scene/childof.py:16-23`) up to the bar's own level.
- If the child sits within the bar's horizontal span the line is vertical; if outside, the
  x is clamped to the nearer end of the bar, so the line runs **diagonally to that corner**
  (`scene/childof.py:40-43`). Matches spec §3.
- **Children are laid out left to right oldest to youngest** when birth dates are known,
  and in record order otherwise (spec §5, Birth Order). The code imposes no order; it
  draws lines to wherever the children already sit. The spec wins here because the code
  leaves it undefined.
- **Sibling spacing** is two box widths centre to centre, **2 `u`** (spec §5), **ruled** as
  drawn; the code has no spacing rule at all, positions being the user's.
- **Generation gap** is twice the box height, **2 `u`** (spec §4); again the spec only.
  On the phone that is 88px between rows.
- **Adopted: the child's line is dashed** (`scene/childof.py:139-140`); the shape is
  unchanged. Matches spec §3. Note the conflict of intent: `REPRODUCTIVE_SCENARIOS.md`
  records an older preference for a **solid** line to every parent, with dashes reserved for
  chosen parents. **Ruled**: the dashed line stays.
- **Twins and other multiple births**: the siblings born together are joined by a
  horizontal line across their top centres, and one single line rises from the middle of
  that line to the parents' crossbar (`scene/multiplebirth.py:54-64`). Each child's own
  short line runs from its top to the shared line.
- The shared line sits the box height ÷ 2.9 = **0.34 `u`** above the highest of those
  children (`scene/multiplebirth.py:157-176`). **Code vs spec**: the spec says it sits at
  the midpoint between the children and the parents' bar (spec §3). **Ruled**: the fixed
  rise above the children.
- **A child whose parents' bond is not in the record** has nothing to hang from. The code
  has no case for this; a child line always needs a bond object
  (`scene/childof.py:34-46`). **Ruled**: the child stands alone on the children's row — no
  bar, no line rising into nothing, no question mark. Nothing is drawn that the record does
  not hold.

## One person with more than one bond

- **Ruled**: the bond lines overlap side to side, each one reaching further right than the
  one before it, with the earliest bond on the left and the latest on the right. The order is
  by the date the bond started, and by the order the record holds the bonds in when no date
  is known. The code has no layout engine and no such rule; this is the fragment's own.
- The person in the middle stays fixed and the partners arrange around them (spec §5, the
  anchor). In a fragment the middle person is always the anchor by definition.
- Each bond keeps its own U at its own depth, and each bond's children hang under that
  bond's own crossbar. Bonds do not share a crossbar.
- **A parent or partner nobody named**: **ruled** — that person is a person in the record
  like any other, named for their relation ("Marcus's father", "Corinne's mother"), and the
  fragment draws them exactly like anybody else, with that name under the shape. The renderer
  never invents a shape and never draws half a bond: **putting that person into the record is
  the scribe's and the coach's work**, part of extraction, not part of drawing. A bond that
  reaches the renderer with a side missing is a fault in the record, and the renderer fails on
  it rather than drawing around it.

## Hostile cases the gallery must draw

Every case below must be drawn, at 393px wide and at 1280px wide.

1. One bond with children under it.
2. A bond that ended: one slash for a separation, two for a divorce, drawn right of centre.
3. Two bonds in sequence for the middle person, with children under each.
4. A partner nobody named, held in the record under a generic name.
5. A parent nobody named, held in the record under a generic name.
6. A deceased person, with an age and without one (four corner ticks vs a full X).
7. A miscarriage among the children.
8. An abortion among the children, next to the miscarriage, to show they draw identically.
9. Twins: the shared horizontal line and the single riser.
10. An adopted child: the dashed line.
11. A person with no gender recorded: the rounded box, and no "?" inside it.
12. A child whose parents' bond is not in the record, standing alone.
13. Two versions of one person that disagree, drawn side by side.
14. A 40-character name under a shape.
15. A name in non-Latin characters, and one with combining marks.
16. All of the above at once in a single fragment, to prove the layout does not collide.
