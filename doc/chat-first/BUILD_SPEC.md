# Chat-first app — build spec

The design is settled. This is the build. Every decision below is ruled; do not
re-open them. `UI_STANDARDS.md` in this folder is binding for every pixel.

## READ THIS FIRST — reuse, do not reinvent

**`BACKEND_INVENTORY.md` in this folder is required reading before you write a
line.** It maps every existing model, column, relationship, endpoint and helper.
Patrick's instruction: understand the existing structures and schema so nothing
gets reinvented; anything that can be reused must be reused. Corrections that
override anything later in this document:

- **Phase 1 is already committed** (`9f31f76`): `users.preferences` with
  `PrefKey` / `Proactive` / `ChatMode` / `Theme` and `pref` / `prefs` / `set_prefs`
  in `pro/models/preferences.py`; `users.birthdate`; `discussions.title`. Alembic
  head is `e1f2a3b4c5d6` — a further revision sets that as `down_revision`.
- **Event field names come from `schema.py`, not from this document**:
  `description`, `notes`, `location`, `dateTime`, `endDateTime`, `dateCertainty`.
  Where this spec says summary / details / where / when / certainty it means those.
  Committed events are plain dicts carrying Qt datetimes, **not `Event` dataclasses** —
  handle them as the existing code does.
- **Event writes reuse** `DiagramData.add_event`, `Diagram.get_diagram_data` /
  `set_diagram_data`, and `update_with_version_check`. Only the route is new.
- **Sessions reuse** the logic in `personal/routes/discussions.py` (today HMAC-signed
  and unreachable from a browser) and the companion blueprint's existing
  `_create_discussion`. Do **not** add a second creation path. Auto-title belongs
  beside `Discussion.update_summary()`.
- **Preferences endpoint adds no storage and no validation**: `User.prefs()` and
  `User.set_prefs()` already raise on bad keys and values. The route is a thin shell.
- **Account endpoint reuses** `User.licenses` → `Policy` (which already carries name,
  amount, interval and description for six plans, so **beta pricing is a Policy row,
  not a front-end constant**), `User.diagrams` / `free_diagram`, and `as_dict(only=…)`.
- **Sign out reuses** `POST /training/auth/logout`, which clears the same cookie
  session the companion blueprint authenticates against.
- **The picture's server side already exists**: `build_timeline` behind
  `GET /companion/timeline`, including extraction freshness. Extend it; do not
  write a second timeline builder.
- **Genuinely new**: the coach-reference chips (extend `Response`, which both chat
  routes return) and event↔statement traceability (capture the negative→positive id
  mapping that `commit_pdp_items` returns and all four callers currently discard).

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

---

# As built (2026-09-03)

Branch `chat-first-app`. Written after the phase-5 integration walk; this
section, not the text above, is the record of what actually exists.

## What was built

`/companion` serves the whole app behind the training-app login, on the user's
own free diagram.

- **The picture**, three levels, pinned above the chat: the resting wire with a
  box per chapter and an amber `?` in unasked gaps; the chapter, one dot per
  event with labels only for what the coach named or what you tapped; the
  play-by-play, the moves stepped over a circular layout of the family.
- **Coach chips.** The coach marks a reference inline; the server strips the
  markup, resolves it against the diagram, drops anything it cannot aim at, and
  hands the client a structured list. All four kinds work: chapter, an explicit
  set of events, a person, a date range.
- **Two-way traceability.** An event that carries the session that coded it
  offers "coded in …", which switches session and highlights the message.
- **Sessions** are Discussions: a searchable overlay grouped by recency, tap to
  switch, long-press to rename, a button for a new one, auto-titled by the coach
  after the first exchange.
- **Settings**, an iOS-style nested list: profile, coach, appearance, diagrams,
  plan and licences, email and sign-in with sign out. Speak-replies also sits on
  the chat view and writes the same value.
- **Timeline list**, full screen, searchable, grouped by chapter, with an
  in-place editor covering every field `schema.Event` carries, and add and
  delete. Every write takes the diagram's optimistic lock.
- **Schema**: `users.preferences`, `users.birthdate`, `discussions.title`, one
  alembic revision (head `e1f2a3b4c5d6`).

`doc/chat-first/API.md` is the endpoint contract.

## Deviations from the spec above, and why

- **System fonts, not Libre Franklin / IBM Plex Mono.** No CDN is allowed, so
  the mockup's faces are replaced by the system sans and mono at the same sizes.
  The mono advance is unchanged, so label geometry matches.
- **The plan line is a placeholder constant**, per the spec. The backend
  inventory argued for a `Policy` row instead, since `Policy` already carries
  name, amount, interval and description. The licences list already shows the
  real policy name and status either way. Patrick's call which wins.
- **Clusters are now persisted by the server.** `get_diagram_data` read
  `clusters` and `clusterCacheKey`; `set_diagram_data` never wrote them. That
  asymmetry meant a chapter chip could not resolve and chapters could never take
  a cluster's title from anything the server wrote. Both fields are now written,
  which changes the pickle shape by two keys the Personal app already produces.
- **A chip must land in a chapter, not merely exist.** The spec said an
  unresolvable reference is dropped. Existing was not enough: a date range over
  empty years, a person with no events, an undated event and a cluster sitting
  in a silence between chapters all resolved and then did nothing when tapped.
  All four are now dropped server-side, so every chip that reaches the client
  moves the picture.
- **The old lane payload is dead weight.** The DRAWABILITY lane, strip, shelf,
  question and axis data is still computed on every timeline read and still
  covered by about ten tests, but nothing in the page draws it — the picture is
  chapter-and-dot now. Deleting it costs those tests. Flagged, not decided.

## Not done

- **The coach is told to use ids it is never given.** The reference instruction
  says "use only ids that appear in the record you were given", but the record
  handed to the coach (`summarize_committed_state`) carries names, genders,
  partners and life facts — no person, event or cluster ids at all. With the
  stock prompt the coach can therefore only emit a date range; every other kind
  would have to be invented, and invented ids are dropped. The chip machinery is
  correct and tested end to end against canned replies, but a live coach cannot
  drive it until the record carries ids. Not fixed here: it changes the coach's
  production context, and prompt changes carry a mandated measurement process.
- **fdserver must carry the reference instruction.** The default is
  `COACH_REFERENCE_INSTRUCTION` in `btcopilot/personal/prompts.py`. fdserver
  overrides `get_conversation_flow_prompt()` wholesale, so chips are off in
  production until fdserver's prompt carries it. Deliberate fail-safe.
- **Inline chips are 26px tall, under the 44px floor.** The approved mockup
  draws them at 21px. A 44px target inside flowing prose cannot also hold the
  standard's 8px gap between adjacent targets without widening the coach
  bubble's line spacing. Two ruled documents disagree; needs a ruling.
- **Historical coach messages carry no chips.** References come back only on a
  live reply, so chips appear on a new reply and not on a reloaded transcript.
- **Traceability records the discussion, never the statement.** Extraction runs
  over a window of statements, so the statement is not knowable at the commit
  site and stays null rather than guessed. On the deep-rebuild path, items
  accumulated across several discussions are accepted through one discussion's
  route and all take that discussion's id.
- **No swipe-to-dismiss on the sessions overlay.** Tap, Done, rename and new all
  work.
- **Voice is a stored preference only**, per "not in scope tonight". Close-up
  triangle drawings and cluster vignettes are likewise out of scope.
- **Patrick's dev database still needs `alembic upgrade head`** before the page
  can run against it.

## Definition of done

| # | item | state |
|---|---|---|
| 1 | `/companion` serves chat, picture, sessions, settings, timeline CRUD | met |
| 2 | replies carry chips that aim the picture; tapping one works | met mechanically; a live coach cannot emit them until the record carries ids |
| 3 | every event edit round-trips and redraws the picture | met |
| 4 | preferences persist; speak-replies agrees in both places; sign out works | met |
| 5 | 44px targets, 13px type floor, drag and wheel scrolling | met except inline chips at 26px |
| 6 | tests cover the new routes and the CRUD round-trip; the suite passes | met |
| 7 | nothing in this repo carries real personal data | met |
