# Re-extraction cursor (watermark) — design for approval

Status: DESIGN, not implemented. Changes a production DB table (migration) and
the accept path. Implement only after Patrick approves the decisions in §6.

## Goal

Re-extraction must not re-emit data already produced from earlier conversation.
Mechanism: extraction sends the full conversation as context but emits items
only for turns after a per-discussion cursor. The cursor advances only when a
PDP is accepted. Validated by experiment: cuts re-extraction event-leak ~⅓ and
lifts re-extraction parent/child recall 0.63→0.73, no F1 regression. It does
NOT eliminate leak — the deterministic pre-commit guard remains the safety net.

## Non-goal

Not a corruption-prevention mechanism. The deterministic committed-duplicate
guard (fixed this session) is what prevents diagram corruption and stays
load-bearing regardless of the cursor. The cursor is a quality + cost +
idempotency improvement, sequenced as enhancement, not MVP-gating.

## 1. Where the cursor lives

On the **Discussion row (server DB)**, not on diagram items, not in the diagram
blob. Rationale:
- The cursor is discussion-scoped session state, not diagram data. Putting it
  on diagram items (provenance) drags in the schema.py public boundary, the
  pickle format, and the two-app applyChange ownership split — all avoided by a
  server-side Discussion column.
- New nullable column `extracted_through_order INTEGER NULL`. NULL = never
  accepted = window from the start (today's behavior exactly).

## 2. Extraction

Prompt gets the full conversation for context plus a marker inserted at the
cursor; instruction: everything above the marker is already captured, emit
items only for content below it. This is a prompt change → full prompt-
optimization workflow (baseline, induction report, engineering log, timeseries).
Cursor experiment already established the baseline and that this does not
regress F1.

## 3. Accept (cursor advance)

On PDP accept/commit, set `extracted_through_order = max(statement.order
included in this extraction)` in the **same transaction** as the commit.
Idempotent: re-applying the same max on a 409 retry is a no-op. Extract without
accept → cursor unchanged (safe; re-extraction re-windows the same range, the
deterministic guard absorbs any resulting dup).

## 4. chat → edit → chat → edit

Cursor model preserves manual edits by construction: re-extraction never re-
reads pre-cursor text, so items derived from it are never regenerated. No
"user-modified" flag needed (this is the advantage over provenance-replace,
which deletes-and-recommits and needs that flag). Residual: a post-cursor turn
referencing a pre-cursor person still needs id-binding — the irreducible
identity case, covered by the deterministic guard, not by the cursor.

## 5. Failure modes

- Commit succeeds, cursor write fails → same transaction, so impossible; if the
  transaction aborts, neither lands and re-extraction repeats the window
  (deterministic guard absorbs dup). Acceptable.
- Statements deleted below the stored cursor → clamp cursor to max existing
  order on read.
- Soft-cursor leak (model emits pre-cursor items anyway) → measured ~⅓ residual;
  deterministic pre-commit guard catches it. Unchanged safety posture.
- Partial accept (user accepts a subset of staged PDP) → see §6.

## 6. Decisions required before implementation

1. **Partial accept rule.** If a user accepts only some staged items, does the
   cursor advance? Proposed: cursor advances only on full-accept of the staged
   PDP; partial accept leaves the cursor (re-extraction re-windows the range;
   guard handles dup). Confirm or specify the partial-accept semantics.
2. **Cursor placement.** Confirm Discussion-column (server-side, this design)
   vs item-level provenance in the diagram blob. This design recommends the
   column; it avoids the schema/sync/pickle blast radius.
3. **Production migration.** Adds a nullable column to the Discussion table on
   the production DB via Alembic. NULL backfill = current behavior, zero-risk.
   Confirm acceptance of the migration.

## 7. Out of scope / explicitly deferred

Provenance/replace-on-re-extract and any LLM dedup-of-committed: rejected
earlier this session (provenance breaks Pro edits / is a hack at full-history
cost; LLM dedup risks silent irreversible merges). Not revisited unless the
cursor + deterministic guard prove insufficient in real use.

## 8. As-built (2026-05-16) + deployment

Implemented (branch FD-319, uncommitted): two nullable columns on the
`discussions` table (`extracted_through_order`, `pending_extracted_through_order`);
cursor windowing in `pdp._windowed_conversation` / `_two_pass_extract`; a nonced
cursor rule prompt (`CURSOR_*_TEMPLATE` in `personal/prompts.py`); the extract
endpoint stashes the pending cursor; a new `POST /personal/discussions/<id>/commit-pdp`
endpoint commits items and promotes the cursor on full accept, one transaction.
11 cursor tests + 53 regression green; adversarial-reviewed; style-enforced.

**Migration**: `alembic/versions/c8f1a2d3e4b5_add_reextraction_cursor_to_discussion.py`.
Applied to the LOCAL dev DB only. NOT run against production (hard constraint).
NULL backfill = legacy behaviour, zero-risk. Production deploy is Patrick's:
`alembic upgrade head` after the branch lands.

**Client follow-on (familydiagram repo, NOT done)**: the Personal app currently
stages PDP server-side and commits client-side via diagram save. To get
cursor-advance, the client must call the new `commit-pdp` endpoint on accept.
Until then the cursor never advances in production (safe: behaves exactly like
today). This client wiring is a separate task in the familydiagram repo.

**Deferred (concurrency)**: adversarial review found concurrent `/extract` and
diagram-blob clobber defects that can skip conversation. Out of scope here;
proposed as a new FD-264 child (see status).
