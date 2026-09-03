# Chat-first app — build spec

The design is settled. This is the build. Every decision below is ruled; do not
re-open them. `UI_STANDARDS.md` in this folder is binding for every pixel.

**Confidential data rule (hard):** no real names, emails, case identifiers, or
clinical content in this repo, in commits, in fixtures, or in tests. Test fixtures
use invented names. The approved visual mockup lives OUTSIDE this repo at
`~/theapp/btcopilot-sources/fd-corpus/design/crowded-chapter/timeline-converged.html`
— read it for pixel reference, never copy its data in.

## What this is

One page, served by the training app at `/companion`, behind the existing login.
A coach you talk to, with a picture of your family's timeline pinned above the chat.
The coach drives: it decides what the picture shows by placing chips in its own
replies. Browsing is secondary and already-cheap.

## Ruled behaviour

### The picture (three levels, pinned above the chat)
1. **Resting wire (~78px).** A line, one cluster box per episode, dots inside,
   an amber `?` in gaps nobody has asked about. Tap a cluster to open it.
2. **Chapter (~158px).** One dot per event on a line, years at the corners.
   **No labels drawn by default** — this is the fix for crowding. Words appear in
   two ways only:
   - the coach's latest message lights the 2–3 events it names (bright dot + one
     label each), everything else stays a dim dot;
   - tapping any dot shows that one event's words.
   Dots that share a date stack vertically. At very high density dots draw at
   reduced opacity so crowding reads as darkness rather than overlap.
3. **Play-by-play (~264px).** The moves played step by step on the simple circular
   layout of people. Keep the ratified move vocabulary and one action-green.
   **Priority: it must feel right** — no gaps between a step and its symbol, no
   dead beats, no styling jumps. Patrick refines this by chatting with it.

### Coach chips (the core mechanism)
The coach's reply may reference the record. A reference renders as an inline chip
in the coach's bubble; tapping it aims the picture. Four target kinds:
`chapter`, `events` (an explicit set), `person`, `range` (dates).
Implement the server-side contract now: the model emits references in its reply,
the server parses them into structured chips, the client renders and resolves them.
Ship a deterministic fallback: if the reply names no reference, no chips appear.
The real prompt lives in the private layer; add the reference instruction to the
default prompt here and note the fdserver override in the PR.

### Two-way traceability
Every event may carry the discussion and statement that coded it. Tapping an event
offers "coded in …", which jumps to that session and highlights the message.
Chips in chat aim the picture; this is the return path.

### Sessions (= Discussions)
A round button at the left of the message bar opens a searchable, swipeable
overlay of past sessions, grouped by recency, showing an auto title and the coach's
one-line summary. Tap to switch; long-press or a menu renames; new session.
`Discussion.summary` exists; **add a `title` column** (nullable; auto-titled by the
coach after the first exchange, hand-editable).

### App-level views
A 44px row under the status bar: the current view's title on the left, the account
avatar on the right. Tapping the avatar opens an **iOS-settings-style nested list**
— a root list whose rows push their own pages with a back chevron, each page naming
itself in the title row. It must reach:
- **Profile**: first name, last name (already on `User`), **birthdate (new column)**.
- **Coach**: speak replies; how often the coach may message first (default: never);
  voice or text.
- **Appearance**: theme (system / light / dark).
- **Your diagrams**: the user's diagrams; with many, a searchable switcher.
- **Plan and licenses**: from `License` / `Policy`. Beta pricing text is a
  placeholder constant — Patrick supplies the numbers.
- **Email and sign-in**: username/email and method. **Sign out.**
A **speak-replies checkbox sits on the chat view itself**, mirroring the preference;
both write the same value.

### Timeline list (full CRUD)
A button in the picture area opens a **full-screen** list (not an overlay) with a
back chevron in the title row and a search field. Rows are grouped by cluster under
a **sticky divider** showing the year range and the count. A row's second line uses
abbreviated codes so it never overflows: `S↑ A↑ F= R conflict→<person> △<person>`.
Tapping a row opens an editor **in place** that edits everything
`btcopilot.schema.Event` carries, following `familydiagram/pkdiagram/resources/qml/EventForm.qml`:
- kind (shift, birth, adopted, bonded, married, separated, divorced, moved, death);
- person; **with** (shown only for bonded/married/separated/divorced); **child**
  (only for birth/adopted);
- summary, details, where;
- when, optional end, certainty (unknown / approximate / certain);
- **only when kind is shift**: Δ symptom, Δ anxiety, Δ functioning, Δ relationship —
  four peers under one heading.
- The **targets picker appears only once a relationship kind is chosen**, and its
  label changes with the kind: conflict/distance → "Other(s)"; overfunctioning →
  "Underfunctioner(s)"; underfunctioning → "Overfunctioner(s)"; projection →
  "Focused"; inside → "Inside(s)"; outside → "Inside(s) 1"; toward → "To"; away →
  "From"; defined-self → "In relation to"; otherwise "Person 2".
- The **triangles picker appears only for inside** (labelled "Outside(s)") **and
  outside** (labelled "Inside(s) 2").
- Saving drops values that no longer apply (switching a shift to a death clears the
  shift values rather than hiding them).
Add and delete as well as edit. Writes go through `Diagram.set_diagram_data`.

## Backend wiring (all of it — this is the point)

| piece | how |
|---|---|
| login | the existing `auth` blueprint; the page is behind it; sign out ends the session |
| sessions | `Discussion` (+ new `title`); list / switch / rename / create endpoints |
| chat | the existing `ask()` pipeline through the companion blueprint |
| the picture | `Diagram.get_diagram_data()` → the existing timeline builder |
| event CRUD | load `DiagramData`, mutate, `set_diagram_data`, commit |
| preferences | a `preferences` JSON column on `User` + a `birthdate` column |
| diagrams | `User.diagrams`, `User.free_diagram` |
| licenses / plan | `User.licenses` → `Policy` |
| schema changes | one alembic revision under `alembic/versions` |

Endpoints are REST per resource, not one endpoint per field.

## Definition of done

1. Signed in as a normal user, `/companion` serves the whole app: chat, picture,
   sessions, settings, timeline list with full CRUD.
2. The coach's replies carry chips that aim the picture; tapping one works.
3. Every event edit round-trips to the database and redraws the picture.
4. Preferences persist; speak-replies agrees in both places; sign out works.
5. `UI_STANDARDS.md` holds: 44px targets, 13px type floor, drag and wheel scrolling.
6. Tests cover the new routes and the CRUD round-trip; the existing suite still passes.
7. Nothing in this repo carries real personal data.

## Not in scope tonight
Close-up triangle drawings and cluster vignettes in the play-by-play (later, on the
real family diagram); the real beta pricing numbers; voice.
