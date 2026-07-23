# Decision Log

Running record of major decisions. See root CLAUDE.md for logging criteria.

**Order:** Newest entries first within each month section. Add new entries at the top of the relevant month.

---

## 2026-06

### 2026-06-15: FD-321 — user profile (name + birth date) ground + UI decisions

**Context:** FD-321 captures the Personal-app user's own name + birth date and feeds them into
extraction/rebuild context (kills the duplicate-proband "Client" fabrication class). Driven via the
workstream skill. Oracle ratified by Patrick: C1–C11 + C13 (machine-proven), C12 (human walk).

**Decisions accepted:**
- **Birth date is a Birth EVENT** on the primary node, not a scalar Person field (Patrick: "it must
  be a birth event"). Avoids a new schema field and the two-location DiagramData sync hazard.
- **Real name everywhere:** the user's name replaces the generic "Client" speaker label in both
  extraction prompts and the chat UI (added C13).
- **Wizard UI = single-screen** (variant A), chosen over a multi-step paged wizard after side-by-side
  prototypes. One reusable `UserDetailsForm` drives both the first-launch wizard and the Settings
  editor. Spec: `familydiagram/doc/ui-specs/user-details.md`.
- **Closure without a referee:** this project has no deterministic referee; every machine-checkable
  criterion is driven to a real measured result and its evidence recorded in the unit state file
  (`doc/workstreams/fd-321.json`). Standing convention, same as in-flight units.

**Revisit trigger:** if extraction F1 moves outside the ±0.05 band after injecting speaker identity
(C11), the prompt-context change is incomplete and must be re-tuned before merge.

### 2026-06-09: Fable 5 extraction experiment — adapter design, induction convergence call

**Context:** Evaluating claude-fable-5 ($10/$50 per MTok) for extraction. No
Anthropic structured-output path existed in the pipeline.

**Decision 1 — prompted-JSON adapter over constrained decoding.** Anthropic's
`output_config.format` rejects the PDPDeltas schema two ways: subset-required
objects time out grammar compilation; require-all + nullable wrappers exceed
the 16-union-param limit (ours needs 23). Adapter embeds the JSON schema in the
prompt and validates client-side via `from_dict()`. Zero parse failures in ~70
calls. Constraint applies to ANY future Anthropic structured extraction on this
schema shape. (`btcopilot/llmutil.py: claude_structured`, fable-5-extraction worktree)

**Decision 2 — dateCertainty="unknown" for inferred dates REVERTED.** Measured
Events −0.016; opening the F1 date gate raised FPs elsewhere and risks false
TPs. Don't retry without a tighter mechanism.

**Decision 3 — induction declared converged at cold baseline.** 4 iterations
(2 kept within noise, 1 reverted, 1 contaminated by billing): Fable 5's +39%
Events gain is model-native; prompts are already at their tuning ceiling.
Implication: future frontier-model evals should run cold baseline + 1-2
targeted iterations, not full 10-iteration inductions.

**Decision 4 — matcher asymmetry classified as metric bug, not model error.**
`match_events` requires exact person/spouse slot assignment on married events;
AI choosing the other partner can never match. Affects all models. Fix belongs
in `f1_metrics.py` (canonicalize spouse pairs symmetrically), not in prompts.

**Decision 5 (Phase 5 results) — hybrid Pass-3 swap is the recommended first
production step.** flash-lite extraction + fable-5 SARF review: SARF macro
0.535 vs 0.375 prod (+43%, 2-run mean), Events/Aggregate unchanged,
~$0.20/discussion, latency cost confined to Pass 3. All-Fable sets records on
every metric (Agg 0.731 / Events 0.617 / SARF 0.621) at ~$1.30/discussion but
is async-only. The 2026-03-04 "hybrid per-pass selection doesn't help" finding
is overturned — it tested same-tier Gemini swaps; a stronger reviewer model
does lift SARF. Production options handed to Patrick: (A) hybrid, (B)
all-Fable async, (C) status quo.

**Revisit trigger:** Anthropic raises the union-param limit (retry constrained
decoding); SARF variance bounds needed before production commit (hybrid macro
spread 0.490-0.579 across 2 runs; all-Fable SARF is single-run).
### 2026-06-10: FD-338 — committed-poison fix = wipe-and-re-extract, not surgical repair; name-leak in history accepted

**Context:** The GT loop proved 5 remaining wrong edges are poison in diagram
1924's committed data (wrong committed parents link on the proband, a person
seated under her sibling's bond via a bad committed birth event, two spurious
committed bonds) — unreachable by the additive pipeline. Options were
supervised surgical repair vs a committed-correction feature.

**Decision (Patrick):** Neither — wipe all committed people/events/bonds from
the canonical diagram and regenerate from the source conversations through the
fixed pipeline (per-discussion extract -> fragmentation check -> rebuild ->
connectivity + GT score). The committed state becomes 100% product of the
current pipeline; consistent with the standing "no tuning on AI-residue data"
ruling. Snapshot of the pre-wipe state kept in btcopilot-sources. Separately:
pre-existing real-name occurrences in already-merged history are ACCEPTED
("I'm not too worried about git history") — no rewrite; working-tree
occurrences stay anonymized going forward.

**Revisit trigger:** If the regenerated canonical state still fails GT
assertions, the committed-correction feature question returns (it would then
be pipeline output, in scope).

### 2026-06-10: FD-338 — ex/romantic partners attach as unmarried pair bonds rendered dashed (GT item 5)

**Context:** GT walk overturned the leave-floating policy for ex-partners: a
girlfriend/boyfriend or ex must attach as a pair bond drawn dashed. The scene
Marriage item already has a `married` property (default True = solid, False =
dashed/bonded-only), but the staged PairBond dataclass had no such field, so
extracted bonds could only commit solid.

**Decision:** Optional tri-state `married: bool | None` on the staged PairBond
(None = unstated). Commit maps None -> True in the committed chunk because the
scene's property reader coerces a literal None to bool(None) = False — an
unmapped legacy bond would silently render dashed. False survives commit and
renders dashed with no familydiagram change (Marriage.read picks the key up
from the chunk). The dock edge schema and DOCK_PROMPT now direct romantic
partners INCLUDING exes to partner_of with married=true/false/unset; friends
remain verdict none. The field is also exposed (optional, described) in the
extraction structured-output schema, and merge_runs copies run bonds instead
of rebuilding them so the flag survives accumulation.

**Reasoning:** Flag plumbed at the schema boundary rather than a parallel
"bond kind" enum: the scene already models married/separated/divorced as
properties, and a single optional boolean keeps old staged data and old
clients valid (from_dict defaults missing -> None). Exposing it to extraction
risks false dashed flags on real marriages — wording restricts false to
stated never-married relationships; DOCK_PROMPT + extraction schema change
triggers the 6-GT F1 overfit-brake re-run in the loop.

**Revisit trigger:** Real rebuilds start staging married=false on actual
spouses (prompt wording too loose), or divorced/separated exes need the
separate scene `divorced`/`separated` properties plumbed the same way.

### 2026-06-10: FD-338 — committed-merge identity gate: no fuzzy-name-only welds onto committed people (F-003/F-007/F-008 class)

**Context:** merge_runs welded run people onto committed people purely via
match_people's fuzzy token-set name score (threshold 0.60). A new sibling
sharing only a last name consumed the committed person (F-003: extracted Ben
matched committed Dennis because Ben iterated first; Ben vanished, a duplicate
Dennis staged, committed Dennis got a bogus parents edit). Same class produced
the GT walk's wrong-parent-couple and mother+son-in-law couplings (F-007/F-008,
three same-first-name men cross-matched).

**Decision:** Hard rule — fuzzy name similarity alone never decides identity
against committed data. Two-stage merge in merge_runs: (1) deterministic exact
pre-pass welds run↔committed people whose normalized names are equal and
unique on both sides, removing them from the fuzzy pool so a partial-name
match can't consume a committed person whose exact counterpart appears later
in the run; (2) a post-match gate on remaining fuzzy matches to committed
people: accepted only with a compatible given name (same first token, or one
token set a subset of the other) AND structural corroboration — shared bond
partner, same parent bond, or shared child — resolved through already-trusted
mappings (speaker welds + exact welds + prior corroborations, fixed-point).
Rejected matches stage as new people. Cross-run matching onto the merge's own
negative-id people stays loose (within-rebuild consensus, not identity).

**Reasoning:** Wrong welds silently corrupt committed structure (wrong parent
edits, generation flips); duplicates are visible in the review sheet and
rejectable. Name compatibility is required on top of structural corroboration
because siblings share parent bonds — corroboration alone would re-weld the
F-003 class one step later. Gate scoped to committed targets only to keep the
K>1 consensus dedup unchanged.

**Revisit trigger:** Real-rebuild dup rate on first-name-only extractions
becomes a review burden (corroboration seeds too thin on bond-poor diagrams),
or nickname variants ("Bob"/"Robert") start staging duplicates frequently
enough to need an alias table.

### 2026-06-09: FD-338 — commit-pdp acceptance contract restricted to negative ids; parents edits applied server-side on full accept

**Context:** Multi-window extraction now stages positive-id Person(id, parents)
edit rows in the PDP. The commit-pdp route treated every staged id as
committable: a client echoing a positive id 500'd (commit_pdp_items raises on
non-negative ids by design), the legacy full-accept fallback comparison went
permanently False whenever positive rows were staged (cursor freeze), and no
server path applied parents edits in the real accept flow — application
depended entirely on a client-side generic field merge that released clients
never run.

**Decision:** The wire contract covers only NEW (negative-id) items. The route
filters echoed positive ids as no-op acknowledgments (schema layer stays
strict and still raises — tolerant idempotent wire layer, strict programmatic
layer); the fallback full-accept comparison runs over staged negatives only;
on full accept the server calls apply_parent_edits AFTER commit_pdp_items
(order load-bearing: the commit's trailing remap rewrites negative bond refs
on parents rows first). Partial accepts leave parents rows staged — a
mid-review apply would silently drop rows whose bond isn't committed yet.
Shared predicate `schema.is_parents_edit` defines "parents-only row" once;
the Personal client (controller + PDPSheet) uses it to exclude those rows
from cards, accept-all echo, and the drained/full-accept computation, and the
per-item Update-card accept now posts commit-pdp so a review ending on an
Update card still advances the cursor.

**Reasoning:** Released clients (2.1.22/2.1.23b2) never echo positive ids or
call commit-pdp, so server-side application at full accept is the only
channel that works for every client generation; negatives-only comparison
restores legacy dev-client cursor advance; treating echoes as no-ops keeps
retry idempotency without masking programmatic misuse.

**Revisit trigger:** Any new staged positive-id row type beyond parents edits
(events/pair_bonds Update rows reaching the accept path), or a server-side
need to apply parents on partial accepts.

### 2026-06-09: FD-338 — canonical-case cleanup approved; scope ruling: stop tuning on AI-residue test data

**Context:** Committed diagram 1924 contained "Jim's Son 1/2" — name-only
placeholder rows duplicating the named Anthony/Joseph, committed by earlier
AI extraction runs during FD-337 testing. Unattachable (no transcript mention
of the placeholder names) and unmatchable (no name overlap, zero structure),
they capped raw LCC just under the 90% bar in 2/7 acceptance runs.

**Decision (Patrick):** Delete the two rows from the dev DB (done, 34→32
people, no event/bond references). Bigger picture: the e2e extraction flow has
not been seriously human-tested on a diagram + its conversations; the 1924
baseline is residue of prior AI runs, not human-validated data. Pre-existing
data bugs are DEFERRED outside FD-338 scope, and no more significant token/day
spend on test data not produced by the e2e extraction flow. The decisive gate
for this feature is a human walking the real e2e flow on fresh extraction.

**Note:** placeholder-vs-named duplicate is another ask-the-user case for the
deferred closed-loop ticket ("Are 'Jim's Son 1' and Anthony the same
person?").

### 2026-06-09: FD-338 — gate-and-dock replaces K-union as the rebuild core; DEFAULT_K 4→1 (supersedes the K=4-default entry below)

**Context:** Measured this session (n=11 single runs + 6 disconnect
classifications): single-run LCC swings 47-94% on the canonical case; failures
are always missing edges, never people; the dominant residual classes are a
pronoun-bridge couple (find rate ~17%/run — union consensus needs ~16 arms for
95% confidence, outside the cost envelope) and seam-severed branches. A
directed-repair probe (full transcript, no cursor rule, explicit
pronoun-resolution instruction, verbatim-quote gate, edges-only programmatic
apply) docked the pronoun bridge 4/4 with verified-correct antecedent, zero
false attaches of the two legit-disconnect singletons, lifting all 5 probe
runs to 93-97%.

**Decision:** Rebuild core = single windowed run + deterministic
connected-components gate (free) + one directed dock call, accepted only if
the floating-component count strictly drops (floor by construction). K stays a
parameter (VALID_K={1,4,8}, arms+merge intact) but DEFAULT_K=1. merge_runs
parents resolution: per-person plurality vote (was first-writer-wins).
78-agent design council + adversarial review preceded this; consensus
(rank 2) is retained as the insurance configuration, not the default.

**Reasoning:** One mechanism covers both failure classes (probe + 7-run
acceptance battery: dock recovered the pronoun bridge 6/6 and the
explicit-evidence singleton 7/7 with zero dock-attributed false attaches);
cost ~$0.11/rebuild vs $0.23 at K=4; the crash fix (pass-3 splice gate) held
0/10 across acceptance+F1 runs vs ~15% before.

**Revisit trigger:** Acceptance re-run after the client accept-path fix; if
dock-attributed false attaches appear, or junk-excluded LCC <90% in >1/8 runs,
fall back to K=4 + dock (rank-2 architecture).

### 2026-06-09: FD-338 — "coach asks when unclear" adopted as a standing principle; closed-loop build deferred

**Context:** The pronoun-bridge evidence exists only because the in-transcript
coach asked whether the person just mentioned was a named relative's sibling.
Patrick: a coach unclear on something
would simply re-ask the client; the conversational prompt never asks
clarifying questions.

**Decision:** Going forward: (1) steer the live conversation to anchor
relational references when first mentioned, so pronoun-only evidence never
gets written; (2) a closed-loop clarification channel (deterministic gate
detects floats; dock "no stated connection" verdicts generate at most one
in-register question; the answer persists as transcript — permanent fix).
Processing failures (evidence already explicit in transcript) are NEVER asked
about — asking reads as not listening; they stay pipeline repairs. DEFERRED
out of the FD-338 PR: needs a question ledger (open/answered/declined,
never-re-ask, confirmed-disconnected persistence) and a client chat channel.
Oracle = the free graph check + dock verdicts, not an LLM.

**Revisit trigger:** If directed repair had failed the probe it would be
mandatory; it passed, so the loop is the compounding complement. Pivot review
(shrink dock/arms further?) once live answer data exists.

### 2026-06-09: FD-338 — fuzzy name matching is WRONG for dedup; never rely on card review; dedup belongs in the LLM

**Two mistakes Patrick has corrected before — logged so they stop recurring:**

1. **Fuzzy name matching does NOT work for person identity / dedup.** Already
   learned (FD-324). I reached for it again in the FD-338 merge/reconcile
   (`match_people`'s fuzzy `token_set_ratio` name component). On the real
   diagram it produced soft-duplicates it could not catch: **"Client"** and
   **"Patrick"** added as separate people from the User/proband node; **"Jim's
   Ex"** vs **"Jim's Ex-Wife"** and **"William"** vs **"William Patrick"** left
   un-merged. Patrick would have blocked this had he seen it. **RULE: never use
   fuzzy name similarity to decide person identity for committed/production
   data.** (Offline F1 *scoring* is a separate, acceptable use.)

2. **Never rely on the user reviewing PDP cards as the quality gate.** Most
   users click **Accept All**; almost no one flips through cards. Output must be
   correct BEFORE the review sheet — the sheet is not a safety net. Recurring
   mistake; stop assuming human curation will catch bad proposals.

**Direction (Patrick):** Dedup must happen **in the LLM** — give the model the
committed people as context so it recognizes existing people semantically and
emits only genuinely-missing people/connections, instead of extracting from
empty and fuzzy-matching afterward. Also reconsider the K-independent-passes
design — it exists only to average out which bridges a stochastic single pass
misses; with LLM-side dedup a simpler/targeted approach is likely enough.

**Status:** FD-338's from-empty + `match_people`-merge reconcile is the wrong
foundation per the above and must be reworked before shipping. Current PRs hold.

**Revisit trigger:** any future person-dedup work — re-read this before reaching
for name similarity.

### 2026-06-09: FD-338 — default rebuild tier K=4 (max-fidelity opt-in); supersedes K=8 default

**Context:** K=8 as the default makes every rebuild ~$0.60 and ~20+ min on a
single worker — too heavy for everyday use. Patrick: the "rigor" (Max fidelity)
toggle should default OFF.

**Decision:** Default rebuild = **K=4** (~$0.30, faster); **K=8 is opt-in** via
the Max-fidelity toggle. UI toggle defaults off; backend `DEFAULT_K = 4`; cost
modal copy is now tier-dynamic ($0.30 / $0.60). Reverses the 2026-06-03
K=8-default decision.

**Reasoning:** Cheap/fast default fits routine use; users wanting the higher
connectivity opt into max fidelity. NOTE: the default K=4 tier does **not**
reliably meet AC#1 (≥90% LCC) — only opt-in K=8 approaches it (~90.5%). Accepted
as a product trade: default fast, rigor on demand.

**Revisit trigger:** AC#1 reinterpreted to require the *default* tier reach 90%;
or a cheaper path to 90% (better merge / parallel workers) lands.

### 2026-06-03: FD-338 — default K bumped 6 → 8 (measured; supersedes the K=6 choice)

**Context:** Measured the consensus delta against the REAL committed diagram 1924
(currently 56% keep-User LCC), reconciled as a true PDP delta — harder and more
realistic than the from-empty prototype's 94.9%. Sampling K-subsets from a 10-run
pool: K=6 median ~85–90% but only ~half of runs clear 90% (tail to ~76–82%); K=8
median ~90.6% with ~11/12 ≥90%. The full 10-run `match_people` merge ceilings at
90.7% (5 residual components) — the forbidden name-dedup's 94.9% is out of
`match_people`'s reach regardless of K.

**Decision:** Ship **default K=8** ("max fidelity"); K=4 is the cheaper opt-down.
`VALID_K = {4, 8}` (K=6 removed). ~$0.61/rebuild; cost modal copy updated to
"about $0.60". Chosen over (a) keeping K=6 and beta-accepting ~88% — fails the
≥90% AC's "reliably"; (b) investing in a better merge to recover toward 95% —
deferred R&D, uncertain, would delay ship. Patrick decided.

**Reasoning:** K=8 is the smallest tier that reliably clears the AC with the
mandated matcher. Caveat: reliability measured on overlapping subsets of one
10-run pool (correlated), not 12 independent K=8 rebuilds — directional, not a
hard guarantee; a few independent K=8 confirmations are the remaining check.

**Revisit trigger:** independent K=8 rebuilds dip below 90%; a merge improvement
recovers the name-dedup ceiling (then K can drop); customer pricing model lands
(remove cost modal).

### 2026-06-02: FD-338 — default_acc_ids exclusion in merge_runs

**Context:** `match_people` has a special rule: "User" in the GT list matches
any AI person name (because the SARF editor labels the proband "User"). In the
merge accumulator, the committed diagram has User (id=1) and Assistant (id=2).
When merge_runs passes the full accumulator to match_people, real family members
from the run match "User" via this rule, polluting the mapping.

**Decision:** Compute `default_acc_ids = _default_ids(committed.people)` (User
+ Assistant) and exclude those from the `matchable_acc` list passed to
match_people. Bond endpoint resolution and parents propagation are also guarded
against default IDs. The default people remain in `acc_bonds` for bond-dyad
resolution.

**Revisit trigger:** match_people special-case behavior changes.

---

### 2026-06-02: FD-338 — deep re-extraction delivers a PDP delta, not a diagram replace; K=6 default

**Context:** Deep re-extraction (multi-sample consensus) rebuilds a fragmented
Personal-app diagram. The ticket framed the on-completion UX as an open product
decision (replace the diagram "recoverable via version history" vs stage into
the PDP review sheet). There is NO diagram version history — replace is
unrecoverable.

**Decision:**
1. **Deliver as a PDP delta vs the committed diagram (improve in place), never
   replace.** Run K independent windowed `extract_full` accumulations from empty
   (cursor nulled) → merge into one consolidated DiagramData → reconcile that
   consolidated picture against the *current committed* diagram via
   `match_people` to emit a delta PDP (negative-ID adds for missing people, new
   pair-bonds bridging already-committed fragments, positive-ID edits for missing
   parent links). Staged into `diagram_data.pdp`; user reviews/accepts in the
   existing PDPSheet. Preserves committed IDs, manual edits, layout. Per
   PDP_DATA_FLOW.md / DATA_SYNC_FLOW.md the PDP *is* the delta system.
2. **Merge dedup MUST use `f1_metrics.match_people`** (structural+name), not the
   prototype's raw-name canonicalization. The prototype hit 94.9% LCC via
   name-dedup (forbidden per FD-324); match_people is the sanctioned swap and
   must be re-verified to clear the ≥90% AC.
3. **Default K=6** (the only consensus tier measured ≥90%, 94.9%); K=4 is the
   cheaper opt-down. Chosen over K=4-default because K=4 single-consensus is
   unproven against the "reliably ≥90%" AC. ~$0.46/rebuild.
4. **Temporary cost-confirm modal** on the Rebuild button (warns ~$0.50/run to
   AFS, says check with patrick@alaskafamilysystems.com first), tagged in-code
   for removal once a customer pricing model exists. Accepted as interim cost
   control pre-pricing.

**Reasoning:** The PDP delta path is the documented mechanism for all diagram
changes and the only non-destructive option. K=6 trades cost for AC compliance.

**Revisit trigger:** match_people merge fails to reach ≥90% LCC reliably on
diagram 1924; customer pricing model lands (remove the cost modal); K=4 later
proven reliable (demote default).

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

---

## 2026-05-16: FD-331 re-extraction/accept concurrency safety; stacked on uncommitted FD-319

**Context:** FD-331 fixes three concurrency defects in FD-319's re-extraction cursor (unguarded /extract, unversioned commit-pdp diagram write, non-atomic Statement.order). FD-319's implementation was discovered to be uncommitted working-tree state in ~/worktrees/FD-319, not on the FD-319 branch.

**Options considered:** (a) wait for FD-319 to be committed; (b) reimplement the cursor on master; (c) carry FD-319's WIP into the FD-331 worktree as a labeled base commit and stack FD-331 on top.

**Decision:** (c). One base commit per repo carries FD-319 WIP verbatim ("rebased away once FD-319 lands"); FD-331's own commits sit on top so the reviewable diff is only the concurrency fix.

**Reasoning:** FD-331 structurally depends on FD-319 code; waiting blocks the work. Carrying as a separate base commit keeps FD-331's delta clean and the eventual rebase mechanical. The FD-319 worktree/branch was left untouched (Patrick's active WIP).

**Fixes:** (1) next_order() takes SELECT FOR UPDATE on the Discussion row (Postgres-enforced; SQLite no-op). (2) /extract claims an atomic `extracting` flag (409 on overlap) and writes the diagram via optimistic version check (409 stale). (3) commit-pdp writes via version-checked bounded retry; cursor advance bound to client-supplied accepted_through_order, not current pending — falls back to pending for legacy clients.

**Revisit trigger:** FD-319 lands (rebase, drop base commit); or true-concurrency Postgres test harness added (the row-lock fix is currently only regression-guarded on SQLite).

---

## 2026-07-22: gemini-3.6-flash recommended as extraction upgrade; E4 metric era started

**Context:** Extraction experiment on newly released gemini-3.6-flash (worktree `~/worktrees/gemini-3.6-flash/`, report `fdserver/training/induction-reports/2026-07-22_07-56-26--gemini-3.6-flash/`). Same-day prod baseline re-measured for comparability.

**Options considered:** (a) status quo (flash-lite / 3-flash); (b) 3.6-flash extraction only; (c) all-3.6-flash including Pass-3 SARF self-review; (d) flash-lite extraction + 3.6-flash reviewer (cheap hybrid).

**Decision (pending Patrick's sign-off):** (c) all-3.6-flash. E4 final ruler (3-run means): Events 0.544 vs 0.413, Agg 0.704 vs 0.652, flash-tier cost, ~76s/disc (2.4x prod — fine async, borderline sync). SARF macro noisy but above prod (batch means 0.451/0.392 vs 0.367/0.359). (d) rejected: reviewer upgrades don't rescue lite extraction (interim-ruler SARF 0.349 < prod 0.367).

**Also decided:** two scorer fixes on the experiment branch (f1_metrics.py) define benchmark era E4: (1) couple-slot symmetric event matching (fixes a documented cross-model bias, prod Events +0.051); (2) year-precision dates — Patrick chose changing the scorer over re-coding GT: Jan-1 + certain = year-only fact, matches any same-calendar-year date. Headline configs re-measured on the final ruler: self-review 0.544/0.704 (Events/Agg) vs prod 0.413/0.652. f1_timeseries needs an era-break entry when committed.

**Reasoning:** Largest Gemini-family quality jump measured on this benchmark; the only cheaper alternative with comparable Events F1 is claude-fable-5 at 2–3 orders of magnitude higher cost and worse latency.

**Revisit trigger:** 3.6-flash pricing/latency changes; GT date-certainty tooling fix (would shift all Events numbers); mobile sync-path latency budget decision.
