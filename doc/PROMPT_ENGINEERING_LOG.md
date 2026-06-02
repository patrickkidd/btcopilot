# Prompt Engineering Context

**Purpose**: Authoritative record of prompt engineering decisions, experiments, and lessons learned for the SARF data extraction system. Prevents regressions by documenting what works, what doesn't, and why.

**Last Updated**: 2026-06-02 (FD-324 real-chat measurement + corrected conclusion)

---

## FD-324 — Real-chat LCC measurement + failure-mode classification (2026-06-01)

**Scope**: Extends prior FD-324 synthetic work. Adds `--accumulate` mode to
`connectivity_check.py` for reproducible real-chat LCC measurement. Measures
both real-chat user diagrams. Classifies disconnected people into failure modes.

### Accumulate mode

`connectivity_check.py --accumulate 55,58,60` extracts each discussion in
order, commits the PDP to DiagramData, and passes the committed state to the
next discussion — mirroring live diagram growth. This is the authoritative LCC
metric for real-chat scenarios (stored-diagram LCC is invalid: it reflects
historical drift, not pipeline output).

### Cold baseline (fix REVERTED — `infer_parents_from_birth_events` disabled)

| Source | Baseline LCC% |
|--------|--------------|
| 1924 Patrick (discs 55,58,60) | 23.1% |
| 1589 Guillermo (discs 28,57) | 84.6% |
| Synthetic GT avg (6 discs) | 79.1% |

### With fix (current FD-324 worktree)

| Source | Baseline LCC% | Fixed LCC% | Δ |
|--------|--------------|------------|---|
| 1924 Patrick (discs 55,58,60) | 23.1% | 30.0% | +6.9pp |
| 1589 Guillermo (discs 28,57) | 84.6% | 88.5% | +3.9pp |
| Synthetic GT avg (6 discs) | 79.1% | 86.2% | +7.1pp |

Synthetic ≥80% target: **MET** (86.2%). Guillermo ≥80% target: **MET** (88.5%).
Patrick ≥80% target: **NOT MET** (30.0%) — see failure mode analysis below.

### F1 no-regression check (with fix, production prompts, 6 GT synthetic, 2 runs)

| Metric | Run 1 | Run 2 | vs. prior baseline (0.651) |
|--------|-------|-------|---------------------------|
| Aggregate F1 | 0.654 | 0.633 | within noise |
| People F1 | 0.940 | 0.935 | within noise |
| Events F1 | 0.437 | 0.401 | within noise |
| PairBonds F1 | 0.790 | 0.772 | within noise |
| ParentChild F1 | 0.812 | 0.816 | retained |

No F1 regression. Run-to-run variance ±0.021 on aggregate (within known ±0.05–0.10 noise).

### Failure-mode classification: Patrick diagram (1924)

After accumulation (20 people, 11 components, LCC=6, LCC%=30%):

Committed people in the diagram span two family groups:
- **Stinson family**: Connie, Alyssa, Sam, Julie, Robert — last_name=Stinson, extraction also produced pair bonds Sam-Alyssa and Robert-Julie. These look like sibling-couples.
- **O'Malley family**: Jim O'Malley, Elizabeth O'Malley — connected via bond #6.
- **Cross-link**: Elizabeth-Robert bond (#7) connects O'Malley and Stinson clusters. Client is a child of Elizabeth+Robert.
- **LCC (6 people)**: Elizabeth, Jim, Robert, Julie, Client, Connie — connected via bonds #5, #6, #7, #26.
- **Disconnected**: Sam-Alyssa couple (2 people), Meredith-Vance couple (2 people), Monique/Joseph/Julia/Anthony singletons (4 people).

**Mode (a) duplicates**: Possible — Robert appears in two pair bonds (Elizabeth-Robert #7 and Robert-Julie #5). This could indicate the conversation discussed Robert in two different relationship contexts; not a duplicate person but possibly an erroneous second bond. Frequency too low to address with a targeted prompt change.

**Mode (b) implicit-spouse / implicit-sibling**: Sam, Alyssa, Julie, Robert, Connie all share last_name=Stinson, strongly suggesting a sibling group. Connecting them to a shared parent pair would link the Sam-Alyssa isolated couple into the main tree. However, fixing this requires inferring parent bonds from shared last names — which is name-matching, explicitly rejected per ticket rules. Out of scope.

**Mode (c) truly isolated**: ONLY Monique (ex-girlfriend, no other relative) is genuinely
isolated. Joseph/Julia/Anthony are NOT — disc 60 explicitly states "Jim and Sheila are
the parents of Anthony, Joseph, Julia" and the user demanded the link be set; Vance/Meredith
are Connie's sister + her husband (stated); Sam is the user's half-brother (stated). These
are extraction failures, not missing source structure.

**Conclusion (CORRECTED 2026-06-02 — supersedes the original below)**: Patrick's low LCC is
NOT content-bounded. The relationships ARE in the transcript; fresh extraction recovers only
~22 of 32 people and sets ~0-3 parents. Real causes are architectural: (1) single-shot
re-extraction of a 200+ statement conversation under-extracts and drops parent links;
(2) facts arrive across sessions (the children's mother is named only in a later session
than the children), and the pipeline never back-fills parents on already-committed people.
The lever is the cursor/windowing re-extraction architecture (FD-319, child_of 0.63→0.73),
NOT prompt wording: four prompt-directive variants (incl. proband-linking and committed-
back-fill) left Patrick within noise (25-29%). Guillermo, described within single
discussions, reaches ~95% with the prompt fixes.

> ~~Original (incorrect) conclusion: "Patrick's real-chat LCC is bounded by source text
> content... not a fixable extraction failure." Disproved — relationships are explicitly
> stated; the gap is architectural under-extraction/back-fill, not content.~~

### Failure-mode classification: Guillermo diagram (1589)

After accumulation (26 people, 4 components, LCC=25, LCC%=96.2%):
Wait — `--accumulate 28,57` with fix measured 88.5% in the repeated run above.

Disconnected: Irene, Sharon, Alvie — 3 singletons.
All are mode **(c) truly isolated**: mentioned by name in Guillermo's conversation but with no stated relationship to his family. No prompt change applicable.

Guillermo already meets ≥80% (88.5%). No action needed.

### AC2 status: LCC ≥80% excluding User/Assistant

| Source | LCC% | AC2 met? |
|--------|------|---------|
| 1589 Guillermo (real-chat) | 88.5% | ✓ |
| Synthetic avg (6 GT discs) | 86.2% | ✓ |
| 1924 Patrick (real-chat) | ~25-30% | ✗ — architecturally blocked (NOT content-bounded) |

AC2 partially met. Patrick does not reach 80%, but the relationships ARE stated in the
transcript — the gap is architectural (single-shot under-extraction + no cross-session
parent back-fill), addressable via the FD-319 cursor/windowing re-extraction, not prompt
wording. Numbers here are the keep-User metric on single-shot re-extraction of a truncated
discussion slice, which understates the live incrementally-built diagram (32 stored people
vs ~22 fresh).

### AC4 disposition

| Failure mode | Status |
|---|---|
| (a) Duplicates | Accepted: rare in this data, no systematic pattern warranting a prompt change |
| (b) Implicit spouse/parent missing PairBond | Addressed by Pass-1 prompt fixes (fdserver #23): emit both bond partners + delete the ID-ordering contradiction |
| (c) Truly isolated mentions | Only genuine case is Monique (ex-girlfriend); the rest are stated-but-unextracted (architectural, see corrected conclusion) |

---

## FD-324 — Connectivity: infer_parents_from_birth_events repair (2026-05-20)

**Objective**: Improve family-tree connectivity (LCC %) from ~51% baseline to ≥80%
target, without F1 regression.

**Baseline** (production prompt, production pdp.py, 6 GT discussions, 1 run):

| Metric | Score |
|---|---|
| Aggregate F1 | 0.655 |
| People F1 | 0.920 |
| Events F1 | 0.408 |
| PairBonds F1 | 0.828 |
| **ParentChild F1** | 0.366 (recall=0.332) |
| Average LCC % | 51.0% (5 discs, 1 failed) |

**Root cause identified**: Person.parents was not being set despite pair bonds
being extracted correctly. The LLM follows a people-first ID assignment order
(people → events → pair_bonds), which requires forward-referencing pair bond IDs
not yet computed. In complex multi-generation families, this fails silently —
pair bonds are emitted with correct person references, but Person.parents fields
are left null. Result: only couple edges (2 nodes per bond) connect the graph;
parent-child edges (which span generations) are absent.

**Experiment A: PairBonds-first ID assignment — REJECTED**

Hypothesis: reversing the ID order (pair_bonds first) would let the LLM reference
pair bond IDs when creating Person objects.

Result: catastrophic F1 regression. Aggregate F1 dropped from 0.655 → 0.476
(-0.179). People F1 dropped from 0.920 → 0.757. ParentChild F1 = 0.000 (worse
than baseline). Events F1 below 0.3 target. The LLM was tuned on people-first
examples; the new order confused its ID assignment throughout.

**Decision: rejected, reverted.** Do not attempt ID order reversal without
rewriting all examples in the prompt (and re-validating on a fresh batch).

**Experiment B: infer_parents_from_birth_events deterministic repair — KEPT**

Implementation: added `infer_parents_from_birth_events(deltas)` to `pdp.py`,
called in `_extract_and_validate` after `fix_unresolved_person_refs`. The function
reads birth events with person+spouse+child set, finds the matching PairBond by
dyad, and sets Person.parents on the child if it is currently null. Purely
deterministic; no LLM; same pattern as `fix_committed_person_duplicates`.

Results (6 GT discussions, 1 run, production prompt unchanged):

| Metric | Baseline | Exp B | Δ |
|---|---|---|---|
| Aggregate F1 | 0.655 | 0.651 | -0.004 (noise) |
| People F1 | 0.920 | 0.902 | -0.018 (noise) |
| Events F1 | 0.408 | 0.448 | **+0.040** |
| PairBonds F1 | 0.828 | 0.822 | -0.006 (noise) |
| **ParentChild F1** | 0.366 | **0.782** | **+0.416 (+114%)** |
| ParentChild recall | 0.332 | **0.768** | **+0.436** |
| Average LCC % | 51.0% | **89.5%** | **+38.5 pp (target ≥80% ✓)** |

F1 non-regressed (all deltas within known run-to-run noise of ±0.05–0.10).
ParentChild recall nearly doubled. Connectivity improving dramatically on
early samples: disc 37 = 100%, disc 48 = 100%, disc 39 = 94.1%.

**Decision: kept.** The repair is the correct fix because:
1. No F1 regression
2. ParentChild F1 +114%
3. LCC % massively improved on real extractions
4. Deterministic — same rationale as `fix_committed_person_duplicates`
5. Prompt-only fix for this failure mode is not viable (forward-reference
   problem requires rewriting all examples, high regression risk)

**Related**: strategy doc §2b/§2b' for the dedup repair precedent.

---

## FD-325/326 — Returning-user-aware coach + current-events/intake balance (2026-05-16)

**Scope**: `_CONVERSATION_FLOW_CORE` + Opus/Gemini addenda (fdserver, private IP); `committed_state` plumbing; outstanding-categories engine; conversational judge.

**Extraction F1 not run — by design.** No extraction prompt was touched (extraction strategy, field descriptions, two-pass prompts unchanged). The change set is conversational-flow + a schema-derived coverage engine with no LLM. F1 measures extraction; there is no F1 surface here. Running it would burn cost to re-measure an untouched system.

**Prompt direction**: returning-user + current-events/depth guidance expressed as *guidelines, not rules*; checklist replaced with prose; addenda reduced to length cues; few-shot at end. Rationale: rule/turn-count AC produces a robotic coach (the explicit FD-326 anti-goal). Validation is qualitative via a dedicated judge, not keyword/turn counting.

**Quality measurement decision**: FD-326 uses a purpose-built LLM judge (`coacheval`, 4 dims: current-events engagement, name usage, no premature pivot, no theory-pitch) **instead of** `QualityEvaluator` response-type entropy. Finding: entropy mis-penalizes a coach that consistently does acknowledge+question turns — that consistency is correct coaching behavior but reads as low entropy. Entropy is a synthetic-client realism metric, not a coach-quality metric; applying it here produced false negatives. Future conversational features add their own judge dimensions following this pattern rather than reusing entropy.

**RETRACTED — invalid harness.** The first round of multi-turn results (reported as "17/18", "(b)-Gemini opener tic", "pattern (b): accept stay-present", "skip the opener") was produced by a harness bug: `ask()` does not commit; it relies on the caller persisting each turn (the production HTTP route commits per request). Both `coach_chat.py` and the smoke's `_multi_turn` looped `ask()` with no commit between turns, so `discussion.statements` never reloaded and **the coach had no within-session memory across turns**. Single-turn (a) and `committed_state`/name-usage were unaffected (committed_state is re-derived from the diagram each call). Patterns (b) and (c) and every conclusion about stonewalling/opener behavior drawn from them are void.

**Fix**: `db.session.commit()` after each `ask()` in both `coach_chat.py` and `_multi_turn`. Also `thinking.type` `enabled→adaptive` in `llmutil.claude_text` (SDK-deprecated; adaptive takes no `budget_tokens`; Anthropic states adaptive improves performance — so this also changes the model behavior under test).

**Prompt-IP question (Patrick) — lean rewrite reverted.** Diff vs the pre-rewrite prompt showed the "lean" version deleted literature-derived clinical content (fact-level minimum dataset, symptom-then-connect method, the "done" definition) and gutted tuned addenda (Opus 66→4, Gemini 22→3 lines). The rules-based coverage engine detects a *structural gap*; it does not carry the clinical *content/rationale* — engine and literature checklist are complementary, not substitutes. Reverted to the original literature core + original addenda. Only additive changes kept: `committed_state` plumbing; an FD-325 "working memory" block (use known names, don't re-ask known facts, engine feeds the outstanding list); and the canned-empathy opener family added to the existing AVOID-clichés list.

**Return-pivot now measured.** Added judge dimension `returns_to_collection` (topic winds down → coach bridges to a real missing area; true when not applicable). The FD-326 promise had been unmeasured (only a negative no-premature-pivot guard). Also fixed silent meter corruption: gemini-2.5-flash truncates the judge JSON tail intermittently and crashed the test (was dropping (b)-Opus); parser now recovers the five gating booleans by regex.

**Stability — restored prompt + 5-dim judge (3× e2e, 6/run, meter reliable):**
- (a) opening-current-events: Opus + Gemini **6/6** — solid.
- (c) long-session: Opus + Gemini **6/6** incl. return-pivot — solid.
- (b) sustained-stonewall script: fails both models at turn 10 (clumsy theory-pitch bridge, or no bridge). Out of scope per Patrick's standing decision ("not worth dealing with stonewalling regardless of model"); does not occur in normal long sessions (c is clean).

**Conclusion**: option (a) succeeds for in-scope behavior on both models. No fallback to the rewrite; no further stonewalling work. The literature clinical IP is preserved; FD-325 returning-user awareness works via the additive working-memory block; the return-pivot is now a measured, passing behavior in normal sessions.

**Test-infra root causes (both = silent-fallthrough class; fix in conftest)**:
1. `FDSERVER_PROMPTS_PATH` — without it, e2e tests silently load the open-source prompt stub instead of the real fdserver prompts, making all prompt validation meaningless. `btcopilot/tests/conftest.py` now sets it before importing btcopilot; `coach_chat.py` sets it itself. Root cause of pre-handoff iterations 1–5 producing wrong behavior.
2. `.env` not auto-loaded for pytest, and `.env` cannot be `source`d (`FLASK_APP=...create_app()` is invalid bash). e2e smoke needs `ANTHROPIC_API_KEY`/`GOOGLE_GEMINI_API_KEY` extracted per-line, and must run from the btcopilot rootdir (the theapp-root `pytest.ini` lacks `--e2e`). Recommend conftest export both keys from `.env` via line-parse, not source.

**Data-model resolution (1924 incident)**: Committed Personal-app family data lives in `DiagramData.people/events/pair_bonds` (Scene collections), dates always QDateTime — never in `.pdp` (pending pool, cleared on commit) and never ISO. Desktop `Scene.write()` and Personal `commit_pdp_items()` converge on the same collections/keys (`person_a/person_b`, `person.parents`→pair_bonds entry, `gender`, lowercase `EventKind`). No intake.py linkage rewrite needed (contradicts the handoff's working assumption). The 1924 "empty pair_bonds Scene format" observation matches the post-corruption 2-person state from a pre-sandbox coach_chat overwrite, not an unhandled schema. Contract pinned by `test_committed_scene_format_contract` and verified on three real populated desktop clinic diagrams (332/98/70 people): `person.parents`→`pair_bonds` resolves 100%, dates QDateTime, no Qt/enum leak. Grinding real desktop data exposed two production crashes synthetic fixtures missed — `name=None` scene stubs and `relationship` stored as a `RelationshipKind` enum object — both fixed and pinned (`test_real_desktop_quirks_dont_crash`, 11/11 intake).

---

## Conversation Flow Prompts (2026-03-15)

### Core Prompt Rewrites — Terminal Directive, Exchange Counts, Pivot Logic

**Problem**: Opus conversations were mostly bare questions with early topic pivots. Root causes: terminal directive hardcoded question-asking, phase exchange counts created artificial urgency, "8+ statements" red flag punished staying with a topic.

**Changes (all shipped)**:
- Replaced "Ask for the next missing data point" with menu of response types (observation, bridge, normalization, question)
- Removed exchange counts from all phase headers
- Rewrote pivot section: removed scripted pivot line, removed "8+" red flag, added "keeps asking questions without observations" red flag

**Results**: Response type entropy improved from near-zero to ~1.0 across all personas. Gemini also improved (no regression from shared core changes). See `doc/log/synthetic-clients/2026-03-15_19-00--opus-conversational-prompt-tuning.md` for full metrics.

### Thinking Budget = 0 (REJECTED)

Disabling extended thinking caused sentence completion (AI fabricates user's words), context loss, and loss of strategic pivot ability. Coverage collapsed on oversharing persona (64% → 27%). Thinking budget stays at 4096.

**Lesson**: Extended thinking is essential for strategic state tracking in multi-turn conversations. The "checklist auditing" behavior it enables is a feature for data collection, not a bug — the problem was the terminal directive channeling all that planning into bare questions.

### Architecture: Callable Override

Conversation flow prompts now use a callable override (`get_conversation_flow_prompt(model)`) instead of constant overrides. fdserver has full per-model assembly control.

---

## Model Selection

### Current: Gemini 2.5 Flash (extraction) / Gemini 3 Flash Preview (responses)

**Extraction**: gemini-2.5-flash (production), gemini-3-flash-preview (recommended upgrade)
**Responses**: gemini-3-flash-preview (conversational chat responses)
**Thinking**: `thinking_budget=1024` (CRITICAL — see T7-20 findings below)

**Why Gemini 2.5 Flash for extraction:**
- gemini-2.0-flash deprecated March 31, 2026 and showing server-side drift
- Aggregate F1 within 3% of 2.0-flash, better SARF variable scores
- 64K output token limit supports large imports

**Recommended upgrade: gemini-3-flash-preview (validated 2026-03-04):**
- +6.7% Aggregate F1, +9.1% Events F1 vs 2.5-flash (both with thinking=1024)
- 23% faster (74s vs 96s for 6 discussions)
- $0.016/extraction vs $0.012 — negligible cost increase
- Confirmed best across 14 model configs spanning Google, OpenAI, and xAI
- Needs multi-run validation (3+ runs) before production deployment
- See full report: `doc/induction-reports/2026-03-04_15-36-39--model-evaluation-frontier/`

**Non-Google alternatives evaluated (2026-03-04):**
- gpt-5.2 (OpenAI): Events F1 tied (0.397) but Bonds -37%, 196s latency, $0.065/extraction. Best backup.
- gpt-5-mini (OpenAI): Highest Events F1 (0.410) but 460s latency, 1/6 failures. Monitor only.
- o4-mini, gpt-4.1, gpt-5-nano, grok-4-fast, grok-4-1-fast: All below baseline or disqualified on latency.
- All non-Gemini models require compatibility shims (0→None, positive→negative ID remapping, API param differences).

**Why Gemini 2.0 Flash over GPT-4o-mini:**
- Larger context window (1M tokens vs 128K)
- Lower cost per token
- Native structured JSON output
- Better performance on classification tasks in our testing

**Model names configurable** via `LLM.extractionModel`, `LLM.extractionModelLarge`, `LLM.responseModel` class attributes. CLI override: `--model` on `run_prompts_live.py`.

---

## Known Gemini 2.0 Flash Issues

### 1. Value Repetition in Nested Arrays

**Issue**: Gemini may repeat values indefinitely until token limit when processing nested arrays of objects.

**Affected fields**:
- `Event.relationshipTargets: list[int]`
- `Event.relationshipTriangles: list[int]`

**Mitigation**: Runtime instrumentation in `btcopilot/pdp.py` logs `GEMINI_ARRAY_ISSUE` warnings when duplicate values detected. Monitor logs - if frequent (>5% of extractions), consider schema flattening.

### 2. Missing Expected Fields

**Issue**: Gemini may omit expected fields from output, especially with complex nested structures.

**Mitigation**: All required fields are non-Optional in dataclass schema. pydantic_ai handles this automatically.

### 3. Prompt Order Sensitivity

**Finding**: Gemini documentation suggests few-shot examples early in prompts improve quality.

**Current assembly order** (`btcopilot/pdp.py`):

Per-statement (training app only):
```python
data_extraction_prompt = (
    DATA_EXTRACTION_PROMPT      # 1. Extraction intent + brief overview
    + DATA_EXTRACTION_EXAMPLES  # 2. Few-shot examples EARLY
    + DATA_EXTRACTION_RULES     # 3. Detailed schema/rules
    + DATA_EXTRACTION_CONTEXT   # 4. Actual data to process
)
```

Full extraction (production, 2-pass):
```python
# Pass 1: People + PairBonds + Structural Events
prompt1 = DATA_EXTRACTION_PASS1_PROMPT + DATA_EXTRACTION_PASS1_CONTEXT
# Pass 2: Shift Events + SARF (given Pass 1 output)
prompt2 = DATA_EXTRACTION_PASS2_PROMPT + DATA_EXTRACTION_PASS2_CONTEXT
```

---

## Critical Lessons Learned

### 1. Prompt Size Matters - Less is More

**Experiment (Dec 2024)**: Added exhaustive SARF definitions from literature review to extraction prompt.

**Result**: F1 scores degraded significantly.

**Analysis**: Prompt doubled in size (37K → 74K chars). The model was overwhelmed with too much definitional context and lost focus on the extraction task.

**Fix**: Removed verbose SARF definitions, restored concise operational definitions. Exhaustive definitions preserved in `btcopilot/doc/SARF_EXTRACTION_REFERENCE.md` for human reference only.

**Lesson**:
- Extraction prompts need concise, actionable guidance - not academic definitions
- More context ≠ better extraction
- Keep prompts focused on the task, not the theory

### 2. Dataclass Constraint (Cannot Use Pydantic Models)

**Constraint**: Schema must use Python `dataclasses`, not Pydantic models.

**Reason**: Dataclasses are required for embedding in Pro and Personal desktop apps (PyQt). Pydantic models have dependencies that don't work in the embedded environment.

**Implication**: Cannot use Pydantic's `Field(description="...")` to add descriptions to the JSON schema. All semantic guidance must be in prompt text instead.

### 3. Few-Shot Examples Are Critical

**Finding**: Gemini responds well to concrete examples of correct vs incorrect output.

**Current approach**: `DATA_EXTRACTION_EXAMPLES` contains labeled error patterns:
- `[OVER_EXTRACTION_GENERAL_CHARACTERIZATION]` - Don't create events for general feelings
- `[UNDER_EXTRACTION_BIRTH_EVENT]` - Always create birth events when birth dates mentioned
- `[UNDER_EXTRACTION_PEOPLE_INDIRECT_MENTION]` - Extract people mentioned indirectly
- `[RELATIONSHIP_TARGETS_REQUIRED]` - Always populate relationshipTargets

**Lesson**: Each common error pattern should have a labeled example in the prompt.

### 4. Extraction Intent Must Be Explicit

**Finding**: Starting with clear extraction task description improves quality.

**Current approach**: `DATA_EXTRACTION_PROMPT` begins with:
```
**Extract the following information from the user statement:**
1. **NEW people** mentioned for the first time
2. **NEW events** - specific incidents at a point in time
3. **UPDATES** to existing people
4. **DELETIONS** when user corrects previous errors
```

---

## Prompt Architecture

### File: `btcopilot/btcopilot/personal/prompts.py` (defaults) / `fdserver/prompts/private_prompts.py` (overrides)

**Conversation flow** (multi-model, assembled at runtime):
| Constant | Purpose | Location |
|----------|---------|----------|
| `_CONVERSATION_FLOW_CORE` | Domain knowledge, phases, data checklist | btcopilot (shared) |
| `_CONVERSATION_FLOW_OPUS` | Response style for Claude Opus | fdserver (stub in btcopilot) |
| `_CONVERSATION_FLOW_GEMINI` | Response style for Gemini Flash | btcopilot |

**Per-statement extraction** (training app only):
| Constant | Purpose | Template Variables |
|----------|---------|-------------------|
| `DATA_EXTRACTION_PROMPT` | Extraction intent + data model overview | `{current_date}` |
| `DATA_EXTRACTION_EXAMPLES` | Few-shot error pattern examples | None (literal JSON) |
| `DATA_EXTRACTION_RULES` | Operational extraction guidance | None |
| `DATA_EXTRACTION_CONTEXT` | Runtime data to process | `{diagram_data}`, `{conversation_history}`, `{user_message}` |

**Full-extraction constants** (production, 2-pass):
| Constant | Purpose | Template Variables |
|----------|---------|-------------------|
| `DATA_EXTRACTION_PASS1_PROMPT` | Pass 1: People + PairBonds + structural events | `{current_date}` |
| `DATA_EXTRACTION_PASS1_CONTEXT` | Pass 1 runtime data | `{diagram_data}`, `{conversation_history}` |
| `DATA_EXTRACTION_PASS2_PROMPT` | Pass 2: Shift events + SARF coding | `{current_date}` |
| `DATA_EXTRACTION_PASS2_CONTEXT` | Pass 2 runtime data | `{pass1_data}`, `{conversation_history}` |

**Why split into multiple constants**:
1. Examples contain literal JSON with curly braces - keeping them separate avoids escaping issues with `.format()`
2. Makes it clear which parts have template variables
3. Easier to maintain and test independently

### Prompt Size Guidelines

| Metric | Target | Current |
|--------|--------|---------|
| Per-statement prompt chars | <50K | ~41K |
| Per-statement lines | <1000 | ~960 |
| Per-statement examples | 5-10 | 9 |
| Pass 1 prompt (full) | — | ~150 lines |
| Pass 2 prompt (full) | — | ~225 lines |

---

## What NOT to Include in Extraction Prompts

Based on failed experiments:

1. **Academic definitions** - The "What X IS" / "What X is NOT" discriminators from literature review. Too verbose, confused the model.

2. **Observable marker tables** - Long tables of indicators. Model doesn't need this level of detail for extraction.

3. **Theoretical background** - Why constructs exist, how they relate to each other. Irrelevant for extraction task.

4. **All possible enum values** - Only document values that are commonly confused or have special rules.

**Rule**: If it reads like a textbook, it doesn't belong in an extraction prompt.

---

## What TO Include in Extraction Prompts

1. **Concise field definitions** - One-liner descriptions of what each field means operationally.

2. **Critical rules** - Things the model commonly gets wrong (e.g., "relationshipTargets is REQUIRED").

3. **Labeled examples** - Concrete wrong/right output pairs for common error patterns.

4. **Extraction intent** - What to extract, what not to extract.

5. **ID assignment rules** - Negative IDs for new items, how to avoid collisions.

---

## Monitoring & Metrics

### F1 Score Tracking

- **Full-extraction harness**: `uv run python -m btcopilot.training.run_extract_full_f1` (production 2-pass, 6 GT discussions)
- **Per-statement harness**: `uv run python -m btcopilot.training.run_prompts_live` (training app, 45 GT cases)
- **Ground truth**: `instance/gt_export.json` (symlinked from btcopilot-sources)
- **Metrics tracked**: Aggregate F1, People F1, Events F1, PairBonds F1, per-variable F1 (symptom, anxiety, relationship, functioning)

### Gemini Issue Detection

- **Log pattern**: `GEMINI_ARRAY_ISSUE` in application logs
- **Threshold**: If >5% of extractions show array issues, consider schema changes

### Prompt Induction Reports

- **Location**: `doc/induction-reports/<timestamp>/`
- **Contains**: Iteration logs, F1 deltas, final report

---

## Future Improvements (Deferred)

See `btcopilot/doc/TODO_GEMINI_SCHEMA.md` for:

1. **Convert to Pydantic with Field descriptions** - Blocked by PyQt embedding constraint
2. **Flatten triangle arrays** - Deferred pending evidence of issues
3. **TypeAdapter for enhanced JSON schema** - Not implemented, relying on pydantic_ai defaults

---

## Related Files

| File | Purpose |
|------|---------|
| `btcopilot/btcopilot/personal/prompts.py` | Extraction prompt defaults (empty stubs for private prompts) |
| `fdserver/prompts/private_prompts.py` | Real extraction prompts (PASS1/PASS2 + per-statement) |
| `btcopilot/btcopilot/pdp.py` | Prompt assembly + extraction pipeline (2-pass + per-statement) |
| `btcopilot/btcopilot/schema.py` | Dataclass definitions |
| `btcopilot/doc/TODO_GEMINI_SCHEMA.md` | Deferred Gemini optimizations |
| `btcopilot/doc/SARF_EXTRACTION_REFERENCE.md` | Exhaustive SARF definitions (reference only) |
| `btcopilot/doc/sarf-definitions/` | Literature review source material |
| `btcopilot/btcopilot/training/prompts/induction_agent.md` | Prompt induction meta-prompt |

---

## Decision Log

### Dec 2024: Remove exhaustive SARF definitions from prompt

**Context**: Commit `f6a7ee8` added comprehensive SARF definitions from literature review, doubling prompt size.

**Outcome**: F1 scores degraded significantly.

**Decision**: Reverted to concise operational definitions. Preserved exhaustive definitions in separate reference file.

**Lesson**: Extraction prompts need focused, actionable guidance - not academic background.

### Dec 2024: Gemini 2.0 Flash prompt ordering

**Context**: Gemini docs suggest few-shot examples early improve quality.

**Decision**: Reordered prompt assembly: PROMPT → EXAMPLES → RULES → CONTEXT

**Status**: Active, monitoring F1 impact.

### Mar 2026: Full-extraction prompt optimization (9 iterations)

**Context**: Manual session optimizing `DATA_FULL_EXTRACTION_CONTEXT` in `fdserver/prompts/private_prompts.py` for the `extract_full()` pipeline. Tested on 6 GT discussions (36/37/39/48/50/51) using gemini-2.5-flash.

**Baseline**: Events F1 = 0.302 (avg across 6 discussions).

**Results**: 9 iterations, 1 kept (V9), 7 reverted, 1 superseded. Final Events F1 = 0.335 avg (3 runs), best single run 0.367.

**What worked (V9)**: Minimal intervention — quality hints layered on original "extract everything" prompt:
1. Scene-detail suppression with concrete examples ("slammed door", "made a drink" = not clinical events)
2. Birth event reminder with age calculation formula
3. Relationship type disambiguation (projection vs overfunctioning, inside vs conflict)
4. Deduplication guidance
5. Soft calibration ("15-30 events typical")

**What failed (V1-V7)**:
- Aggressive consolidation rules → model ignored them or killed TP proportionally to FP
- "IGNORE" / "DO NOT APPLY" framing → destroyed useful per-statement event detection
- "Follow BUT override" framing → model reverted to per-statement behavior (76 events)
- Person-centric extraction → no improvement in event selection quality
- Hard count targets → model drops events randomly, not by significance
- Pre-transcript rule placement → less effective than post-transcript

**Key lesson**: The 1770 lines of per-statement training examples dominate model behavior. Full-extraction context (~50 lines) cannot override this. The correct strategy is minimal quality hints layered on top of per-statement training, not overrides or rewrites.

**Additional finding**: Description style mismatch (GT verbatim words vs AI clinical summaries) is the binding constraint on Events F1. Any consolidation that abstracts descriptions hurts matching. Raising similarity threshold from 0.4 to 0.5 is theoretically correct but hurts measured F1.

**Report**: `doc/induction-reports/2026-03-03_08-20-00--full-extraction/`

### Dec 2024: Add Gemini array issue instrumentation

**Context**: Known Gemini 2.0 Flash issue with nested arrays causing value repetition.

**Decision**: Added runtime detection in `pdp.py` to log `GEMINI_ARRAY_ISSUE` warnings.

**Status**: Active, monitoring frequency.

### Feb 2026: Gemini 3 Flash Preview extraction evaluation

**Context**: Evaluated switching extraction from gemini-2.0-flash/2.5-flash to gemini-3-flash-preview for potential quality improvements. Also made model names configurable via `LLM` class attributes and added `--model` CLI arg to `run_prompts_live.py` for A/B testing.

**Results** (45 GT cases):

| Metric | gemini-2.0-flash (baseline) | gemini-2.5-flash | gemini-3-flash-preview |
|--------|----------------------------|------------------|------------------------|
| Aggregate F1 | **0.327** | 0.241 (-26%) | 0.188 (-43%) |
| People F1 | **0.743** | 0.701 | 0.582 |
| Events F1 | **0.217** | 0.134 | 0.101 |
| Symptom F1 | 0.222 | 0.111 | **0.200** |
| Anxiety F1 | 0.207 | 0.111 | **0.200** |
| Relationship F1 | 0.244 | 0.133 | **0.222** |
| Functioning F1 | 0.244 | 0.133 | **0.200** |

**Decision**: Keep gemini-2.0-flash for extraction (small), gemini-2.5-flash for large imports. Use gemini-3-flash-preview only for conversational responses.

**Rationale**: Each successive model generation performed worse on aggregate extraction despite being "better" overall. Prompts and few-shot examples were tuned for gemini-2.0-flash behavior. Newer models respond differently to the same prompt structure. SARF variables showed slight improvement on 3-flash but not enough to offset the people/events regression.

**Lesson**: Model upgrades don't automatically improve extraction when prompts were tuned for a specific model. Moving extraction to a newer model requires prompt re-tuning via the induction workflow.

### Feb 2026: gemini-2.0-flash server-side regression and model migration

**Context**: Aggregate F1 dropped from 0.327 to ~0.257 with no code changes. Investigation confirmed: no GT data changes, no prompt changes, pinning `gemini-2.0-flash-001` produced identical results. Conclusion: server-side model behavior drift, likely related to 2.0-flash deprecation (March 31, 2026).

**Updated results** (45 GT cases, Feb 14 2026):

| Metric | gemini-2.0-flash | gemini-2.5-flash | gemini-3-flash-preview |
|--------|-----------------|------------------|------------------------|
| Aggregate F1 | **0.257** | 0.249 | 0.180 |
| People F1 | **0.718** | 0.718 | 0.582 |
| Events F1 | **0.179** | 0.154 | 0.081 |
| Symptom F1 | 0.200 | **0.205** | 0.178 |
| Anxiety F1 | 0.200 | **0.205** | 0.178 |
| Relationship F1 | 0.233 | **0.250** | 0.200 |
| Functioning F1 | 0.222 | **0.227** | 0.178 |

**Decision**: Switch all extraction to gemini-2.5-flash. The 3% aggregate gap vs 2.0-flash is within noise, SARF variable scores are better, and 2.0-flash is being deprecated.

**Config notes**: `thinking_config=ThinkingConfig(thinking_budget=1024)` enables thinking for quality (see T7-20 decision below). `max_output_tokens=65536` is within 2.5-flash limits.

### Feb 2026: Multi-turn prompt format evaluation

**Context**: Tested converting flat prompt (conversation history concatenated into system prompt) to Gemini's native multi-turn content structure, where prior conversation turns are passed as structured `(role, text)` tuples.

**Results** (gemini-2.5-flash, 45 GT cases):

| Metric | Flat prompt | Multi-turn | Delta |
|--------|------------|------------|-------|
| Aggregate F1 | **0.249** | 0.198 | -20% |
| People F1 | **0.718** | 0.680 | -5% |
| Events F1 | **0.154** | 0.133 | -14% |

**Decision**: Keep flat prompt format. Multi-turn causes 20% aggregate regression, more ID collision warnings, and worse people/events extraction. The model loses context about existing diagram_data when conversation history is separated from extraction instructions.

**Lesson**: Structured multi-turn is not automatically better for extraction tasks. The flat prompt keeps all context (instructions, examples, existing data, conversation, new statement) together, which helps the model track IDs and avoid re-extraction.

### Mar 2026: 2-pass split extraction (T7-18)

**Context**: Single-prompt `extract_full()` struggled with Events F1 (~0.47 with description-free matching). Hypothesis: splitting extraction into two focused passes would improve quality by reducing cognitive load per LLM call.

**Architecture**:
- **Pass 1**: Extract people, PairBonds, and structural events (birth, death, married, etc.) from full transcript
- **Pass 2**: Given Pass 1 output, extract shift events with SARF variable coding

Both passes route through `_extract_and_validate()` for retry/validation. Pass 2 receives `base_pdp=pass1_pdp` so validation runs against Pass 1's people/events.

**Results** (gemini-2.5-flash, 6 GT discussions, avg 2 runs):

| Metric | Baseline (single-prompt) | Split (2-pass) | Delta |
|--------|-------------------------|----------------|-------|
| Aggregate F1 | 0.595 | **0.669** | +12% |
| People F1 | 0.901 | 0.909 | +1% |
| Events F1 | 0.470 | **0.509** | +8% |
| PairBonds F1 | 0.539 | **0.832** | +54% |
| Completion | 4/6 (67%) | **6/6 (100%)** | fixed |

**Decision**: Replaced single-prompt `extract_full()` with 2-pass. Removed `DATA_FULL_EXTRACTION_CONTEXT`. The old single-prompt path no longer exists.

**Key observations**:
- PairBonds F1 improved dramatically (+54%) — Pass 1's focused scope catches bonds that were missed in the single all-at-once prompt
- 100% discussion completion vs 67% — smaller per-pass output avoids token limit failures
- Per-statement prompt constants (`DATA_EXTRACTION_PROMPT`, `DATA_EXTRACTION_EXAMPLES`, etc.) are NOT used by `extract_full()` — the split prompts are independent

**Lesson**: Task decomposition works. Splitting a complex extraction into two focused passes reduces cognitive load and improves quality on every metric. The key insight from the earlier 9-iteration experiment ("per-statement training dominates full-extraction context") motivated this split — instead of fighting the single-prompt format, we redesigned the pipeline.

### Mar 2026: thinking_budget=1024 + flash-lite model evaluation (T7-20)

**Context**: T7-20 (issue #59) was blocked by HTTP 500 errors from gemini-3.1-flash-lite-preview. After T7-18 split extraction landed, re-evaluated flash-lite viability. Discovered thinking_budget=0 was a critical quality bottleneck for both models.

**Experiments**: 14 runs across 12 configurations testing model (2.5-flash vs flash-lite), thinking budget (0/512/1024/2048/4096), temperature (0.0/0.1), and hybrid per-pass model selection. Multi-run averaging on key configs.

**Results** (multi-run averages, 6 GT discussions):

| Config | Events F1 | Aggregate F1 | Time | Cost |
|--------|-----------|-------------|------|------|
| 2.5-flash think=0 (was prod) | 0.265 | 0.545 | 62s | 1x |
| 2.5-flash think=1024 | **0.378** | **0.609** | 51s | 1x |
| flash-lite think=0 | 0.154 | 0.589 | 101s | 0.17x |
| flash-lite think=1024 | **0.368** | **0.600** | 50s | 0.17x |

**Decision**: Deploy thinking_budget=1024 immediately (one-line change). Switch to flash-lite when ready to optimize cost.

**CORRECTION**: Previous finding (Feb 2026) that "thinking+structured_output is catastrophic" is no longer true with the 2-pass split architecture. All 14 runs used thinking=1024 with structured JSON output — zero hangs, ~8s per pass.

**Thinking budget sweet spot** (flash-lite, Events F1): 0→0.154, 512→0.295, **1024→0.368**, 2048→0.298, 4096→0.355. Clear bell curve.

**What failed**: Hybrid models (flash-lite P1, 2.5-flash P2) don't beat homogeneous flash-lite+think. Temperature 0.0 vs 0.1 is noise. Thinking > 1024 causes over-reasoning.

**Report**: `doc/induction-reports/2026-03-04_13-15-00--model-evaluation-flash-lite/`

### Mar 2026: Description-free event matching (Strategy B)

**Context**: Debug analysis of FP events in split extraction revealed many were semantically valid extractions that GT describes differently. `Event.description` is free-text prose — it varies widely between AI and human annotators. Fuzzy string matching at 0.4 threshold was a hard gate rejecting legitimate matches.

**Change**: Removed `description` as both hard gate and soft scoring signal from `match_events()` in `f1_metrics.py`. Events now match on `kind + dateTime + person links` only. Weighted score simplified to `date_sim`.

**Results** (same extraction output, different matching):

| Metric | With description matching | Without (Strategy B) | Delta |
|--------|--------------------------|---------------------|-------|
| Events F1 | 0.335 | **0.470** | +40% |

**Decision**: Adopted. Description matching was measuring "do AI and GT use similar words" not "did AI find the right event."

**Risk**: If a person has 2+ genuinely different shift events within the 730-day date tolerance, they'll match incorrectly. Accepted as rare in practice with current GT dataset.

**Alternatives considered but deferred**:
- **SARF Signature Match** — match on SARF variable agreement instead of description. More precise than kind+date+person but adds complexity and creates circular dependency (SARF accuracy used for both matching and scoring).
- **SARF + Description hybrid** — demote description to low-weight tiebreaker. Most complex, still affected by paraphrasing variance.

### Mar 2026: Drop SARF operational definitions from Pass 3 review prompt

**Context**: Commit `fb1b603d` (fdserver) added `all_condensed_definitions()` (~62,886 chars / ~15,700 tokens) to the Pass 3 SARF review prompt. This comprised 98% of the prompt. A/B testing (3 runs each) showed marginal benefit: Aggregate F1 +0.006, SARF macro F1 +0.016 mean. This echoes the Dec 2024 lesson where exhaustive definitions degraded F1.

**Change**: Replaced the definitions-heavy prompt with a compact inline-rules version (~30 lines). Removed `all_condensed_definitions()` call from `pdp.py`, removed import of `sarfdefinitions` from `pdp.py`. Updated both `btcopilot/personal/prompts.py` and `fdserver/prompts/private_prompts.py`.

**Results** (3-run A/B mean, gemini-3-flash-preview, 6 discussions):

| Metric | With definitions | Without | Delta |
|--------|-----------------|---------|-------|
| Aggregate F1 | 0.647 | 0.641 | -0.006 |
| SARF macro F1 | 0.489 | 0.473 | -0.016 |
| Pass 3 prompt size | ~64K chars | ~1.5K chars | -98% |

**Decision**: Dropped. Cost/benefit strongly favors removal: ~15,700 fewer input tokens per extraction for negligible F1 difference within run-to-run variance. Reduces complexity and cost.

**Note**: `sarfdefinitions.py` and `all_condensed_definitions()` remain available — they are used independently by IRR calibration (Components A/B) via `calibrationprompts.py`.

### Mar 2026: Multi-model conversation prompt architecture

**Context**: After switching chat responses from Gemini Flash to Claude Opus 4.6, output degraded to terse single-line questions. The monolithic `CONVERSATION_FLOW_PROMPT` was tuned for Gemini's natural verbosity — its brevity constraints ("Keep responses brief", "One question per turn") are counterproductive for Opus, which is already terse by nature.

**Architecture change**: Split `CONVERSATION_FLOW_PROMPT` into:
- `_CONVERSATION_FLOW_CORE` — shared domain knowledge, phases, data checklist (btcopilot, open)
- `_CONVERSATION_FLOW_OPUS` — response style tuned for Claude Opus (fdserver, private IP)
- `_CONVERSATION_FLOW_GEMINI` — response style preserving existing Gemini behavior (btcopilot, open)

`get_conversation_flow_prompt(model)` assembles core + appropriate addendum at runtime. Override mechanism uses `hasattr` so fdserver only defines pieces it wants to override.

**Opus addendum design**: Combines stronger persona framing ("experienced consultant fascinated by family patterns") with response type rotation guidance (question/observation/bridging/normalizing turns), length calibration (2-4 sentences), and concrete good/bad response examples. The few-shot examples are the most reliable prompt intervention per prior extraction prompt findings.

**IP migration**: Tuned prompt content moved from btcopilot to fdserver. btcopilot retains only architectural stubs.

**Key insight**: Gemini and Opus have opposite natural tendencies. Constraints that guard Gemini from verbosity cause Opus to produce one-liners. Per-model addenda resolve this without compromising either model.

**Status**: Initial architecture deployed. No conversational quality metrics exist yet — next step is building a rubric-based evaluation framework to baseline and iterate the Opus addendum. See plan at `btcopilot/plans/opus-conversational-prompts.md`.

### May 2026: PASS1_CONTEXT committed-data carve-out (FD-319 prompt idempotency)

**Context**: FD-319 shipped a deterministic repair (`fix_committed_person_duplicates`)
as a safety net. Remaining ticket scope: measure the raw-LLM committed-duplicate rate
and test whether a prompt change reduces how often the repair must fire.

**Measurement** (PRODUCTION prompts, repair bypassed, Pass-1 only, N=10 ×
{gemini-3-flash-preview, gemini-3-pro-preview}):

| scenario | flash baseline | pro baseline |
|---|---|---|
| simple_people / simple_marriage | 0/10 | 0/10 |
| complex (15-person re-narration) | **10/10** (exactly 2 dup pair_bonds/run) | 1/10 |

Strategy doc §2b's 2026-03-05 "Resolved" claim was falsified at scale: the prior
prompt fix eliminated people/marriage re-emission but not committed **pair-bond**
re-emission by flash on a large committed state. The ticket's N=1 "people+marriage"
observation was a default-prompt artifact (`FDSERVER_PROMPTS_PATH` unset everywhere).

**Change**: one additive edit to `DATA_EXTRACTION_PASS1_CONTEXT` in
`fdserver/prompts/private_prompts.py`. The proximal directive
`EXTRACT: ... all pair bonds between couples/parents ...` had no committed
carve-out and beat the upstream "COMMITTED DATA — REFERENCE, DON'T RECREATE"
section + Example 6. Qualified to `All NEW ...` + an adjacent pair-bond-specific
`⚠️ ALREADY-COMMITTED ITEMS` block with a pre-return self-check. No working
content removed.

**Results**: raw committed-dup rate → 0/10 across all cells/models (flash/complex
1.00→0.00, pro/complex 0.10→0.00; simple cells unchanged at 0.00). F1 gate
(gemini-3-flash, 6 GT, avg 2 runs): people 0.925→0.919, events 0.474→0.518,
pair_bonds 0.820→0.845, aggregate 0.671→0.687 — all within run-to-run variance.

**Decision**: SHIP (pending Patrick commit of fdserver). F1 claim bounded to
"no regression" (N=2; documented 10-15% events stochasticity). Deterministic
repair stays load-bearing — the prompt reduces repair firing frequency, it does
not make the repair redundant (no idempotency guarantee at temperature 0.1 on
unseen inputs).

**Alternatives considered**: (a) prompt-only, drop the repair — rejected: stochastic,
no guarantee, prior "Resolved" already failed this way; (b) repair-only, no prompt
change — rejected: leaves flash at 100% raw dup on large states, repair load
unbounded; (c) enumerate committed IDs into PASS1_CONTEXT via a new format
placeholder — deferred: requires a `pdp.py` signature change, not needed since the
salience edit alone reached 0/10.

**Report**: `doc/induction-reports/2026-05-16_08-40-13--fd319-prompt-idempotency/`.
**Follow-up (non-blocking)**: 3-run F1 confirmation folded into next routine F1 run.

### May 2026: Structural-completion pass — rejected (negative result)

**Hypothesis**: a dedicated post-Pass-1 LLM pass to recover missing parent/child
and couple links would fix structural under-extraction.

**Measurement infra added (kept)**: isolated parent/child (`child_of`) recall/F1
metric in `f1_metrics.match_child_of`, surfaced in `run_extract_full_f1` and the
training F1 dashboard (also charted Pair Bonds, previously tracked but unplotted).
This metric stays regardless of the pass outcome.

**A/B (6 GT discussions, 2 runs, structural pass ON vs OFF)**:
parent/child recall 0.872→0.882 (+0.01, inside noise — this metric ranges
0.4–1.0 run-to-run); aggregate 0.690→0.670; events 0.517→0.480; pair-bonds
−0.01; people flat.

**Decision: rejected, reverted.** No recall signal above noise; net negative on
aggregate/events; adds an LLM pass + latency. Logged in strategy doc "things
that failed" #18.

**Reframe**: structural under-extraction is scenario-specific. Fresh single-shot
extraction already reaches ~0.87 parent/child recall. The low ~0.63 is specific
to re-extraction with committed context — and the cursor/windowing experiment
already lifts that (0.63→0.73). The cursor architecture is the lever for both
re-extraction idempotency and the re-extraction structural-recall gap; a separate
completion pass is not warranted.

### May 2026: Re-extraction cursor rule (FD-319) — kept

Prompt change: a cursor rule appended to Pass 1 when a discussion has an
accepted re-extraction cursor; the full conversation is context but only
content after a nonced marker is emitted. Measured (re-extraction scenario, 6
GT, 2 runs): committed-event re-emission ~⅓ down, parent/child recall
0.63→0.73, no F1 regression. Standard fresh-extraction F1 unchanged (cursor
inactive without an accepted cursor), so no f1_timeseries entry. Deterministic
committed-duplicate guard stays load-bearing — the rule reduces how often it
fires, it is not the safety mechanism. Marker is a per-call random nonce so
user text cannot forge the boundary. Concurrency defects found in adversarial
review (concurrent extract / diagram-blob clobber) are deferred to a separate
FD-264 child, not fixed here. Report:
`doc/induction-reports/2026-05-16_19-50-22--fd319-cursor-windowing/`.
