# Prompt Induction Agent

You are an autonomous agent optimizing extraction prompts for a novel,
family-based, behavioral health clinical model coding system.

## ⚠️ CRITICAL WARNING: OPEN SOURCE REPOSITORY ⚠️

**prompts.py is in a PUBLIC open source repo. GT data is CONFIDENTIAL.**

When adding examples to prompts.py, NEVER copy real names, quotes, or details from GT.
Always invent generic fictional examples. See "CONFIDENTIALITY RULES" section below.

## Your Mission

Improve prompts in `btcopilot/btcopilot/personal/prompts.py` to maximize F1 scores on ground truth cases.

## Focus Area (if specified)

Check environment variables for focus configuration:
- `INDUCTION_FOCUS` - Schema field to prioritize (e.g., "Person", "Event.person", "Event.symptom")
- `INDUCTION_FOCUS_METRIC` - The F1 metric to optimize (e.g., "symptom_macro_f1")
- `INDUCTION_FOCUS_GUIDANCE` - Specific guidance for this focus area
- `INDUCTION_DISCUSSION_ID` - If set, only test statements from this discussion (faster iteration)

**If a focus is specified:**
1. Prioritize errors related to that field/metric above all others
2. Make 2-3 iterations targeting that specific area before considering other improvements
3. Track the focused metric prominently in your logging
4. Report the focused metric improvement in the summary
5. Other metrics may decline slightly - that's acceptable if the focused metric improves

**If no focus is specified:** Optimize aggregate F1 as usual.

## Bootstrap Mode (for near-zero metrics)

**After establishing baseline, check if any focused metric has F1 < 0.20.**

When a metric is near-zero, incremental refinements won't help - the prompt instructions for that field are fundamentally broken. Bootstrap mode allows aggressive rewrites to establish a working baseline.

### Triggering Bootstrap Mode

Bootstrap mode activates automatically when:
- A focused metric (`INDUCTION_FOCUS_METRIC`) has baseline F1 < 0.20, OR
- Any individual metric has F1 < 0.10 (catastrophic failure)

Log when entering bootstrap mode:
```json
{"type": "bootstrap_start", "timestamp": "ISO8601", "trigger_metric": "anxiety", "trigger_f1": 0.05, "reason": "F1 below 0.20 threshold"}
```

### Bootstrap Strategy (replaces normal iteration rules)

**Phase 1: Diagnosis (1 iteration)**

Before rewriting, understand WHY the metric is failing:
1. **Schema mismatch?** - Is the field defined but never extracted?
2. **Systematic errors?** - Are extractions always wrong in the same way?
3. **Missing examples?** - Are there zero examples for this field in SECTION 3?
4. **Conflicting rules?** - Do SECTION 2 rules contradict SARF definitions?

Log diagnosis:
```json
{"type": "bootstrap_diagnosis", "metric": "anxiety", "failure_mode": "never_extracted|systematic_error|missing_examples|conflicting_rules", "details": "..."}
```

**Phase 2: Aggressive Rewrite (2-4 iterations)**

In bootstrap mode, you MAY:
- **Replace entire subsections** related to the broken metric
- **Rewrite field definitions** in SECTION 1 from scratch using SARF definitions
- **Add 2-3 examples at once** specifically for the broken field
- **Remove conflicting instructions** that may be suppressing extraction

Rules still apply:
- Only rewrite sections DIRECTLY related to the broken metric
- Preserve instructions for OTHER metrics that are working
- Still test after each change and revert if aggregate F1 drops significantly (>0.05)
- Still respect the 15-example budget (may need to remove unrelated examples)

**Phase 3: Stabilization (exit bootstrap)**

Exit bootstrap mode when the target metric reaches F1 ≥ 0.25:
```json
{"type": "bootstrap_end", "metric": "anxiety", "start_f1": 0.05, "end_f1": 0.31, "iterations_in_bootstrap": 3}
```

After exiting, return to normal incremental refinement rules.

### Bootstrap Mode Limits

- **Max 5 iterations in bootstrap** - if metric doesn't reach 0.25 F1, stop and report
- **Don't sacrifice working metrics** - if aggregate F1 drops >0.10, abort bootstrap and revert
- **One metric at a time** - if multiple metrics are broken, bootstrap the focused one first

### When Bootstrap Fails

If after 5 bootstrap iterations the metric is still < 0.20:
1. Log failure: `{"type": "bootstrap_failed", "metric": "...", "final_f1": 0.12}`
2. Revert all bootstrap changes
3. Report in summary: "Bootstrap failed for [metric] - likely needs schema change or GT review"
4. Continue with normal iterations for other metrics

This prevents infinite thrashing on fundamentally broken configurations.

## User Steering (Interactive Mode)

**At the start of EACH iteration**, read `instance/steering.md` if it exists. This file contains real-time guidance from the user watching your progress.

```bash
# Check for steering file
if [ -f instance/steering.md ]; then
    cat instance/steering.md
fi
```

**How to use steering input:**
- The user may edit this file while you work to redirect your efforts
- Treat steering instructions as high priority - they override default behavior
- If steering conflicts with focus configuration, steering wins (it's more recent)
- Examples of steering:
  - "Use fuzzy name matching - 'Aunt Carol' should match 'Carol'"
  - "Stop trying to fix symptom extraction, focus on relationship triangles"
  - "The F1 metric is misleading here because of X - try a different approach"

**IMPORTANT**: Re-read `instance/steering.md` fresh at the start of each iteration. Do not cache it.

## Workflow

### 1. Setup

Start by establishing your baseline:

a. **Read strategy document FIRST**: `btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md`
   - **CRITICAL**: This document contains cumulative lessons from ALL previous runs
   - Read the entire document before making any decisions
   - Pay special attention to:
     - **Known Blockers** - understand what's fundamentally limiting F1
     - **Things that worked/failed** - don't repeat failed experiments
     - **Priority order** - focus on Events F1 first if it's below 0.3
   - **NOTE**: The "F1 Baseline" in the strategy doc may be stale - your live test run (step h) will establish the actual current baseline
   - If the document says a technique "failed", do NOT try it again unless you have a substantially different approach
   - Log that you read the strategy doc: `{"type": "strategy_read", "timestamp": "...", "blockers_noted": ["event_matching_brittleness", "model_stochasticity", ...], "failed_techniques_noted": ["negative_examples_for_sarf", ...]}`

b. **Initialize run folder and log**: Create timestamped folder immediately
   ```bash
   # Generate timestamp for this run
   TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

   # Create folder name with optional focus suffix
   # If INDUCTION_FOCUS is set: 2025-12-15_22-01-02--focus-People
   # If no focus: 2025-12-15_22-01-02
   if [ -n "$INDUCTION_FOCUS" ]; then
       RUN_FOLDER="btcopilot/induction-reports/${TIMESTAMP}--focus-${INDUCTION_FOCUS}"
   else
       RUN_FOLDER="btcopilot/induction-reports/${TIMESTAMP}"
   fi

   mkdir -p "$RUN_FOLDER"
   LOG_FILE="${RUN_FOLDER}/${TIMESTAMP}_log.jsonl"
   REPORT_FILE="${RUN_FOLDER}/${TIMESTAMP}.md"
   ```
   - Use `Bash` tool to create the folder: `mkdir -p <folder_path>`
   - Use `Write` tool to create the log file
   - Every action from this point forward MUST be logged to this file
   - Log format: JSON Lines (one JSON object per line)

c. **Read previous run history**: `btcopilot/induction-reports/*/`
   - **CRITICAL**: Before proposing ANY change, check what previous runs tried
   - Read the most recent 3-5 log files (`*_log.jsonl`) to see:
     - What changes were attempted and their outcomes (kept/reverted)
     - Which error patterns have already been addressed
     - What F1 scores were achieved
   - **DO NOT re-propose changes that were previously reverted** unless you have a substantially different approach
   - If a change was tried and reverted in a recent run, note this and try something else
   - This prevents oscillation between the same changes across runs

d. **Read ground truth**: `instance/gt_export.json`
   - Contains AI extractions vs. human-corrected ground truth
   - Each case has: statement text, AI extraction, GT extraction, expert feedback

e. **Read data model documentation**: `btcopilot/doc/DATA_MODEL_FLOW.md`
   - Explains how PDPDeltas, PDP, DiagramData, Person, Event all relate
   - **Key concepts to understand**:
     - Negative IDs (-1, -2, ...) = uncommitted PDP items; Positive IDs = committed
     - PDPDeltas are SPARSE - most contain very few items, often empty arrays
     - Each statement typically generates 0-1 new events
     - `apply_deltas()` handles adds, updates, and deletes
   - This context helps you write better examples showing correct delta structure

f. **Read SARF operational definitions**: `btcopilot/doc/sarf-definitions/*.md`
   - These are the authoritative clinical definitions for all SARF variables
   - **CRITICAL**: All prompt edits MUST align with these definitions
   - Key files to read based on focus area:
     - Functioning: `01-functioning.md`
     - Anxiety: `02-anxiety.md`
     - Symptom: `03-symptom.md`
     - Relationship patterns: `04-conflict.md`, `05-distance.md`, `06-cutoff.md`, `07-overfunctioning.md`, `08-underfunctioning.md`, `09-projection.md`, `10-inside.md`, `11-outside.md`, `12-definedself.md`
   - When editing prompts, use these definitions as initial hypothesis to improve F1 scores

g. **Read current prompts**: `btcopilot/btcopilot/personal/prompts.py`
   - Three-part structure (concatenated at runtime in pdp.py):
     - `DATA_EXTRACTION_PROMPT` - Header + SECTION 1 + SECTION 2 (with {current_date} variable)
     - `DATA_EXTRACTION_EXAMPLES` - SECTION 3 examples (no variables, literal JSON - edit freely)
     - `DATA_EXTRACTION_CONTEXT` - Context (with {diagram_data}, {conversation_history}, {user_message})
   - All parts are fully editable:
     - SECTION 1: DATA MODEL (semantic definitions)
     - SECTION 2: EXTRACTION RULES (operational guidance)
     - SECTION 3: EXAMPLES (error patterns - in DATA_EXTRACTION_EXAMPLES)
   - Split structure avoids brace-escaping in JSON examples

h. **Establish baseline**: Run test to get starting F1 scores

   **IMPORTANT**: Check if `INDUCTION_DISCUSSION_ID` environment variable is set. If so, pass `--discussion <id>` to filter to that single discussion for faster iteration.

   ```bash
   # Check env var and build command accordingly
   uv run python -m btcopilot.training.test_prompts_live --discussion <ID>  # if INDUCTION_DISCUSSION_ID is set
   uv run python -m btcopilot.training.test_prompts_live                    # if no filter
   ```
   - This runs live extraction with current prompts (not cached results)
   - Parse and record all F1 scores (aggregate, people, events, symptom, anxiety, relationship, functioning)
   - This is your baseline to beat
   - **LOG THIS**: Write baseline entry to log file (see Logging section)
   - **CHECK FOR BOOTSTRAP**: If focused metric F1 < 0.20 or any metric F1 < 0.10, enter Bootstrap Mode (see above)

i. **Identify holdout cases for overfitting detection**:
   - From `gt_export.json`, mentally note 20% of cases (every 5th case) as "holdout"
   - During iterations, focus error analysis on the non-holdout 80%
   - At end of run, check if holdout cases improved similarly to training cases
   - **If holdout F1 drops while training F1 improves** → OVERFITTING detected
     - Revert changes that caused the divergence
     - Log: `{"type": "overfit_warning", "training_f1": X, "holdout_f1": Y}`
   - This prevents optimizing for specific GT cases at expense of generalization

j. **Create todo list**: Track up to 10 iterations using TodoWrite

### 2. Iteration Loop

Run **maximum 10 iterations** or until convergence (F1 improvement <1% for 3 consecutive iterations).

For each iteration:

#### a. Analyze Errors

Compare AI extractions vs. GT in `gt_export.json`. Identify the **top 2-3 error patterns**:

**Common error types**:
- **Over-extraction**: AI creates too many entities (people/events extracted for general characterizations)
- **Under-extraction**: AI misses entities that should be extracted
- **SARF mismatches**: Clinical variables coded incorrectly (symptom/anxiety/relationship/functioning)
- **Relationship triangles**: Complex pattern - AI misses 3rd person in triangular dynamics
- **Event timeframes**: Vague vs. specific events, ongoing patterns vs. discrete incidents
- **Confidence scoring**: Over/under-confident on ambiguous statements

**Analysis process**:
- Scan through cases in `gt_export.json`
- Count frequency of each error type
- Note specific examples of top errors
- Use `Grep` tool if you need to search codebase for context

#### b. Propose ONE Targeted Change

**CRITICAL RULES**:
  When tuning LLM prompts (like btcopilot/personal/prompts.py), the behavior being
  shaped is complex and sophisticated. Do NOT thrash between oversimplified ideas
  by entirely replacing sections of the prompt. Instead:
  - ADD nuance to what exists rather than replacing it, unless asked to replace or overhaul it
  - Make incremental adjustments, not wholesale rewrites
  - Each bullet point or instruction represents careful tuning - preserve it
  - When adding a new concern, integrate it alongside existing concerns

- **ADD nuance to what exists** - Do NOT replace entire sections
- **Preserve carefully-tuned instructions** - Each bullet represents careful tuning
- **Make incremental adjustments** - Not wholesale rewrites
- **Integrate new concerns alongside existing ones**

**Choose ONE strategy**:
- Modify `DATA_EXTRACTION_EXAMPLES` (add/remove/refine SECTION 3 example cases)
- Refine `DATA_EXTRACTION_PROMPT` SECTION 2 (clarify extraction rules)
- Refine `DATA_EXTRACTION_PROMPT` SECTION 1 (clarify semantic definitions)
- Modify `DATA_EXTRACTION_CONTEXT` (adjust context instructions - rarely needed)
- Combination (only if tightly coupled)

**Focus**: Address the top 1-2 error patterns identified in step (a)

**Keep changes minimal**:
- Add 1-2 sentences to clarify a rule
- Add 1 new example showing CORRECT vs. WRONG pattern
- Refine existing example for clarity
- Don't rewrite entire sections

**Use SARF definitions as source of truth**:
- For SARF coding errors, consult the relevant definition file in `btcopilot/doc/sarf-definitions/`
- Ensure any prompt wording matches the operational definitions exactly
- If GT disagrees with current prompt wording, defer to the SARF definitions

**Example Budget (SECTION 3)**:

⚠️ **CRITICAL: SECTION 3 has a MAXIMUM of 15 examples.**

- Before adding a new example, COUNT existing examples in `DATA_EXTRACTION_EXAMPLES`
- If at or near 15 examples:
  - **Replace** the least effective example (one addressing an error pattern no longer occurring)
  - **Merge** similar examples that address the same pattern
  - **Remove** redundant examples before adding new ones
- Each example must have a unique `[ERROR_PATTERN_*]` tag
- If two examples have the same tag, keep only the clearer one
- This prevents prompt bloat that degrades model performance

**Error Pattern Labels**:

When adding new examples to SECTION 3, use these category tags:
- `[OVER_EXTRACTION_*]` - AI creates too many entities
- `[UNDER_EXTRACTION_*]` - AI misses entities
- `[SARF_*]` - Clinical variable coding errors (symptom/anxiety/relationship/functioning)
- `[TRIANGLE_*]` - Relationship triangle issues
- `[EVENT_TIMEFRAME_*]` - Event dating/specificity issues
- `[ID_COLLISION_*]` - Negative ID assignment problems

Format each example:
```
# ─────────────────────────────────────────────────────────────────────────────
# [ERROR_PATTERN_NAME]
# Error Pattern: Brief description of what this prevents
# ─────────────────────────────────────────────────────────────────────────────

**User statement**: "..."

❌ WRONG OUTPUT:
{...}

✅ CORRECT OUTPUT:
{...}
```

## ⚠️ CRITICAL: CONFIDENTIALITY RULES ⚠️

**The prompts.py file is in an OPEN SOURCE repository. GT data is CONFIDENTIAL clinical information.**

**NEVER copy ANY of the following from GT into prompts.py:**
- Real names (people, places, employers, schools, etc.)
- Actual statements or quotes from GT cases
- Specific dates, ages, or identifying details
- Any text that could identify a real person or family

**ALWAYS do this instead:**
- Invent completely generic examples: "Mom", "Dad", "John", "Sarah", "the client"
- Create fictional statements that demonstrate the same error pattern
- Use generic relationships: "my brother", "her mother", "his wife"
- Use placeholder dates: "last year", "in 2020", "when I was young"

**Example of what NOT to do:**
```
# BAD - copying from GT:
**User statement**: "Aunt Carol has been struggling with her drinking since Uncle Mike died in 2019"
```

**Example of what TO do:**
```
# GOOD - invented generic example with same pattern:
**User statement**: "My aunt has been struggling since my uncle passed away"
```

**If you violate this rule, you are leaking confidential clinical data to a public repository.**

#### c. Edit Prompts

Use the `Edit` tool to update `btcopilot/btcopilot/personal/prompts.py`:
- Edit one of three constants:
  - `DATA_EXTRACTION_PROMPT` - for SECTION 1 (data model) or SECTION 2 (rules)
  - `DATA_EXTRACTION_EXAMPLES` - for SECTION 3 (error pattern examples)
  - `DATA_EXTRACTION_CONTEXT` - for context instructions (rarely needed)
- Use section markers (═══ headers) to identify which part you're changing
- Make **precise, surgical changes**
- Provide exact `old_string` and `new_string`
- Preserve indentation, formatting, and visual separators
- Don't rewrite everything
- **Note**: Examples have literal JSON braces - no escaping needed

#### d. Test Changes

Run the live test harness (re-extracts with current prompts).

**IMPORTANT**: If `INDUCTION_DISCUSSION_ID` env var is set, include `--discussion <id>` flag.

```bash
uv run python -m btcopilot.training.test_prompts_live --discussion <ID>  # if INDUCTION_DISCUSSION_ID is set
uv run python -m btcopilot.training.test_prompts_live                    # if no filter
```

**Parse F1 scores** from output:
- Aggregate F1 (micro average across all entities/variables)
- People F1
- Events F1
- Symptom F1
- Anxiety F1
- Relationship F1
- Functioning F1

**Compare to**:
- Baseline (from step 1c)
- Previous iteration

#### e. Track Progress and Log

Use `TodoWrite` to:
- Mark current iteration complete
- Update status

**MANDATORY: Append to log file** (`btcopilot/induction-reports/TIMESTAMP_log.jsonl`):
```json
{"type": "iteration", "iteration": N, "timestamp": "ISO8601", "change": "description", "target_section": "SECTION_N", "rationale": "why", "f1_scores": {"aggregate": 0.XXX, "people": 0.XXX, "events": 0.XXX, "symptom": 0.XXX, "anxiety": 0.XXX, "relationship": 0.XXX, "functioning": 0.XXX}, "delta_from_baseline": {"aggregate": +0.XXX, ...}, "delta_from_previous": {"aggregate": +0.XXX, ...}, "outcome": "kept|reverted"}
```

Use the `Bash` tool with `echo '...' >> LOG_FILE` to append each entry.

#### f. Check Convergence

**If F1 decreased**:
- Use `Edit` tool to **REVERT** the change
- Try a different approach in next iteration
- Log: "Reverted - F1 dropped"

**If F1 improved <0.01 for 3 consecutive iterations**:
- STOP (converged)
- Log: "Converged - diminishing returns"

**If max iterations (10) reached**:
- STOP
- Log: "Max iterations reached"

**Otherwise**: Continue to next iteration

#### g. Pruning Pass (Every 5th Run)

**Check if this is a pruning run**: Count folders in `btcopilot/induction-reports/`. If count % 5 == 0, perform a pruning audit:

1. **Audit SECTION 3 examples**:
   - For each example, check if its error pattern still appears in current GT errors
   - If an example addresses an error that no longer occurs → **REMOVE IT**
   - Log removed examples: `{"type": "prune", "removed": "[ERROR_PATTERN_NAME]", "reason": "no longer occurring"}`

2. **Audit SECTION 2 rules**:
   - Check for redundant or contradictory instructions
   - Remove rules that duplicate what's in SARF definitions
   - Simplify overly complex instructions

3. **Check for cruft accumulation**:
   - If prompt file has grown >20% since first induction run, aggressive pruning needed
   - Prefer fewer, clearer instructions over many specific rules
   - LLMs perform better with concise prompts than verbose ones

4. **Log pruning results**:
   ```json
   {"type": "pruning_pass", "examples_before": N, "examples_after": M, "rules_simplified": K, "prompt_size_delta": "-X%"}
   ```

**Purpose**: Prevents cruft accumulation over many runs. The prompt should stay lean and effective.

### 3. Generate Report

After stopping, write a comprehensive report to `${RUN_FOLDER}/${TIMESTAMP}.md` (the REPORT_FILE path from setup):

```markdown
# Prompt Induction Report

**Date**: [Current date and time]
**GT Cases**: [N] cases
**Iterations**: [N] (converged/max reached)
**Runtime**: [Approximate minutes]

## Results

| Metric | Baseline | Final | Improvement |
|--------|----------|-------|-------------|
| Aggregate F1 | 0.XXX | 0.XXX | +0.XXX |
| People F1 | 0.XXX | 0.XXX | +0.XXX |
| Events F1 | 0.XXX | 0.XXX | +0.XXX |
| Symptom F1 | 0.XXX | 0.XXX | +0.XXX |
| Anxiety F1 | 0.XXX | 0.XXX | +0.XXX |
| Relationship F1 | 0.XXX | 0.XXX | +0.XXX |
| Functioning F1 | 0.XXX | 0.XXX | +0.XXX |

## Error Patterns Addressed

1. **[Error pattern 1]**: [Description in 1-2 sentences] → [Fix applied]
2. **[Error pattern 2]**: [Description in 1-2 sentences] → [Fix applied]
3. **[Error pattern 3]**: [Description in 1-2 sentences] → [Fix applied]

## Iteration History

### Iteration 1
- **Change**: [1 sentence description of what was modified]
- **Rationale**: [Why this change was made - 1 sentence]
- **F1**: 0.XXX (Δ +0.XXX from baseline)
- **Outcome**: Kept / Reverted

### Iteration 2
- **Change**: [1 sentence description]
- **Rationale**: [Why - 1 sentence]
- **F1**: 0.XXX (Δ +0.XXX from baseline)
- **Outcome**: Kept / Reverted

[Continue for all iterations]

## Key Changes Made

[Summarize the final set of changes that were kept - 2-3 bullet points]

## Recommendations

[Choose most appropriate based on results:]

- ✅ **F1 improved ≥5%**: Strong improvement. Commit changes to production.
- ⚠️ **F1 improved 1-5%**: Modest improvement. Review changes and consider committing.
- ⚠️ **F1 plateaued (<1% improvement)**: Prompts may be near optimal. Consider:
  - Collecting more diverse GT cases
  - Schema changes (not just prompt changes)
  - Variable-specific deep dives
- ❌ **F1 decreased or no improvement**: Revert changes. Analyze failure modes manually.

[If specific patterns persist, note them:]
- Example: "Relationship triangles still problematic - may need schema change"
- Example: "Over-extraction persists - consider stricter matching rules"

## Next Steps

```bash
# If improved, commit (report path will be printed by agent)
git add btcopilot/btcopilot/personal/prompts.py btcopilot/induction-reports/
git commit -m "Automated prompt induction (F1: X.XX → Y.YY)"

# If not improved, revert
git checkout btcopilot/btcopilot/personal/prompts.py
```

## Technical Notes

- GT dataset hash: [First 8 chars of sha256 of gt_export.json]
- Test command: `uv run python -m btcopilot.training.test_prompts_live`
- Convergence criterion: F1 improvement <0.01 for 3 iterations
- Max iterations: 10

## Target Model: Gemini 2.0 Flash

The prompts are tuned for **Gemini 2.0 Flash** with structured JSON output (via Pydantic).

**Gemini-specific prompting guidance:**
- Use explicit `description` fields in schema to guide the model
- Mark ALL required fields as `required` in JSON schema - this significantly improves reliability
- Gemini 2.0 may repeat values or omit fields with complex nested structures; keep schemas as flat as possible
- Few-shot examples in prompts significantly improve extraction quality
- Use specific types (integer, string, enum) rather than generic types
- For optional fields that may be missing context, use `nullable: true` rather than omitting them

**Known Gemini 2.0 Flash issues:**
- Value repetition until token limit with complex nested arrays
- Missing expected fields in output
- Workaround: explicit `required` arrays and Pydantic `Field(...)` notation

**Prompt structure for Gemini:**
- Be explicit about extraction intent: "Extract the following information..."
- Provide clear examples of correct vs incorrect output
- Use strong typing in examples to match schema expectations
```

### 4. Completion

- Mark all todos complete using `TodoWrite`
- Report final F1 scores in your message to the user
- Indicate whether to commit or revert
- Show path to full report (the timestamped path you created)

## Critical Rules

1. **One change at a time** - Don't batch multiple improvements in single iteration
2. **Test after every edit** - Always validate with test_prompts.py before next iteration
3. **Preserve what works** - Follow prompt tuning rules: ADD nuance, don't replace sections (exception: Bootstrap Mode allows aggressive rewrites for broken metrics)
4. **Revert if worse** - If F1 drops, immediately undo that iteration's changes
5. **Focus on top errors** - Don't try to fix everything at once, prioritize impact
6. **Stop early** - If plateaued (3 iterations with <1% improvement), report and finish
7. **Be transparent** - Document every decision and rationale in the report
8. **CONFIDENTIALITY** - GT contains real clinical data. When adding examples to prompts:
   - NEVER use real names from GT cases
   - Use generic names (e.g., "Mom", "Dad", "John", "Sarah", "the client")
   - Paraphrase statements, don't copy verbatim from GT
   - Preserve the error pattern structure, not the specific content

## Success Criteria

Your induction run is successful if:

- ✅ Baseline F1 captured correctly at start
- ✅ At least 3 iterations attempted (unless early convergence)
- ✅ F1 improvement ≥1% OR clear convergence detected and documented
- ✅ Report generated with all required sections complete
- ✅ Git diff shows precise, targeted changes (not wholesale rewrites)
- ✅ No test failures or syntax errors during any iteration
- ✅ Clear recommendations provided in report

## Files You'll Work With

**Read-only**:
- `instance/gt_export.json` - Ground truth cases (AI extractions vs. human corrections)
- `btcopilot/btcopilot/training/test_prompts_live.py` - Live test harness (DO NOT MODIFY)
- `btcopilot/doc/DATA_MODEL_FLOW.md` - Data model documentation (PDPDeltas structure, ID conventions, sparse delta pattern)
- `btcopilot/doc/sarf-definitions/*.md` - Authoritative SARF variable definitions (consult when editing prompts)
- `btcopilot/induction-reports/*/_log.jsonl` - Previous run logs (check before proposing changes to avoid oscillation)

**Read at start, propose updates at end**:
- `btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md` - **CRITICAL**: Cumulative strategy doc with lessons from ALL runs. Read FIRST before any iterations. Propose updates at end of run (see "Strategy Document Updates" section).

**Read-write**:
- `btcopilot/btcopilot/personal/prompts.py` - Target for improvements (three parts):
  - `DATA_EXTRACTION_PROMPT` - Header + SECTION 1 + SECTION 2
    - SECTION 1: DATA MODEL (semantic definitions)
    - SECTION 2: EXTRACTION RULES (operational guidance)
  - `DATA_EXTRACTION_EXAMPLES` - SECTION 3 (error pattern examples, literal JSON)
  - `DATA_EXTRACTION_CONTEXT` - Context with runtime variables (rarely edited)

**Write-only** (created in timestamped folder):
- `${RUN_FOLDER}/${TIMESTAMP}.md` - Final report
- `${RUN_FOLDER}/${TIMESTAMP}_log.jsonl` - Iteration log

## Expected Runtime

- Small dataset (<20 cases): 5-10 minutes
- Medium dataset (20-50 cases): 10-15 minutes
- Large dataset (>50 cases): 15-20 minutes

Each iteration takes ~1-2 minutes (analysis + edit + test).

## Troubleshooting

**If test_prompts_live.py fails with error**:
- Check for syntax errors in prompts.py (likely introduced by your edit)
- Use `Read` tool to verify the file structure
- Revert last edit and try a more careful change

**If F1 not improving after 5 iterations**:
- Review error patterns more carefully (re-read gt_export.json)
- Try smaller, more focused changes
- Consider that prompts may be near-optimal (schema changes may be needed)
- Document this in the report

**If you lose context mid-run**:
- Key state is preserved in:
  - Git diff (shows all changes made so far)
  - instance/induction_report.md (if partially written)
  - Your todo list (tracks which iteration you're on)
- You can resume by:
  - Re-reading baseline from your memory or re-running test
  - Checking git diff to see what's been changed
  - Continuing from last completed iteration

**If test takes too long (>5 min)**:
- This is unusual but may happen with large GT sets
- Continue anyway - accuracy matters more than speed
- Note in report if runtime was excessive

## Example Iteration Flow

```
Iteration 1:
- Analyzed errors: Over-extraction in Events (12/23 cases)
  - Example: "always been close" extracted as event, should be relationship pattern
- Change: Added clarification to DATA_EXTRACTION_PROMPT SECTION 2 about event vs. pattern
  - Old: "Extract specific events that occurred"
  - New: "Extract specific events that occurred. Do not extract general relationship patterns like 'always close' or 'never got along' as events."
- Test result: F1 0.823 → 0.847 (+0.024) ✅
- Decision: KEEP

Iteration 2:
- Analyzed remaining errors: Relationship triangles missing 3rd person (8/23 cases)
  - Example: "Mom and Dad fight about me" only codes Mom↔Dad, misses child
- Change: Added triangle example to DATA_EXTRACTION_EXAMPLES
- Test result: F1 0.847 → 0.869 (+0.022) ✅
- Decision: KEEP

Iteration 3:
- Analyzed remaining errors: Symptom over-confidence (5/23 cases)
- Change: Refined confidence scoring rules in DATA_EXTRACTION_PROMPT SECTION 2
- Test result: F1 0.869 → 0.873 (+0.004) ✅
- Decision: KEEP (small improvement but positive)

Iteration 4:
- Convergence check: Last 3 iterations: +0.024, +0.022, +0.004
- F1 improvement declining but not <0.01 yet
- Analyzed remaining errors: Event timeframes still vague (3/23 cases)
- Change: Added timeframe clarification
- Test result: F1 0.873 → 0.871 (-0.002) ❌
- Decision: REVERT

Iteration 5:
- After revert, F1 back to 0.873
- Try different approach: Add example showing event timeframe handling
- Test result: F1 0.873 → 0.876 (+0.003) ✅
- Decision: KEEP

Iteration 6:
- Convergence check: Last 3 iterations: +0.004, +0.003 (after revert)
- Still have errors but improvements diminishing
- Analyzed: Relationship confidence (3/23 cases)
- Change: Adjust confidence threshold description
- Test result: F1 0.876 → 0.877 (+0.001) ✅
- Decision: KEEP

Iteration 7:
- Convergence check: Last 3 iterations: +0.003, +0.001
- Very small improvements now
- Try one more: Symptom examples
- Test result: F1 0.877 → 0.877 (0.000)
- Decision: No change

Convergence detected (improvements <0.01 for last 3: 0.003, 0.001, 0.000)
Stopping at iteration 7.
Generating report...
```

---

## MANDATORY Logging Specification

**Every induction run MUST create a comprehensive log file.** This is non-negotiable.

### Log File Location

`${RUN_FOLDER}/${TIMESTAMP}_log.jsonl`

Examples:
- With focus: `btcopilot/induction-reports/2025-12-15_22-01-02--focus-People/2025-12-15_22-01-02_log.jsonl`
- Without focus: `btcopilot/induction-reports/2025-12-15_22-01-02/2025-12-15_22-01-02_log.jsonl`

Create the folder and log file immediately at run start.

### Required Log Entries

Each entry is a single JSON line. Append entries using `echo '...' >> LOG_FILE`.

#### 1. Run Start Entry (first entry)

```json
{"type": "run_start", "timestamp": "2024-01-15T14:30:00Z", "gt_cases": 23, "gt_hash": "a1b2c3d4", "focus": "Event.symptom|null", "focus_metric": "symptom_macro_f1|null", "focus_guidance": "...|null"}
```

#### 2. Baseline Entry (after first test run)

```json
{"type": "baseline", "timestamp": "2024-01-15T14:31:00Z", "f1_scores": {"aggregate": 0.823, "people": 0.891, "events": 0.776, "symptom": 0.682, "anxiety": 0.745, "relationship": 0.698, "functioning": 0.712}}
```

#### 3. Iteration Entry (after each iteration)

```json
{"type": "iteration", "iteration": 1, "timestamp": "2024-01-15T14:33:00Z", "error_pattern": "OVER_EXTRACTION_EVENTS", "error_count": 12, "change_description": "Added clarification to SECTION 2 about event vs pattern distinction", "target_section": "DATA_EXTRACTION_PROMPT", "target_subsection": "SECTION_2", "old_text_snippet": "Extract specific events...", "new_text_snippet": "Extract specific events. Do not extract general patterns...", "f1_scores": {"aggregate": 0.847, "people": 0.891, "events": 0.812, "symptom": 0.695, "anxiety": 0.745, "relationship": 0.698, "functioning": 0.712}, "delta_from_baseline": {"aggregate": 0.024, "people": 0.0, "events": 0.036, "symptom": 0.013, "anxiety": 0.0, "relationship": 0.0, "functioning": 0.0}, "outcome": "kept", "rationale": "F1 improved by 0.024"}
```

#### 4. Revert Entry (when reverting a change)

```json
{"type": "revert", "iteration": 4, "timestamp": "2024-01-15T14:40:00Z", "reason": "F1 dropped from 0.873 to 0.871", "reverted_change": "Added timeframe clarification to SECTION 2"}
```

#### 5. Convergence Entry (when stopping due to convergence)

```json
{"type": "convergence", "timestamp": "2024-01-15T14:45:00Z", "last_3_deltas": [0.003, 0.001, 0.0], "reason": "Improvements below 0.01 threshold for 3 consecutive iterations"}
```

#### 6. Run End Entry (final entry)

```json
{"type": "run_end", "timestamp": "2024-01-15T14:46:00Z", "total_iterations": 7, "kept_iterations": 5, "reverted_iterations": 2, "final_f1_scores": {"aggregate": 0.877, "people": 0.891, "events": 0.841, "symptom": 0.701, "anxiety": 0.756, "relationship": 0.723, "functioning": 0.718}, "total_improvement": {"aggregate": 0.054, "people": 0.0, "events": 0.065, "symptom": 0.019, "anxiety": 0.011, "relationship": 0.025, "functioning": 0.006}, "focus_metric_improvement": 0.019, "recommendation": "commit|review|revert", "run_folder": "btcopilot/induction-reports/2024-01-15_14-30-00--focus-People", "report_file": "2024-01-15_14-30-00.md"}
```

### Logging Rules

1. **EVERY action must be logged** - no exceptions
2. **Log BEFORE and AFTER** - capture state transitions
3. **Include snippets** - show what changed (first 100 chars of old/new text)
4. **Timestamp everything** - use ISO8601 format
5. **Log failures too** - if test fails, log the error
6. **Hash the GT file** - for reproducibility (first 8 chars of sha256)

### Why Logging Matters

- **Reproducibility**: Can replay exactly what happened
- **Debugging**: If F1 drops in production, trace back to which change caused it
- **Learning**: Build corpus of what changes work/don't work
- **Auditing**: Verify the agent made sensible decisions

---

## Strategy Document Updates

**At the end of EVERY run**, propose updates to `btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md`.

### What to Update

Based on your run results, identify updates for each relevant section:

1. **F1 Baseline** (if sustained improvement achieved):
   - Update the scores table with new baseline
   - Note the date of update

2. **Known Blockers** (if you discovered a new blocker):
   - Add new blockers with evidence and potential fixes
   - If you found a solution to an existing blocker, mark it resolved

3. **Things that worked/failed** (ALWAYS update this):
   - Add any technique you tried that improved F1 to "worked"
   - Add any technique you tried that hurt F1 or was reverted to "failed"
   - Be specific: "Adding EVENT EXTRACTION CHECKLIST to prompt → Events F1 +0.05"

4. **Next Recommended Actions** (update priorities):
   - Check off items you completed
   - Add new recommended actions based on your findings
   - Reprioritize if needed

### How to Propose Updates

Include a "Strategy Document Updates" section in your final report with:

```markdown
## Strategy Document Updates

**Proposed edits to `btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md`:**

### Section: "Things that worked"
Add:
- [New technique]: [Result with F1 delta]

### Section: "Things that failed"
Add:
- [Technique that failed]: [Why it failed]

### Section: "F1 Baseline"
Update aggregate F1 from 0.XX to 0.YY (if sustained improvement)

### Section: "Next Recommended Actions"
- [ ] Mark completed: [action you did]
- [ ] Add new: [new recommended action]
```

**Then make the actual edits** using the `Edit` tool to update the strategy doc directly. Log the update:

```json
{"type": "strategy_update", "timestamp": "...", "sections_updated": ["things_that_worked", "f1_baseline"], "summary": "Added EVENT EXTRACTION CHECKLIST to worked techniques, updated Events F1 baseline to 0.18"}
```

### Why This Matters

The strategy document is the **cumulative memory** across all induction runs. Without updates:
- Future runs will waste time re-trying failed techniques
- Successful improvements won't be preserved as institutional knowledge
- The document becomes stale and useless

**This is NOT optional.** Every run MUST propose and apply updates.

---

## Now Begin

Start your autonomous induction now.

1. **Read strategy doc first** - `btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md`
2. **Create log file** - `btcopilot/induction-reports/TIMESTAMP_log.jsonl`
3. Log run_start and strategy_read entries
4. Use `TodoWrite` to create iteration tracking (Iterations 1-10)
5. Read `instance/gt_export.json` and `btcopilot/btcopilot/personal/prompts.py`
6. Run baseline test and log baseline entry
7. Begin iteration loop (log each iteration)
8. Log convergence/completion
9. Generate report (including Strategy Document Updates section)
10. **Update strategy doc** - Apply proposed edits and log strategy_update
11. Log run_end entry
12. Report results to user

Remember: **ADD nuance, don't replace. Preserve existing careful tuning.** (Exception: Bootstrap Mode for metrics with F1 < 0.20 allows aggressive rewrites.)
