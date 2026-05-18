# Decision Log

Running record of major decisions. See root CLAUDE.md for logging criteria.

**Order:** Newest entries first within each month section. Add new entries at the top of the relevant month.

---

## 2026-05

### 2026-05-16: FD-319 — fix repair non-convergence (hard 500 on real diagram)

**Context:** Manual test on a real 27-person diagram (disc 55) hit an
intermittent extraction 500, blocking the returning user entirely — worse
than the original duplication symptom. Root cause: the duplicate validator
and the duplicate repair call the same `match_people` (a global assignment).
One repair pass drops its matches; removing them shifts the optimal matching
and exposes committed duplicates the first pass never saw. The validator
recomputes the same matcher and rejects the residual; 3 retries exhaust → 500.

**Decision:** Iterate the remap/drop in `fix_committed_person_duplicates` to a
fixed point (bounded by delta size; each non-empty pass drops ≥1 person so it
converges). Chosen over (a) loosening the validator — would let real duplicates
through; (b) a different matcher in repair vs validator — guarantees divergence.

**Reasoning:** Aligns repair with its validator by construction. Verified on the
exact captured 500 payload (now passes) and 20/20 clean re-extractions on disc
55; regression test added; full pdp suite + 3-cycle journey green.

**Revisit trigger:** `did not converge; residual committed duplicates` appears
in logs, or a matcher change reintroduces instability.

### 2026-05-16: FD-319 — ship PASS1_CONTEXT committed-data carve-out; keep deterministic repair as load-bearing safety net

**Context:** FD-319 shipped a deterministic post-extraction repair
(`fix_committed_person_duplicates`). Remaining scope: quantify the raw-LLM
committed-duplicate rate and test a prompt fix. Measurement (PRODUCTION prompts,
repair bypassed, N=10 × {gemini-3-flash-preview, gemini-3-pro-preview}) showed
the prior strategy-doc §2b "Resolved 2026-03-05" claim was falsified at scale:
flash re-emits committed **pair_bonds** 10/10 on a 15-person re-extraction
(people/marriage already 0/10). The ticket's original N=1 "people+marriage" was
a default-prompt artifact (`FDSERVER_PROMPTS_PATH` unset everywhere).

**Options considered:**
1. Prompt-only, drop the repair — rejected: stochastic, no idempotency guarantee at
   temperature; the 2026-03-05 prompt-only approach already failed this way at scale.
2. Repair-only, no prompt change — rejected: leaves flash at 100% raw dup on large
   committed states; repair firing load unbounded and untracked pre-beta.
3. Enumerate committed IDs into PASS1_CONTEXT via a new format placeholder —
   deferred: needs a `pdp.py` signature change; unnecessary since the salience edit
   alone reached 0/10.
4. Salience edit to the proximal `EXTRACT: ... all pair bonds ...` directive
   (qualify to `All NEW ...` + adjacent `⚠️ ALREADY-COMMITTED ITEMS` self-check) —
   chosen.

**Decision:** Ship option 4 (edit in `fdserver/prompts/private_prompts.py`, uncommitted
pending Patrick). Keep `fix_committed_person_duplicates` as the load-bearing safety net,
not redundant. Reverses the 2026-03-05 "post-hoc dedup is wrong-headed" stance.

**Reasoning:** Raw committed-dup → 0/10 across all cells/models (flash/complex
1.00→0.00, pro/complex 0.10→0.00); F1 not regressed (flash, 6 GT, avg 2:
agg 0.671→0.687, people 0.925→0.919 — all within run-to-run noise). Decisive on the
N=10 deterministic gate; F1 claim bounded to "no regression" at N=2. The carve-out
must live in the *last* generation directive — an upstream rules section loses to a
literal "extract all X" at scale.

**Revisit trigger:** Production `fix_committed_person_duplicates:` grep frequency
materially non-zero once a post-beta window exists; or a 3-run F1 confirmation
shows a real regression; or a model upgrade changes the raw-dup profile.

### 2026-05-16: FD-325/326 returning-user coach — data-model contract, pattern (b), measurement

**Context:** FD-326 (returning-user-aware Personal coach balancing current-events talk with intake completion). A handoff flagged an unresolved data-model question: where committed Personal-app family data lives, and whether `intake.py` needed a linkage rewrite for Scene/QDateTime format (real diagram 1924 looked like raw Scene format with empty pair_bonds).

**Options considered:**
1. Harden `intake.py` to read `person.marriages` + Scene parents (handoff's assumed branch).
2. Treat flat-PDP/ISO as the contract; document 1924 as a Pro-only artifact.
3. Trace the extract→commit path to ground the answer before acting.

**Decision:** #3 then a corrected form of #2. Committed Personal data lives in `DiagramData.people/events/pair_bonds` (Scene collections), dates always QDateTime — never `.pdp` (pending pool, cleared by `commit_pdp_items`), never ISO. Desktop `Scene.write()` and Personal `commit_pdp_items()` **converge** on the same collections/keys, so **no linkage rewrite is needed** (contradicts the handoff's working assumption). Contract pinned by a Scene-format/QDateTime regression test (`test_committed_scene_format_contract`); 9/9 intake tests pass. The 1924 "empty pair_bonds" observation is the post-corruption 2-person state from a pre-sandbox `coach_chat` overwrite, not an unhandled schema.

**Pattern (b):** Opus stays present under sustained stonewalling (correct; do not force an intake bridge — mechanical pivoting is the FD-326 anti-goal). Gemini does NOT reliably stay present (see Correction below). Open decision: accept Gemini as a known-weaker secondary path vs invest.

**Measurement decision:** FD-326 uses a dedicated 4-dim LLM judge (`coacheval`), not `QualityEvaluator` response-type entropy. Entropy mis-penalizes consistent acknowledge+question turns (correct coaching, low entropy) — it measures synthetic-client realism, not coach quality. Extraction F1 deliberately not run: no extraction prompt was touched, so there is no F1 surface.

**Reasoning:** Tracing beat guessing — the feared intake.py rewrite was unnecessary, saving churn and a class of silent regressions. Three test-infra root causes found, all silent-fallthrough: `FDSERVER_PROMPTS_PATH` (e2e silently used the OSS prompt stub — cause of prior wrong-behavior iterations); `.env` not pytest-loaded / unsourceable; and — most consequential — **`ask()` does not persist turns, so the REPL and the smoke `_multi_turn` ran a coach with no within-session memory**. The production HTTP route commits per request and is unaffected; only the test/dev harnesses were. All first-round multi-turn results and the conclusions drawn from them ("17/18", "(b)-Gemini opener tic", "stay-present accepted", the measured/reverted prompt-reframe, "skip") are RETRACTED.

**Correction (valid harness + Claude thinking enabled→adaptive):** 3× e2e = 15/18. (a) and (c) solid on Opus AND Gemini, 3/3 each. (b): Opus 3/3 PASS; Gemini 0/3 — two canned-empathy clichés, one cardinal failure (pivoted to family-history interrogation while the user was on current events). Conclusion: model-capability gap on the Gemini stonewalling path, not a prompt phrase. Open decision (Patrick): accept Gemini as a known-weaker secondary path (Opus primary and solid across a/b/c) vs invest (Gemini work / post-strip / route (b)-type sessions to Opus).

**FD-325 graceful degradation (real-diagram finding + fix):** On real committed diagrams the returning-user coach went blank — the committed-state summary traversed structural links from the speaker, and extraction connectivity (FD-324) does not reliably produce them (real Marcus diagram 1813: 14 people committed, speaker not primary and unlinked to parents → coach told only "spouse Jennifer", not the roster). Decision: the coach is now handed every committed, real-named person by name (`roster_for_prompt`) independent of speaker traversal, folded into FD-326. Full structural coverage (mother/father/siblings categories) remains gated on FD-324; the roster makes returning-user awareness usable before FD-324 lands. Verified on 1813 + unit-pinned (10/10 intake).

**Desktop-synced residual closed (and it was hiding crashes):** Verified roster/coverage/summarize on three real populated desktop clinic diagrams (332/98/70 people). `person.parents` resolves into `pair_bonds` 100% on real data — the handoff's feared linkage rewrite is disproven by observation, not just code-trace. Found and fixed two production crashes that synthetic fixtures missed: (1) scene-stub person with `name=None` → `AttributeError` in roster; (2) `relationship` stored as a `RelationshipKind` enum object (not its string) → `TypeError` sorting in coverage. Both would have 500'd `summarize_committed_state` on any real desktop diagram. Pinned by `test_real_desktop_quirks_dont_crash` (11/11 intake).

**Gemini-(b) closed (Patrick):** Accept Gemini as a known-weaker secondary path; do not invest in stonewalling handling on any model. Opus is primary and solid across a/b/c.

**Prompt IP restored — aggressive rewrite reverted (option a):** The lean rewrite deleted literature-derived clinical content (fact-level minimum dataset, clinical method, the "done" definition) and gutted tuned addenda (Opus 66→4, Gemini 22→3 lines). Reverted to the original literature `_CONVERSATION_FLOW_CORE` + original Opus/Gemini addenda; the ONLY changes layered on are additive: (1) the `committed_state` plumbing, (2) a "working memory of this user's family" block (FD-325: use known names, don't re-ask known facts, engine feeds the outstanding list), (3) the canned-empathy opener family ("I'm sorry to hear/Sorry to hear it") added to the existing AVOID-clichés list. No clinical IP deleted.

**Return-pivot now measured + judge made robust:** Added a 5th judge dimension `returns_to_collection` (positively scores: topic winds down → coach bridges to a real missing area; true when not applicable) — the FD-326 promise was previously unmeasured (only a negative no-premature-pivot guard existed). Also fixed a silent meter corruption: gemini-2.5-flash intermittently truncated the judge JSON tail, crashing the test and dropping patterns (had been losing (b)-Opus); parser now recovers the five gating booleans by regex.

**Measured outcome (3× e2e, 5-dim judge, restored prompt):** (a) opening 6/6 and (c) long-session 6/6 PASS on BOTH models incl. return-pivot. (b) sustained-stonewall script: fails both models at turn 10 (clumsy theory-pitch bridge or no bridge) — the explicitly out-of-scope case; does not occur in normal long sessions. Conclusion: option (a) succeeds for in-scope behavior; no fallback to (b), no further stonewalling work.

**Presenting-problem coverage deferred (FD-330):** Patrick (PR #116 review) asked whether the presenting problem's ~10 literature sub-facts could be tracked in the engine like structural categories. Not feasible in the schema-derived engine: those sub-facts have no structured home in DiagramData/PDP, and an LLM/conversation pass violates the engine's no-LLM/blank-history design. Filed FD-330 (schema + extraction + per-sub-fact coverage; depends on FD-324). Kept the single coarse PresentingProblem category for now.

**Methodology rule added:** any multi-turn coach validation must persist each turn (commit) — an in-process `ask()` loop without commit silently tests a memoryless coach. Encoded by the `db.session.commit()` in `_multi_turn` and `coach_chat.py`.

**Revisit trigger:** A Personal-app user surface that writes committed data in a form other than `commit_pdp_items` output or desktop `Scene.write()`; or the cliché judge dimension blocking otherwise-correct Gemini coaching.

### 2026-05-02: Snapshot-diff merge + server-side block id allocation for concurrent Pro/Personal saves

**Context:** When both Pro and Personal apps had the same diagram open, the second-saver's stale snapshot silently overwrote the other side's edits via `merge_scene_collection` ("union by id, local wins" — clobbers any item present in both snapshots regardless of who actually edited it). Plus `lastItemId` is a single counter both apps allocate from, so concurrent adds collide. This blocked the MVP intake flow (clinician leaves Pro open while client uses Personal).

**Options considered:**
1. **Renumber-on-collision** (rewrite cached ids in undo stack, Layer.itemProperties, etc.) — audit found ~10 distinct id-keyed sites; high silent-corruption risk if any missed.
2. **Per-app id namespace partitioning** (Pro uses ids in [1, 2^30), Personal in [2^30, 2^31)) — Patrick rejected (apps share data, should share namespace).
3. **UUIDs** — Patrick rejected (id space is integer).
4. **Server-side block id allocation** (Pro reserves blocks of N ids on diagram open via dedicated endpoint; server's lastItemId always advances ahead of any block) — chosen.
5. **Snapshot-diff merge** (`apply_local_changes`) replacing `merge_scene_collection`: user's actual changes (snapshot → local) applied on top of server's current state; items the user didn't touch pass through from server, preserving concurrent edits at item level.

**Decision:** Both #4 and #5. The combination eliminates silent data loss across the realistic MVP intake scenarios (Pro left open while Personal does PDP commits, etc.) without requiring renumbering of established item ids. Tested via 46 unit tests + 3 e2e harness journeys + 7/8 manual journeys on real hardware. PR #114 (btcopilot) + #135 (familydiagram).

**Reasoning:**
- Snapshot-diff merge is correct by construction: items user didn't touch pass through from server. No more "local wins always" clobbering.
- Block allocation makes id collisions structurally impossible without changing the integer id space. Pre-reserved block belongs to the requesting client; server's `lastItemId` advances atomically via SELECT FOR UPDATE + optimistic version locking.
- Both fixes are localized and reversible. No schema migrations.
- Caller-captured `_lastSavedSnapshot` (Pro's setData / Personal's saveDiagram) is the merge baseline — NOT the post-merge canonical bytes (which may include other-client items the local Scene never loaded). This subtle distinction was found by e2e harness after the first ship attempt.
- Native Python `==` for dirty-detection (replaces pickle byte comparison): 1078x faster, more correct (Qt's QPointF/QDateTime use semantic equality including fuzzy float compare; pickle bytes produce false-positive dirties for identical-semantic floats with different IEEE 754 representation).

**Trade-offs accepted:**
- Item-level last-write-wins on the same-item-different-fields case (Pro and Personal both edit same person's different fields → second saver's whole item dict wins). Documented as MVP behavior; field-level merge is v3.
- Block allocation leaks unused ids when a Pro session ends mid-block (~95 ids/session worst case). Math: 2^31 / (10 instances × 5 sessions/day × 95 leaks) > 1100 years per diagram. Negligible.
- `reserve_id_block` concurrency under SQLite `:memory:` test environment can't be fully simulated (each thread gets a private DB). Production correctness verified by SQL semantics + serial test + monkeypatched retry-branch coverage.
- `J-6` manual journey deferred until Personal exposes `editEvent` in QML (slot exists, no UI surface). Same-item-LWW behavior covered by unit test `test_same_item_both_sides_edited_local_wins`.

**Revisit trigger:**
- Customer report of same-field concurrent edit loss → time to ship field-level merge (v3 work item).
- Block allocator failure under real PostgreSQL load → instrument `reserve_id_block` retry rate.
- Future Personal-embedded-in-Pro architecture obsoletes the wire-protocol layer — at that point both fixes can be retired.

**Plan:** [familydiagram/doc/plans/2026-05-01--mvp-merge-fix/](../familydiagram/doc/plans/2026-05-01--mvp-merge-fix/README.md). Manual journey results: [JOURNEYS_HUMAN.md](../familydiagram/doc/plans/2026-05-01--mvp-merge-fix/JOURNEYS_HUMAN.md). Implementation log: [logs/](../familydiagram/doc/plans/2026-05-01--mvp-merge-fix/logs/).

---

## 2026-04

### 2026-04-12: Auto-accept extraction — skip PDP approval step for MVP 1

**Context:** During MVP consolidation, Patrick identified that the PDP drawer approval step (review/accept/reject individual extraction items) adds friction that beta users won't understand. The LLM-based deduplication (T7-9 positive-ID filtering, 12 tests) makes re-extraction mostly idempotent, reducing the need for human review.

**Options considered:**
1. Keep PDP approval step, fix the 4 PDP drawer bugs (#128, #130, #132, #133)
2. Skip PDP approval entirely — extract + commit + cluster detect in one shot
3. Simplified approval (Accept All only, no per-item review)

**Decision:** Option 2 — New single backend endpoint performs extract_full() + commit_pdp_items() + ClusterModel.detect() in one atomic DB transaction. "Build my diagram" button calls this directly. PDP drawer code preserved but not wired up.

**Reasoning:**
- Users won't understand what PDP items are or why they need to approve them at this stage
- Atomic transaction prevents data corruption on partial failure
- 4 PDP drawer bugs (#128, #130, #132, #133) become irrelevant, removing them from MVP 1 critical path
- F1 of 0.616 means ~38% of items are wrong/missing — acceptable for beta since users can re-extract
- T7-9 dedup ensures re-extraction doesn't create duplicates of committed items
- Timeline (Learn tab) is the primary content view, not the PDP — same content, easier to digest

**Trade-offs accepted:**
- No human review of extraction output before committing to diagram
- PDP drawer investment is dormant (could be revived later for power users)
- Backend endpoint must be strictly transactional — any failure rolls back everything

**Revisit trigger:** If beta users express desire to review/edit extraction results before committing, or if extraction quality (F1) drops below acceptable levels on real conversations.

### 2026-04-12: MVP Dashboard consolidation — milestone-based source of truth

**Context:** After Patrick stepped away for several weeks, the MVP tracking was split across three contradictory sources: MVP_DASHBOARD.md (stale since March), GitHub Issues (some incorrectly closed by OpenClaw automation), and GitHub Project Board (human-only tasks marked Done, reverted code marked Done). No single source could be trusted.

**Decision:** Restructure MVP_DASHBOARD.md from goal-based to milestone-based, aligned to GitHub milestone descriptions (which are the correct definitions). GitHub project board flagged as unreliable — do not trust its status fields. Dashboard + GitHub issues are the source of truth.

**Key findings during consolidation:**
- T3-7 (timeline→diagram highlight): Closed on GitHub, Done on project board — zero code exists. Moved to Jira nice-to-have.
- T7-11 (rules-based dedup): Done on project board — was implemented then reverted. Dead; replaced by T7-9 LLM-based approach.
- T7-9 (idempotent re-extraction): Open on dashboard — actually complete with 12 tests. Dashboard never updated.
- T8-1 (beta test): Closed on GitHub — partial. Patrick tested on iOS, captured friction, but bugs not fixed.
- T7-5, T5-1, T5-2 (human GT tasks): Done on project board — human-only tasks that OpenClaw couldn't have done. Patrick confirmed he coded GT for 6 discussions (meets target).
- SARF accuracy (Goal 4): Removed from developer burndown — human tester scope, Patrick mobilizing testers.
- Gemini coaching validation: Deferred — Opus is excellent, no one will use Gemini until later.

**Revisit trigger:** If tracking drifts again. Consider automated dashboard generation from GitHub issues/milestones.

### 2026-04-11: FR-2 fix — Pro app applyChange uses explicit field merge

**Context:** Pro app's `applyChange` in `ServerFileManagerModel.setData()` was replacing the entire DiagramData on 409 conflict retry, destroying Personal-app-owned fields (pdp, clusters, clusterCacheKey). This was the FR-2 violation tracked as T0-4 / GH #82.

**Options considered:**
1. Skip-list approach — replace everything except a blacklist of Personal-owned keys
2. Explicit field assignment — only write Scene-owned fields, same pattern as PersonalAppController.saveDiagram()
3. Full merge strategy with per-field conflict resolution

**Decision:** Option 2 — Explicit field assignments for Scene-owned fields only in applyChange. Matches the existing PersonalAppController.saveDiagram() pattern. No metadata, no skip lists.

**Reasoning:**
- Skip-list is fragile — new fields default to "replace" and silently break Personal data
- Explicit assignment is self-documenting — only the fields listed are overwritten
- Matches existing pattern in PersonalAppController, reducing conceptual overhead
- Full merge is overengineered for the actual conflict surface

**Trade-off accepted:** Hardcoded field list in applyChange must be updated when DiagramData fields change. Rule added to top-level CLAUDE.md.

**Pre-existing gap noted:** Server save path (getDiagramData → asdict) already strips unknown/legacy keys from blob. File save path preserves them via _readChunk. Not addressed — low risk for MVP.

**Also fixed:** hideSARFGraphics was missing from Scene.diagramData().

**Revisit trigger:** If DiagramData fields change and the explicit field list falls out of sync, or if a third client type (beyond Pro and Personal) needs its own merge strategy.

---

## 2026-03

### 2026-03-05: IRR calibration features — coding advisor fix + review drawer redesign

**Component A fix:** Commit `876fd3c` broke per-event coding advisor by dropping `max_output_tokens` from 4096→1024 and removing `thinking_config`. Fix: `deep` parameter on `gemini_calibration()` — `deep=True` (4096 + thinking) for per-event modal, `deep=False` (1024) for IRR batch triage.

**Component B — IRR review drawer:**

Key insight: the unit of IRR review is a **matched cumulative event** across coders, not a per-statement delta. Events are paired by kind + dateTime + person links across the full discussion. Two coders' codes in one card can come from different statements.

Design decisions driven by this:
- **Scroll-to-source** on coder badge click (traced via exact description match — fragile, arrow only shows when source found)
- **3-way view toggle**: meeting order (ratify/discuss by impact) → variable → chronological
- **Per-coder dates** grouped with badges (coders can have different dates for the same matched event due to fuzzy matching)
- **Card IDs** (`#N`) for meeting/troubleshooting reference
- **Admin-only generation**, auditors can view but not regenerate

**Terminology:** Considered "coding unit", "incident", "phenomenon" for the unit of analysis. Existing term "shift" already captures the latent/inferred nature. No rename.

**Rate limiting:** 60s batch delay was for Gemini Pro (25 RPM). Now on Flash (~1000+ RPM). Can be removed. Pending confirmation.

**Revisit:** `trace_to_statements()` fragility; triage classification accuracy; rate limit removal.

---

## 2026-02

### 2026-02-24: Single-prompt extraction replaces delta-by-delta for Personal app

**Context:** Delta-by-delta extraction (one LLM call per statement, 25 calls for a discussion) produces massive over-extraction. Discussion 48 cumulative F1: Aggregate 0.25, Events 0.099 (60 AI events vs 21 GT). Cross-statement person duplication (Sam/Maya/Leo extracted twice), event inflation (3-4x GT count), and high run-to-run variance (same prompt yields aggregate F1 ranging 0.20-0.25).

Single-prompt extraction (full conversation → one LLM call → complete PDP) tested on discussion 48: Aggregate 0.45, Events 0.29 (17 AI events vs 21 GT). People extraction deterministic across runs. Nearly 2x aggregate F1 improvement with zero prompt tuning.

**Options considered:**
1. Continue tuning delta-by-delta prompts (diminishing returns, high variance)
2. Single-prompt extraction only post-conversation ("Build my diagram" button)
3. Single-prompt re-extract after each turn (expensive, same code path)

**Decision:** Option 2 — User-initiated single-prompt extraction for the Personal app.

**UX flow:**
- User chats freely (no extraction during chat — just conversation)
- User taps "Build my diagram" → full conversation sent as one prompt → complete PDP returned
- User can Accept All to commit, or continue chatting
- Subsequent "Build my diagram" re-extracts full conversation, producing a fresh PDP that applies on top of any committed items

**Architectural implications:**
- `chat.py:ask()` drops `skip_extraction=False` path — chat is chat-only
- New `pdp.extract_full()` function (alongside existing `update()` and `import_text()`)
- `Statement.pdp_deltas` no longer written during Personal app use
- Per-statement delta pipeline kept for training app GT coding/auditing only
- Celery extraction chain not needed for Personal app users

**Resolves decision 2025-12-27** (scope MVP to People/PairBonds only?): Full extraction is now viable at acceptable quality. Events F1 jumped from 0.09 to 0.29, above the "hide events" threshold.

**Measured results (discussion 48, 2 runs):**

| Metric | Delta-by-delta (best) | Single prompt (avg) |
|--------|----------------------|---------------------|
| Aggregate F1 | 0.252 | 0.450 |
| People F1 | 0.595 (23 AI) | 0.720 (11 AI) |
| Events F1 | 0.099 (60 AI) | 0.290 (17 AI) |
| People FP | 12 | 2 |
| Events FP | 56 | 11.5 |

**Revisit trigger:** If conversations become too long for single-prompt context window, or if users need real-time PDP feedback during chat.

### 2026-02-24: Patrick is sole GT source for MVP

**Context:** IRR study with Guillermo and Kathy is valuable long-term but won't build consensus quickly enough for MVP timeline. Existing GT for discussions 36/37/39 may need replacement with new synthetic discussions using improved personas.

**Decision:** Patrick codes all GT for MVP. Single source eliminates IRR delays. ~60 min per discussion. Target: 3-5 coded discussions.

**Reasoning:** MVP needs a rapid iteration loop: extract → measure F1 → tune → re-extract. Waiting for multi-coder consensus breaks that loop.

**Revisit trigger:** Post-MVP, when IRR study becomes relevant for clinical validation and publication.

### 2026-02-14: PairBonds are first-class entities, explicitly extracted by AI

**Context:** Cumulative F1 revealed AI extracts zero pair bonds across all discussions (0.000 F1). Investigation showed the fdserver prompt has zero positive PairBond extraction examples, and `cleanup_pair_bonds()` aggressively prunes pair bonds not referenced by Person.parents.

**Background — two creation paths exist:**
1. **Explicit**: AI/auditor creates PairBond entity, sets Person.parents to reference it
2. **Inferred**: AI creates Married/Birth event with person+spouse → system auto-creates PairBond at commit time via `_create_inferred_pair_bond_items()` / `_create_inferred_birth_items()`

**Options considered:**
1. Fix AI prompt to extract PairBonds directly as first-class delta entities
2. Lean into auto-inference only, exclude pair bonds from F1
3. Add pair bond inference to F1 calculation to mirror commit-time behavior

**Decision:** Option 1 — PairBonds are first-class, explicitly extracted.

**Reasoning:**
- PairBonds encode *relationships* (stated facts). Events encode *occurrences*. "My parents are Mary and John" is a relationship, not an occurrence — only a PairBond makes sense.
- The pro app's event-first design ("add events, diagram builds itself") was a UX simplification for non-technical clinicians, not a statement about PairBond importance in the domain model.
- Person.parents needs a PairBond ID to reference. The SARF editor needs PairBonds for coding. F1 needs them for measurement. All downstream consumers expect explicit PairBonds.
- Auto-inference stays as a fallback for cases the AI misses, not the primary path.

**Changes:**
- Add positive PairBond extraction examples to fdserver prompt
- Fix `cleanup_pair_bonds()` to keep pair bonds referenced by events (not just Person.parents)
- Keep pair bonds in F1 metric
- Update DATA_MODEL_FLOW.md to correctly document PairBond lifecycle

**The conceptual inconsistency** (Birth events + explicit PairBonds both establish parentage) is acceptable for MVP. Dedup logic in `_create_inferred_pair_bond_items()` handles it. Full resolution would require major refactoring not warranted now.

**Revisit trigger:** If PairBond F1 remains low after prompt fix, revisit whether the extraction schema or inference approach needs restructuring.

---

## 2026-01

### 2026-01-08: IRR analysis page using F1 + Cohen's/Fleiss' Kappa for SARF validation

**Context:** First GT discussion coded by Patrick and one IRR coder, with two more coders finishing the same synthetic discussion soon. Need formal, publishable IRR metrics for clinical validity of SARF data model.

**Options considered:**
1. Reuse existing F1 analysis page (AI vs GT) for coder-vs-coder comparison
2. Build new IRR page with clinical-standard Kappa metrics alongside F1
3. Use traditional eyeball/non-scalable IRR methods from clinical psychology literature

**Decision:** Option 2 - New `/training/irr/` page with:
- Entity-level F1 (reusing existing matching logic from f1_metrics.py)
- Cohen's Kappa (pairwise, sklearn) per SARF variable
- Fleiss' Kappa (3+ coders) per SARF variable
- Primary vs IRR coder distinction via existing `Feedback.approved` field (no schema change)

**Reasoning:**
- Existing F1 matching logic is source-agnostic (compares two PDPDeltas regardless of origin)
- Kappa is the clinical standard for IRR - chance-corrected, publishable
- Dual-purpose: validates SARF clinical reliability + provides IRR-validated GT for AI training
- Fleiss' extends to 3+ coders (Guillermo, Kathy, Patrick) without N² pairwise comparisons
- Separate page avoids confusing AI evaluation with human agreement metrics

**Publication focus:** SARF variable kappas (symptom, anxiety, relationship, functioning) on matched events - this is the clinically novel contribution. Entity F1 is secondary infrastructure.

**Revisit trigger:** If kappa values are unacceptably low (<0.4), indicating SARF model needs refinement before scaling IRR coder recruitment.

---

## 2025-12

### 2025-12-27: MVP scope - consider shipping People/PairBonds only, defer Events/SARF

**Context:** Evaluating whether F1 is the right metric for MVP given human-in-the-loop accept/reject workflow. Analysis of current extraction performance revealed asymmetric quality across entity types.

**Current metrics (45 statements, 3 discussions):**
- People: Precision 77%, Recall 56%, F1 0.65
- PairBonds: F1 0.78
- Events: Precision 9%, Recall 8%, F1 0.09 (broken)
- SARF variables: All at 0.11 (non-functional)
- Overall: FP=71, FN=106 (missing more than hallucinating)

**Options to consider:**
1. Ship full extraction (People + Events + SARF) and iterate on quality
2. Ship People/PairBonds only (decent F1), add Events/SARF later
3. Delay MVP until Events/SARF quality improves

**Key insight:** Human-in-the-loop makes FPs cheap (professional rejects bad suggestions) but FNs dangerous (professional might not notice missing clinical info). Current FN > FP means recall is the actual problem. However, People/PairBonds at 0.65-0.78 F1 may provide enough value for MVP while Events extraction is fundamentally broken.

**Implications:**
- If scoped to People/PairBonds only, F1 is reasonable metric (both above 0.6)
- Events need architectural fix before worrying about metric choice
- SARF coding may be premature - model isn't learning it at all
- Small GT sample (45 statements) limits statistical confidence

**Decision:** Pending - need to think through UX implications of partial extraction.

**Revisit trigger:** When Events F1 exceeds 0.4, or when UX design clarifies whether partial extraction is viable.

---

### 2025-12-09: Synthetic discussion generation for ground truth manual coding

**Context:** Extraction accuracy evals required ground truth separate from conversational flow assessment - needed raw coding tasks without chat context.

**Options considered:**
1. Use same synthetic discussions for both conversational flow and extraction evals
2. Extract snippets from real audited discussions
3. Generate standalone synthetic discussions specifically for extraction coding

**Decision:** Option 3 - Generate synthetic discussions focused solely on extraction accuracy without conversational flow constraints.

**Reasoning:**
- Conversational flow scenarios optimize for coaching quality, not extraction difficulty
- Targeted synthetic discussions can stress-test edge cases (complex triangles, ambiguous functioning shifts)
- Separates two distinct eval dimensions (conversation quality vs. extraction precision)
- Enables focused prompt tuning without confounding variables
- Experts can code extraction-focused scenarios faster than full coaching conversations

**Revisit trigger:** If maintaining two synthetic generation systems becomes unsustainable, or if real discussion volume makes targeted synthesis unnecessary.

---

### 2025-12-09: Minimum required data checklist in system prompts and for human evaluators

**Context:** Both AI and human evaluators were inconsistent about what data constitutes a "complete" Bowen theory case evaluation.

**Options considered:**
1. Leave completeness criteria implicit in training
2. Provide general guidelines without specific requirements
3. Define explicit minimum data checklist in both AI system prompts and human training materials

**Decision:** Option 3 - Explicit checklist: 3+ generations, all SARF variables tracked, at least one triangle identified, timeline with notable periods.

**Reasoning:**
- Ensures AI prompts don't prematurely conclude data gathering
- Provides objective standard for human evaluators to measure against
- Prevents incomplete evaluations from entering ground truth dataset
- Supports certification criteria (students must meet checklist to pass)
- Makes implicit domain knowledge explicit and teachable

**Revisit trigger:** If checklist proves too rigid for real clinical variation, or if it excludes valid evaluation approaches.

---

### 2025-12-09: Conversational flow evals for measuring therapist skill

**Context:** Bowen theory training focuses on conceptual knowledge but lacks objective measurement of conversational coaching skill.

**Options considered:**
1. Traditional supervisor observation (subjective, unscalable)
2. Self-reported skill assessments
3. Standardized conversational flow evals using validated scenarios

**Decision:** Option 3 - Evals developed for AI will be adapted for human therapist skill measurement.

**Reasoning:**
- Same rubric for AI and humans enables direct comparison
- Standardized scenarios ensure consistent assessment conditions
- Scalable via web interface (no supervisor scheduling required)
- Provides objective data for certification and training programs
- Repurposes AI development work for human training outcomes

**Revisit trigger:** If human therapists reject being measured by AI-derived standards, or if conversational complexity proves too nuanced for rubric-based assessment.

---

### 2025-12-09: Synthetic discussions and user personas for conversational flow

**Context:** Conversational flow prompts needed testing beyond manual expert simulation, but real user data was unavailable pre-launch.

**Options considered:**
1. Wait for real user data post-launch
2. Have experts manually simulate many conversation styles
3. Generate synthetic discussions using user personas (varying demographics, presenting problems, communication styles)

**Decision:** Option 3 - LLM-generated synthetic discussions with explicit user personas.

**Reasoning:**
- Enables pre-launch testing across diverse user types
- Expert time focused on validation rather than simulation
- Reproducible test scenarios for A/B testing prompts
- User personas (e.g., "anxious parent", "avoidant adult child") map to real clinical presentations
- Can generate volume needed for statistical significance

**Revisit trigger:** If synthetic conversations fail to predict real user issues, or if real user volume makes synthetic data obsolete.

---

### 2025-12-09: IRR study with parallel expert coding (Guillermo, Kathy)

**Context:** SARF data model had no formal inter-rater reliability validation - unclear if multiple experts would code cases consistently.

**Options considered:**
1. Sequential auditing (one expert per case)
2. Parallel coding with small sample (10-20 cases)
3. Parallel coding with large sample (100+ cases) for statistical power

**Decision:** Option 3 - Guillermo and Kathy independently code same cases in parallel with Patrick's work.

**Reasoning:**
- First formal IRR study for Bowen theory constructs at scale
- Validates whether SARF model is sufficiently well-defined for consistent application
- Essential for academic credibility and certification system
- Identifies ambiguous constructs requiring model refinement
- Parallel workflow doesn't slow down AI training data collection

**Revisit trigger:** If IRR results show unacceptable disagreement requiring SARF model redesign, or if expert availability drops.

---

### 2025-12-09: Hierarchical F1 dashboard for extraction accuracy

**Context:** Extraction errors varied widely across construct types (Person vs. Triangle vs. ChildFocus), making aggregate metrics misleading.

**Options considered:**
1. Single overall accuracy metric
2. Flat per-construct metrics
3. Hierarchical dashboard: overall → construct type → specific fields

**Decision:** Option 3 - Multi-level F1 score dashboard with drill-down capability.

**Reasoning:**
- High-priority constructs (Functioning, Triangle) need separate tracking
- Field-level granularity (e.g., Triangle.inside vs. outside) reveals specific prompt weaknesses
- Enables targeted prompt improvements instead of blind iteration
- Supports prioritization framework (high/medium/low impact errors)

**Revisit trigger:** If prompt engineering reaches plateau and dashboard complexity outweighs utility, or if fine-tuning makes granular tracking obsolete.

---

### 2025-12-09: Ground truth for standardizing human case evaluation

**Context:** Bowen theory lacks formal evaluation standards - application is subjective and inconsistent across practitioners.

**Options considered:**
1. Develop standards through academic committee consensus
2. Use AI-generated evaluations as standard
3. Use expert-audited ground truth dataset to define measurable evaluation criteria

**Decision:** Option 3 - Ground truth dataset from auditing system becomes the operational standard for case evaluation.

**Reasoning:**
- Auditing workflow forces experts to make explicit, measurable judgments
- Large dataset reveals consensus patterns and acceptable variation ranges
- Provides objective foundation for practitioner training and certification
- Can measure inter-rater reliability at scale for first time in Bowen theory

**Revisit trigger:** If IRR study reveals SARF model is insufficiently reliable, or if academic community rejects data-driven standardization approach.

---

### 2025-12-09: Ground truth extracted data for system prompt refinement

**Context:** System prompts for extraction were underperforming without concrete examples to tune against.

**Options considered:**
1. Rely solely on expert feedback post-deployment
2. Manually craft synthetic examples
3. Have domain experts audit real discussions to create ground truth dataset

**Decision:** Option 3 - Expert auditing system to create ground truth from real conversations.

**Reasoning:**
- Real examples capture edge cases synthetic data misses
- Expert corrections provide precise training signal
- Dataset serves both prompt engineering and future fine-tuning
- Auditing workflow validates the SARF data model itself

**Revisit trigger:** If expert availability drops below sustainable threshold, or if synthetic generation quality improves enough to supplement real data.

---

## 2025-11 (Reconstructed from ARCHITECTURE.md)

### 2025-11-XX: Restructure fdserver as deployment-only repo

**Context:** fdserver contained both application code and deployment config, causing GitHub cache limitations in private repo.

**Options considered:**
1. Keep monolith with fdserver extending btcopilot
2. Split: btcopilot (open source, all app code) + fdserver (private, deploy only)

**Decision:** Option 2 - fdserver becomes deployment-only, all app code to btcopilot.

**Reasoning:**
- GitHub cache works better in public repo
- Single wheel architecture (btcopilot only)
- Clear BUILD vs DEPLOY separation
- Extended prompts and policies can be open source

**Revisit trigger:** If btcopilot needs to be made private, or if deployment complexity increases.

---

## 2025-06

### 2025-06-11: Real-time PDP data flow into diagram files

**Context:** Personal app needed a way to show users extracted data before committing it to their diagram database.

**Options considered:**
1. Separate staging database requiring explicit sync
2. Negative IDs in-memory only (lost on restart)
3. Embedded PDP pool in diagram file with negative IDs

**Decision:** Option 3 - PDP stored directly in diagram pickle with negative IDs, converted to positive on accept.

**Reasoning:**
- Users can see extracted data immediately in UI without server round-trip
- Negative IDs prevent collisions with committed data
- Diagram file remains single source of truth
- Accept/reject operations are atomic and traceable

**Revisit trigger:** If PDP grows too large and bloats diagram files, or if multi-device sync requires server-side PDP storage.

---

### 2025-06-11: PDP Deltas as dual-purpose UX and ML training signal

**Context:** Need both a user-friendly accept/reject workflow and ground truth data for extraction accuracy. Traditional approaches require separate labeling steps.

**Options considered:**
1. Show full extracted data, require users to manually edit JSON
2. Separate UX layer (simple approve/reject) from ML layer (engineer extracts training signal)
3. LLM outputs deltas that serve as both UX proposal and atomic training examples

**Decision:** Option 3 - PDP deltas are the atomic unit for both user interaction and ML ground truth.

**Reasoning:**
- User sees only what changed (cognitive load matches clinical review process)
- Each delta is independently accept/reject (granular feedback, not all-or-nothing)
- Rejected deltas are negative examples (prevents model from repeating errors)
- No separate labeling workflow needed (UI interaction generates training data automatically)
- Deltas are traceable and reusable (can replay decisions, analyze patterns)
- Atomic structure enables field-level accuracy metrics (which attributes are hardest to extract)

**Source:** https://grok.com/share/bGVnYWN5_04d604a7-a3e9-4078-a007-3d2f659fc155

**Revisit trigger:** If users struggle with delta-based review (prefer full-context editing), or if delta granularity proves too fine/coarse for effective learning signal.

---

## Template

```markdown
## YYYY-MM-DD: [Decision Title]

**Context:** Brief situation summary

**Options considered:** What alternatives were weighed

**Decision:** What was decided

**Reasoning:** Key factors that drove the decision

**Revisit trigger:** Conditions that would prompt reconsideration
```
