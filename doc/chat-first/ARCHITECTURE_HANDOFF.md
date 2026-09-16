# Architecture session — handoff brief

Everything below came out of the session that designed and built the chat-first app
(2026-09-02/03). It is scope and open questions for a dedicated architecture session,
not a plan. Nothing here is ruled unless it says so.

## The vision this has to serve (STATE.md "The product (ruled)" — read it, not this summary)

We are finishing what was started on the drawing board, not designing a new product.
The architecture is judged by whether it can carry these, all previously ruled:

- **"A coach who never forgets your family."** The family record — structure plus
  timeline — is the coach's visible, touchable memory, **growing for years**. Longevity
  is an architectural requirement, not a feature.
- **Conversation drives everything AND manual tweaking stays**: chat tool calls control
  everything in the app with **full bidirectional reactivity** (oracle R-0055). This is
  the single strongest constraint on the write path — the agent and the browser must be
  clients of the same thing, or reactivity is faked.
- **Two clocks**: chat is the event clock and is never rewritten; the record is the
  state clock and corrections change it. A document plus an append-only command log is
  the natural shape of exactly this — the session should notice that the two-clocks
  ruling already half-specifies the storage design.
- **One picture pinned above the chat**, strip-small at rest, always current. "Always
  current" across an agent worker, a browser and background extraction is a concurrency
  requirement.
- **No modes, one agent**; coaching, app-help, corrections and journaling are registers
  routed from context. Corrections are ordinary turns, which is why a correction must be
  as cheap and reversible as any other write.
- **Lanes are queries over the existing schema, not entities.** Whatever replaces the
  format must keep that true, or lanes become tables and the product becomes a data tool.
- **Loop engineering**: every tap, chip, correction and drill is collected. The log is
  the obvious home for that signal too.
- **The acceptance test is the felt shift**, one or two brain-rearranging correlations
  per user — not coverage, not a dataset. Coverage serves only better coach questions and
  the timeline's own correlations.
- Drawing and asking rules stay canonical in [../DRAWABILITY.md](../DRAWABILITY.md).
- **The human oracle binds all agentic development**; the store is IP and lives in
  fdserver. Architecture decisions get ruling ids like everything else.

Working order was ruled too: filter → document the nature of the data → model-optimized
visual choices → build. The chat-first build jumped ahead of that deliberately, to get
something testable. The architecture session is where it rejoins the plan.

**Scope of that session: the parent repo with worktrees in btcopilot and fdserver.**
fdserver holds the prompts and the valuable IP and must be in scope. familydiagram is
out — that trajectory ends with the Qt front end, and the only tie back to it is the
one-shot converter.

## What is already ruled (from STATE.md — confirm, don't re-derive)

- Diagram becomes a JSON document plus an append-only command log; one module mutates
  it; browser and agent are clients of the same endpoint; the agent loop runs in a
  worker streaming patches over server-sent events; the client keeps a small reducer
  for optimistic drags; per-turn undo via compare-and-set inverses.
- Front end: one Vite/TypeScript SVG page, phone and desktop, installed as a PWA.
- Migration from the Pro pickles: a one-shot converter, gated on positions exact and
  every count difference explained; hard cutover, old Pro becomes export-only.
- Release: PR checks → tag → one image → GHCR → one compose pull.

## What we measured this session

**The record already splits in two.** Conversations, users, licences and preferences
are ordinary relational rows and are fine as they are. Only the diagram itself —
people, events, relationships — lives in the pickled blob. A symptom worth
remembering: the sessions list looked broken while the picture worked, because the
two come from completely different places.

**The new code is barely welded to the old storage.** ~5,900 lines on the branch; the
pickled document is touched in exactly four places, one call each (read a diagram,
write an event, seed, the session route). The timeline builder, the reference parser,
the settings and account routes and the ~1,900-line page never touch storage — they
work on plain dictionaries. So swapping the format is a rewrite of four call sites and
what sits behind them, not of the app.

**The real constraint is the write model, not the code volume.** Whole-document read,
modify, write under an optimistic lock. That cannot do granular multi-writer editing or
per-turn undo, and no care at those four call sites fixes it.

**The front end is the wrong shape regardless** — hand-written JavaScript in a Flask
template, where the ruling says Vite/TypeScript PWA. That part is a rewrite whatever
happens to the diagram format.

## The PDP question (NOT previously ruled — discovered here)

Evidence: Patrick's own record carries hundreds of statements across two conversations
and had **zero committed events**; everything the coach had extracted sat unreviewed in
the pending pool (two dozen people, ~30 events, several pair bonds). The picture was
correctly empty. The path from conversation to committed record had never been walked
to the end.

In the ruled architecture, accepting a moment is just another command in the log, so
the review gate disappears. **But the pending pool is dual-purpose** — decision log,
2025-06-11: PDP deltas are the atomic unit for *both* the user's review interaction
*and* the ML ground-truth signal. Only the first half disappears. Open question: where
the training signal lives afterwards. The command log is the obvious candidate and is
arguably better evidence, since it records what actually changed rather than what a
reviewer approved in a batch.

## The old format — two separate questions, do not merge them

1. **Does it work mechanically?** Pickle, whole-document writes, an optimistic lock,
   Qt datetime objects inside the blob, no granular concurrency, no per-turn undo.
   This is where the answer looks like "no".
2. **Is the model itself too restrictive?** A lot of human thought went into the
   schema, and it encodes real clinical semantics: event kinds, relationship kinds with
   targets and triangles, date certainty, the variable shifts, the person-resolution
   rules. That thinking is an asset and mostly survives a storage change.
   The question is whether the *shape* constrains what the coach and the timeline need
   to express — for example whether a "moment" is always an Event, whether clusters are
   first-class, whether a relationship needs richer structure than kind + targets +
   triangles, and whether anything needs to be time-ranged rather than dated.

Answering (1) "no" does not answer (2). Keep them apart in the session.

## The fork to settle first

Does the command log **replace the storage layer behind the existing models**, or does
it become a **separate service** the training app talks to? Everything downstream
depends on it. The first is implied by STATE.md; the second is cleaner and much more
expensive.

## Other open questions for that session

- Migration: what the converter must prove beyond positions and counts; what happens to
  records mid-flight; whether the pending pool is converted or dropped.
- Multi-writer: what actually needs realtime — the agent and one browser, or several
  people on one record? The answer changes the conflict model.
- The training app's existing writers (extraction, the SARF editor) also mutate
  diagrams. They either move onto the same write path or become a second writer that
  the log has to tolerate.
- Where the Pro app's export-only ending leaves the desktop codebase and its users.
- Whether clusters/chapters become stored entities (today they are partly derived,
  partly stored, and a chapter chip depends on the stored ones).

## Sizing (my estimate, not measured)

Not one session. A written plan first, then several sessions. A thin slice — the log and
a shared write path behind those four call sites, with the current page still on top —
is plausibly one session.

## What is salvageable from the chat-first build

The design and the concepts, which is what was actually being tested: the coach-driven
picture, chips that aim it, the chapter view that shows no words until the coach names
them or you tap, the play-by-play (**ruled good by Patrick, 2026-09-03: "looks and
feels great, that is what I wanted"**), the timeline list and the event editor's
conditional rules. Also the storage-agnostic code: the timeline builder, the reference
parser and index, the endpoint shapes. What does not survive: the storage calls, the
page's implementation language, and the review-gate assumption.

**Still unverified and worth carrying in:** whether a live coach actually cites the
reference index in a real conversation, which is the last thing standing between the
chip mechanism and a coach that genuinely drives the picture.
