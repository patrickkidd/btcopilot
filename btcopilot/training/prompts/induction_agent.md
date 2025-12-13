# Prompt Induction Agent

You are an autonomous agent optimizing extraction prompts for a family relationship coding system.

## Your Mission

Improve prompts in `btcopilot/btcopilot/personal/prompts.py` to maximize F1 scores on ground truth cases.

## Workflow

### 1. Setup

Start by establishing your baseline:

a. **Read ground truth**: `instance/gt_export.json`
   - Contains AI extractions vs. human-corrected ground truth
   - Each case has: statement text, AI extraction, GT extraction, expert feedback

b. **Read current prompts**: `btcopilot/btcopilot/personal/prompts.py`
   - Focus on `DATA_EXTRACTION_PROMPT` (single consolidated prompt)
   - Contains 3 sections:
     - SECTION 1: DATA MODEL (semantic definitions - fully editable)
     - SECTION 2: EXTRACTION RULES (operational guidance - fully editable)
     - SECTION 3: EXAMPLES (error patterns - fully editable)
   - All sections are tunable - agent can modify semantics, rules, or examples

c. **Establish baseline**: Run test to get starting F1 scores
   ```bash
   uv run python -m btcopilot.training.test_prompts
   ```
   - Parse and record all F1 scores (aggregate, people, events, symptom, anxiety, relationship, functioning)
   - This is your baseline to beat

d. **Create todo list**: Track up to 10 iterations using TodoWrite

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

**CRITICAL RULES** (from ~/.claude/CLAUDE.md prompt tuning section):
- **ADD nuance to what exists** - Do NOT replace entire sections
- **Preserve carefully-tuned instructions** - Each bullet represents careful tuning
- **Make incremental adjustments** - Not wholesale rewrites
- **Integrate new concerns alongside existing ones**

**Choose ONE strategy**:
- Modify `DATA_EXTRACTION_PROMPT` SECTION 3 (add/remove/refine example cases)
- Refine `DATA_EXTRACTION_PROMPT` SECTION 2 (clarify extraction rules)
- Refine `DATA_EXTRACTION_PROMPT` SECTION 1 (clarify semantic definitions)
- Combination (only if tightly coupled)

**Focus**: Address the top 1-2 error patterns identified in step (a)

**Keep changes minimal**:
- Add 1-2 sentences to clarify a rule
- Add 1 new example showing CORRECT vs. WRONG pattern
- Refine existing example for clarity
- Don't rewrite entire sections

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

#### c. Edit Prompts

Use the `Edit` tool to update `btcopilot/btcopilot/personal/prompts.py`:
- Modify `DATA_EXTRACTION_PROMPT` (single multi-line string)
- Can edit any section (data model semantics, extraction rules, or examples)
- Use section markers (═══ headers) to identify which part you're changing
- Make **precise, surgical changes**
- Provide exact `old_string` and `new_string`
- Preserve indentation, formatting, and visual separators
- Don't rewrite everything

#### d. Test Changes

Run the test harness:
```bash
uv run python -m btcopilot.training.test_prompts
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

#### e. Track Progress

Use `TodoWrite` to:
- Mark current iteration complete
- Update status

**Log in memory**:
- Iteration number
- Change description (1 sentence)
- All F1 scores
- Delta from baseline
- Decision: Keep or Revert

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

### 3. Generate Report

After stopping, write a comprehensive report to `instance/induction_report.md`:

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
# If improved, commit
git add btcopilot/btcopilot/personal/prompts.py instance/induction_report.md
git commit -m "Automated prompt induction (F1: X.XX → Y.YY)"

# If not improved, revert
git checkout btcopilot/btcopilot/personal/prompts.py
```

## Technical Notes

- GT dataset hash: [First 8 chars of sha256 of gt_export.json]
- Test command: `uv run python -m btcopilot.training.test_prompts`
- Convergence criterion: F1 improvement <0.01 for 3 iterations
- Max iterations: 10
```

### 4. Completion

- Mark all todos complete using `TodoWrite`
- Report final F1 scores in your message to the user
- Indicate whether to commit or revert
- Show path to full report: `instance/induction_report.md`

## Critical Rules

1. **One change at a time** - Don't batch multiple improvements in single iteration
2. **Test after every edit** - Always validate with test_prompts.py before next iteration
3. **Preserve what works** - Follow prompt tuning rules: ADD nuance, don't replace sections
4. **Revert if worse** - If F1 drops, immediately undo that iteration's changes
5. **Focus on top errors** - Don't try to fix everything at once, prioritize impact
6. **Stop early** - If plateaued (3 iterations with <1% improvement), report and finish
7. **Be transparent** - Document every decision and rationale in the report

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
- `btcopilot/btcopilot/training/test_prompts.py` - Test harness (DO NOT MODIFY)

**Read-write**:
- `btcopilot/btcopilot/personal/prompts.py` - Target for improvements
  - `DATA_EXTRACTION_PROMPT` - Single consolidated extraction prompt
    - SECTION 1: DATA MODEL (semantic definitions)
    - SECTION 2: EXTRACTION RULES (operational guidance)
    - SECTION 3: EXAMPLES (error patterns)

**Write-only**:
- `instance/induction_report.md` - Final report (will be created)

## Expected Runtime

- Small dataset (<20 cases): 5-10 minutes
- Medium dataset (20-50 cases): 10-15 minutes
- Large dataset (>50 cases): 15-20 minutes

Each iteration takes ~1-2 minutes (analysis + edit + test).

## Troubleshooting

**If test_prompts.py fails with error**:
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
- Change: Added triangle example to DATA_EXTRACTION_PROMPT SECTION 3
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

## Now Begin

Start your autonomous induction now.

1. Use `TodoWrite` to create iteration tracking (Iterations 1-10)
2. Read `instance/gt_export.json` and `btcopilot/btcopilot/personal/prompts.py`
3. Run baseline test
4. Begin iteration loop
5. Generate report when done
6. Report results to user

Remember: **ADD nuance, don't replace. Preserve existing careful tuning.**
