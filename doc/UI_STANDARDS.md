# UI standards (BINDING, ruled 2026-09-02)

The phone frame is 400px wide standing in for a ~390pt iPhone, so 1px = 1pt here.
Apple's Human Interface Guidelines and Material 3 are the source; where they differ
we take the stricter number. Nothing ships below these. No exceptions without a ruling.

## Tap targets
- **44 x 44 minimum** for every interactive element (HIG 44pt; Material 48dp — 44 is
  the floor, 48 preferred for primary actions). Applies to icon buttons, chips,
  checkboxes, rows, close glyphs, segment members, tabs.
- The **visual** may be smaller than the target: a 24px glyph inside a 44x44 button is
  correct. The TARGET is never smaller than 44.
- **8px minimum gap** between adjacent targets so a thumb cannot hit two.
- List rows: **≥44 high** for one line, **≥56** for title + secondary line.

## Type scale (never smaller than the floor)
| role | size / weight | use |
|---|---|---|
| screen title | 17 / 600 | title row, page headings |
| body | 17 / 400 | chat bubbles, row titles, field values, settings labels |
| secondary | 15 / 400 | row summaries, helper text, field labels |
| caption | 13 / 400-500 | section headers (uppercase, +0.4 tracking), timestamps, meta |
| **floor** | **13** | nothing renders below 13px, mono included |
- Mono (IBM Plex Mono) is a utility face for data and chips, at 13 or 15, never below 13.
- Line height ≥1.3 for body, ≥1.2 for captions.

## Controls
- Boolean: an **iOS switch, 51 x 31**, inside a ≥44 row — or, where the word "checkbox"
  is called for, a **24 x 24 box** with a 17px label inside a 44 row. Never a native
  unsized checkbox.
- Segmented control: **32 high**, inside a 44 row, each segment ≥44 wide.
- Avatar: **40px circle inside a 44 x 44 target**.
- Text field: **44 high**, 17px value, 16px side padding.
- Icon-only button: 44 x 44, glyph 20–24px.

## Spacing
- Side gutters **16px**. Related items 8px apart, groups 16–24px, section breaks 32px.
- Content never runs closer than 16px to the phone edge.

## Scrolling (must work on phone AND desktop web)
- Every scroll area supports **wheel, trackpad, touch drag, and mouse drag**. Mouse
  drag is not native to an overflow container, so a drag-to-scroll handler is required
  on every scroll area in a mockup.
- `touch-action: pan-y` (or pan-x) on every scroll area; `overscroll-behavior: contain`
  so an inner list never scrolls the page behind it.
- Nothing programmatic may scroll the outer page: focus with `{preventScroll: true}`,
  set `scrollTop` on the container, never `scrollIntoView`.

## Content
- **One home per setting.** A setting appears in exactly one place; a second appearance
  is a deliberate shortcut, named as such, and both write the same value. The only
  ruled shortcut today is speak-replies on the chat view mirroring preferences.
- No surface repeats another surface's list.

## Behaviour
- A control that starts something starts it immediately, not on the next tick of a
  shared clock.
- Every interactive element has a visible pressed state and a keyboard focus ring.
- Page state survives a reload. Every screen rebuilds what the person was looking at from the server on load — an open vote, a selected mode, a selection in progress — so a reload never changes what they see. [Oracle: R-0652]

## How a diagram is opened
- The page holds the open diagram in one place, `web/src/store.ts`: the
  diagram itself (name, owner, whether it is read-only), its record and the
  coach's questions, the newest page of its thread, its sittings, the running
  turn's stream, and the controller that cancels its pending reads.
- One step opens a diagram, `store.open(id)`, for the first load and every
  switch alike. It cancels every read still coming for the diagram before and
  closes its running turn's stream, empties every screen, reads the record, the
  thread, the sittings and the diagram itself by the diagram's id in parallel,
  and draws every screen from what came back. When two opens overlap, only the
  last is drawn. On the first load the server's page supplies the diagram and
  the thread, so only the rest is read.
- Every screen that shows the open diagram registers with `store.watch`: a
  `reset` that puts it back to empty and a `draw` that draws it from the parts
  that changed. It reads the diagram from `store.current()` and never fetches
  the diagram's data on its own; a part read again goes through
  `store.refresh`, and any other request about the open diagram through
  `store.fetch`, which drops the answer if another diagram was opened meanwhile.
- Every request about the open diagram names its id (`?diagram_id=`). The
  server rejects an id the caller may not open with a 404. The account's
  current diagram on the server only decides where the next page load lands.
- What is the open diagram is never copied: the title, the read-only line, the
  ticks in the diagrams list and the product events all read the store.
- The coding screen and the cut picker show a different diagram (the coding's
  own record, the family a cut is placed on) and keep their own reads.
