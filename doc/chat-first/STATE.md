# Chat-first rebuild — STATE (the system of record)

Read this first, every session. This is the current truth; the derivation lives in
[HISTORY.md](HISTORY.md). Both are living documents under the two-clocks regime:
**append to HISTORY, revise STATE** as part of any work that changes either.
Ten-minute read by design.

## The product (ruled)

**"A coach who never forgets your family."** You talk to it (voice or text) the way
you'd talk to someone trained in Bowen theory; it asks what a trained coach asks; the
family record — structure + timeline — is its visible, touchable memory, growing for
years. Conversation drives everything. One picture rides pinned above the chat:
strip-small at rest, cartoon-level detail, always current. Chat is the event clock
(never rewritten); the record is the state clock (corrections change it). Proactive
messages exist and default to near zero. The product's acceptance test is the felt
shift — one or two brain-rearranging correlations per user, not a dataset. Coverage
serves exactly two things: better coach questions, and the timeline's own
correlations.

All drawing/asking rules are canonical in [../DRAWABILITY.md](../DRAWABILITY.md)
(five drawability rules; one amber question treatment in three places; cartoon rule;
at-rest vocabulary = line, dots, question mark; words-on-tap; no legends; no
lane-filter UI; expanded view must be designed for sparse data; tokens-only styling
so themes are A/B-testable with stable semantics: teal=data, amber=asking).

Owner teachings that bind all inference: ~/fd-corpus/OWNER_RULINGS.md (accumulating,
verbatim-close). Core of it: this data is far more nuanced than it looks; no rubric
or quality judgment is inferred without Patrick — he rules by example and by
correcting proposed values; scaffold vs active events (early births are age
scaffolding, not SARF material; the diagnostic period starts at the first event with
a nodal flag or variable value); max-effort model spend only on the filtered corpus.

## Architecture and stack (ruled, unbuilt except FD-360)

Keep the Flask/Celery/Postgres/Redis backend. Target shape: diagram = JSON document +
append-only command log; one Python module mutates; browser and agent are clients of
the same endpoint; agent loop in a worker streaming via Redis→SSE (async worker;
agent queue separate from long extractions); server sends patches, client has a small
reducer for optimistic drags; per-turn undo with compare-and-set inverses. Front end:
one Vite/TypeScript SVG page, phone+desktop, installed as a PWA (no Xcode, no store;
Capacitor only if store presence / locked-screen recording / hostile-Apple forces it —
a packaging step, not a rewrite). Release: PR checks → tag → one Docker image (web
bundle inside) → GHCR → one SSH compose pull. Login: passwordless (pre-authed QR/link
onboarding, months-long sessions, passkeys/Face ID, 6-digit emailed code recovery;
login IS signup for later self-serve). Migration from Pro pickles: one-shot converter,
gate = positions exact + count differences explained; hard cutover (old Pro becomes
export-only). Known debt to schedule: secrets committed in compose need rotation.

## Prototyping status (honest)

- **FD-360 page** (PR #133, draft, worktree ~/theapp/btcopilot/.claude/worktrees/FD-360):
  works and independently verified — chat through the real coach pipeline;
  session-cookie auth bridged WITHOUT touching the HMAC path (tested); CSRF added;
  per-person timeline math with a regression test against the Qt app's
  mixed-people-sum bug; resting strip obeys the three-mark rule; tap-a-mark speaks a
  plain sentence; seeded or real-record sandbox on 8889 (relaunch command in the PR /
  worker report; real-record DB at /tmp/fd360-sandbox.db). **Ruled good**: the
  narrow-lane always-on resting strip; inline chips in coach text aiming the picture.
  **Ruled not understood**: the expanded/detail view — Patrick's walk found it
  illegible on real sparse data; it is a placeholder pending ground-up design FROM
  the corpus analysis. Era-compression work exists reverted-but-recoverable in branch
  history.
- **proto.html** (jobs tmp): interactive two-concept prototype — REJECTED by Patrick,
  shelved. Its creative-round survivors (Chapter Shelf, Quiet Threads) and
  cross-cutting findings remain hypotheses only.
- Three artifacts stand as reference: Drawability, "Three Ways to Ask", "Flowing
  Through It" (URLs in HISTORY.md).

## The corpus (system of record for phases A and B)

Location **~/fd-corpus/** — NEVER in any repo; rebuild everything with
`rebuild.py <diagrams-dir> <out-dir>` (self-verifying allowlist, no data inside it).
- `clinic/case_01..61.json` + `index.json`: his 61 real clinical cases, one-way
  anonymized (P-ids, gender, decimal years, unsure flags, kind enums, per-variable
  direction enums incl. differentiation, nodal flag, text byte-lengths; free text
  never extracted). Content-blind protocol holds until the Anthropic BAA exists.
- `design/`: his own record (corpus_patrick_chat/journal.json), prod-derived
  comparisons (corpus_304/9/1341/757.json), and `prod_candidates.csv` — 104 prod
  diagrams (email + id, floor ≥40 dated events, UNRANKED; volume column explicitly
  "not quality").
- `PRIVATE_case_mapping.md`: case_NN → his actual diagram file, HIS EYES ONLY,
  regenerated on the active basis.
- `QUALITY_NOTES.md`: volume ≠ quality, in writing. `OWNER_RULINGS.md`: his teachings.

Corpus facts (post bug-fixes; details in HISTORY): events live in five homes; median
real case 23 dated events over 81 years; direction tagging in 21% of his cases;
uncertainty a right-skewed spread (median ~96% guessed); he dates marriages 2–3x more
than the prod population. **Active-basis tiers (current cut): 11 cases ≥30 active,
13 at 10–29, 28 at zero active (pure scaffold by the marker — possibly coding style;
his eyeball decides), 9 out.** The corpus self-sorted into the two planned subsets:
active-bearing cases → FUNCTION candidates; zero-active-but-structure-rich →
STRUCTURE candidates. **Waiting on Patrick: eyeball via PRIVATE_case_mapping.md and
rule the in-lists.**

A disposable Postgres container `fd-scratch-pg` (port 55432) holds the restored July
prod dump for any further prod queries; `docker rm -f fd-scratch-pg` when done.

## The ruled working order (violations get killed)

**Filter (Patrick rules by example/correction) → A: max-effort document on the nature
of this data → B: max-effort, model-optimized generation of visual-representation
choices → build.** Nothing visual is derived before A is ratified. Model policy:
judgment on the big model; max effort ONLY on the filtered corpus; implementation to
precise spec on cheaper models; mechanics on the cheapest.

## Jira / branches

- FD-359 epic (chat-first web app) with FD-360 (built, draft PR #133) and FD-361
  (corrections through chat — not started). FD-341 untouched as the June plan of
  record; FD-336 superseded as the first chat surface (in docs, not yet in Jira).
- This branch (`fall-2026-direction`) carries: decision log entries, the two
  brainstorm docs, DRAWABILITY.md, and this package.

## Open security items (Patrick's calls, untouched)

1. FD-360 branch git history: two commits with real personal data (f55c5b0,
   35dd13b). Recommended: delete remote branch + PR, re-push clean, reopen.
2. Public master, pre-existing: a test-fixture name, names in decisions/log.md, and
   IRR meeting transcripts under doc/irr/meetings quoting Patrick on family matters.
   Recommended: PR moving transcripts to fdserver + neutralizing names; his risk call.
3. Business model TABLED (numbers in HISTORY); BAA with Anthropic in pursuit — until
   it exists, clinical content never enters model context (structure-only corpus).

## What's next

The two sessions in [NEXT_SESSIONS.md](NEXT_SESSIONS.md): FUNCTION-subset and
STRUCTURE-subset needling, both gated on Patrick's tier rulings, both feeding phase A.
