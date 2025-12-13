# CLI-Driven Automated Prompt Induction

**Status**: PROPOSED - Third option between manual and API-automated approaches

**Bridges**: Manual approach (PROMPT_OPTIMIZATION_MANUAL.md) + API automation (PROMPT_INDUCTION_AUTOMATED.md)

**When to use**: After 3-5 manual iterations when the process feels repetitive, but before justifying full API infrastructure

---

## Quick Start

```bash
# 1. Export ground truth
uv run python -m btcopilot.training.export_gt

# 2. Run automated induction (Claude Code does everything)
claude --prompt-file btcopilot/training/prompts/induction_agent.md

# 3. Review results
cat instance/induction_report.md

# 4. If improved, commit
git add btcopilot/personal/prompts.py instance/induction_report.md
git commit -m "Automated prompt induction (F1: 0.78 → 0.82)"
```

---

## Core Concept

**Leverage Claude Code's agentic capabilities via CLI invocation** instead of:
- Manual copy-paste (current manual approach)
- API calls + web infrastructure (future automated approach)

### How It Works

1. **Meta-prompt file** (`btcopilot/training/prompts/induction_agent.md`) instructs Claude Code to:
   - Read GT export (`instance/gt_export.json`)
   - Analyze error patterns autonomously using its tools
   - Propose prompt improvements
   - Edit `prompts.py` directly
   - Run `test_prompts.py` to validate
   - Iterate until F1 converges or max iterations reached
   - Generate report with findings

2. **CLI invocation** runs Claude Code in autonomous mode:
   ```bash
   claude --prompt-file btcopilot/training/prompts/induction_agent.md
   ```

3. **Claude Code uses its tools** (no API needed):
   - `Read` - Load GT export and current prompts
   - `Grep`/`Glob` - Search codebase for context
   - `Edit` - Modify prompts.py iteratively
   - `Bash` - Run test_prompts.py after each change
   - `TodoWrite` - Track iteration progress
   - `Write` - Generate final report

4. **Zero API costs** - Uses Claude Code subscription ($100/mo already paid), can use Opus 4.5 for best quality

---

## Benefits Matrix

| Feature | Manual | CLI Agent (This) | API Automated |
|---------|--------|------------------|---------------|
| **Cost** | $0 | $0 | $50-100/mo |
| **Time per run** | 10-20 min | 5-15 min | 2-5 min |
| **Human effort** | High (copy-paste) | Low (review only) | Minimal |
| **Infrastructure** | None | Shell script | DB + UI + Celery |
| **Model quality** | Opus 4.5 | Opus 4.5 | Haiku/GPT-4o-mini |
| **Transparency** | Full | Full (report + git diff) | Dashboard UI |
| **Control** | Full | High (approve before commit) | Lower |
| **Auto-trigger** | No | No (but easily scripted) | Yes |
| **Iteration** | Manual | Autonomous | Autonomous |

**Sweet spot**: Automation without infrastructure or API costs

---

## Implementation

### Phase 1: Core Agent (1-2 days)

**File: `btcopilot/training/prompts/induction_agent.md`**

```markdown
# Prompt Induction Agent

You are an autonomous agent optimizing extraction prompts for a family relationship coding system.

## Your Mission

Improve prompts in `btcopilot/personal/prompts.py` to maximize F1 scores on ground truth cases.

## Workflow

1. **Setup**
   - Read ground truth: `instance/gt_export.json`
   - Read current prompts: `btcopilot/personal/prompts.py`
   - Establish baseline: `uv run python -m btcopilot.training.test_prompts`
   - Create todo list with max 10 iterations

2. **Iteration Loop** (max 10 iterations or until convergence)

   For each iteration:

   a. **Analyze Errors**
      - Compare AI extractions vs. GT in `gt_export.json`
      - Identify top 2-3 error patterns:
        - Over-extraction (too many entities)
        - Under-extraction (missed entities)
        - SARF mismatches (wrong variable coding)
        - Relationship triangles (complex, often wrong)
      - Use `Grep` to find similar patterns in codebase if needed

   b. **Propose ONE Targeted Change**
      - Modify `DATA_EXTRACTION_PROMPT` (single consolidated prompt):
        - SECTION 1: DATA MODEL (semantic definitions)
        - SECTION 2: EXTRACTION RULES (operational guidance)
        - SECTION 3: EXAMPLES (error patterns)
        - Or combination of sections (if tightly coupled)
      - Focus on fixing top 1-2 error patterns
      - Keep changes minimal (avoid over-engineering)
      - Follow prompt tuning rules from ~/.claude/CLAUDE.md:
        * ADD nuance, don't replace entire sections
        * Preserve existing carefully-tuned instructions
        * Make incremental adjustments

   c. **Edit Prompts**
      - Use `Edit` tool to update `btcopilot/personal/prompts.py`
      - Make precise changes (don't rewrite everything)

   d. **Test Changes**
      - Run: `uv run python -m btcopilot.training.test_prompts`
      - Parse F1 scores from output
      - Compare to baseline and previous iteration

   e. **Track Progress**
      - Update todo list (mark iteration complete)
      - Log results in memory:
        - Iteration number
        - Change description
        - F1 scores (aggregate, per-type)
        - Improvement vs. baseline

   f. **Check Convergence**
      - If F1 improvement < 0.01 for 3 consecutive iterations → STOP
      - If F1 decreased → REVERT edit and try different approach
      - If max iterations reached → STOP

3. **Generate Report**

   Write `instance/induction_report.md`:

   ```markdown
   # Prompt Induction Report

   **Date**: YYYY-MM-DD HH:MM
   **GT Cases**: N cases
   **Iterations**: N
   **Runtime**: N minutes

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

   1. [Error pattern 1]: [Description] → [Fix applied]
   2. [Error pattern 2]: [Description] → [Fix applied]
   3. [Error pattern 3]: [Description] → [Fix applied]

   ## Iteration History

   ### Iteration 1
   - **Change**: [Description]
   - **F1**: 0.XXX (Δ +0.XXX)
   - **Outcome**: [Kept/Reverted]

   ### Iteration 2
   - **Change**: [Description]
   - **F1**: 0.XXX (Δ +0.XXX)
   - **Outcome**: [Kept/Reverted]

   [...]

   ## Recommendations

   - [If F1 improved ≥5%]: Commit changes to production
   - [If F1 plateaued]: May need schema changes, not just prompt changes
   - [If specific error persists]: Consider adding more GT cases for that pattern

   ## Next Steps

   ```bash
   # If improved, commit
   git add btcopilot/personal/prompts.py instance/induction_report.md
   git commit -m "Automated prompt induction (F1: X.XX → Y.YY)"

   # If not improved, revert
   git checkout btcopilot/personal/prompts.py
   ```
   ```

4. **Completion**
   - Mark all todos complete
   - Report final F1 scores
   - Indicate whether to commit or revert

## Critical Rules

1. **One change at a time** - Don't batch multiple improvements
2. **Test after every edit** - Always validate with test_prompts.py
3. **Preserve what works** - Follow prompt tuning rules (ADD nuance, don't replace)
4. **Revert if worse** - If F1 drops, undo that iteration
5. **Focus on top errors** - Don't try to fix everything at once
6. **Stop early** - If plateaued, report and finish
7. **Be transparent** - Document every decision in the report

## Success Criteria

- ✅ Baseline F1 captured correctly
- ✅ At least 3 iterations attempted (unless early convergence)
- ✅ F1 improvement ≥1% OR clear convergence detected
- ✅ Report generated with all required sections
- ✅ Git diff shows precise, targeted changes
- ✅ No test failures or errors during iterations

## Files You'll Work With

**Read-only**:
- `instance/gt_export.json` - Ground truth cases
- `btcopilot/training/test_prompts.py` - Test harness

**Read-write**:
- `btcopilot/personal/prompts.py` - Target for improvements
  - `DATA_EXTRACTION_PROMPT` - Single consolidated extraction prompt
    - SECTION 1: DATA MODEL (semantic definitions)
    - SECTION 2: EXTRACTION RULES (operational guidance)
    - SECTION 3: EXAMPLES (error patterns)

**Write-only**:
- `instance/induction_report.md` - Final report

## Expected Runtime

- Small dataset (<20 cases): 5-10 minutes
- Medium dataset (20-50 cases): 10-15 minutes
- Large dataset (>50 cases): 15-20 minutes

## Troubleshooting

**If test_prompts.py fails**:
- Check syntax errors in prompts.py
- Revert last edit and try again

**If F1 not improving after 5 iterations**:
- Review error patterns more carefully
- Consider smaller, more focused changes
- May need schema changes (report this)

**If Claude Code loses context**:
- Key state is in git diff and induction_report.md
- Re-read baseline scores from report
- Continue from last successful iteration

---

Begin autonomous induction now. Use TodoWrite to track iterations.
```

**Wrapper Script: `btcopilot/training/scripts/run_induction.sh`**

```bash
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/../../.."  # Project root

echo "🚀 Starting automated prompt induction..."
echo ""

# 1. Export GT
echo "📊 Exporting ground truth..."
uv run python -m btcopilot.training.export_gt
if [ ! -f "instance/gt_export.json" ]; then
    echo "❌ GT export failed"
    exit 1
fi

GT_COUNT=$(jq length instance/gt_export.json)
echo "✅ Exported $GT_COUNT GT cases"
echo ""

# 2. Create checkpoint
echo "💾 Creating checkpoint..."
git add btcopilot/personal/prompts.py 2>/dev/null || true
git stash push -m "Pre-induction checkpoint" btcopilot/personal/prompts.py 2>/dev/null || echo "No changes to stash"
CHECKPOINT_SHA=$(git rev-parse HEAD)
echo "✅ Checkpoint: $CHECKPOINT_SHA"
echo ""

# 3. Run Claude Code agent
echo "🤖 Running Claude Code induction agent..."
echo ""
claude --prompt-file btcopilot/training/prompts/induction_agent.md

# 4. Check results
if [ ! -f "instance/induction_report.md" ]; then
    echo ""
    echo "❌ No report generated - something went wrong"
    exit 1
fi

echo ""
echo "✅ Induction complete!"
echo ""
echo "📊 Results:"
grep "| Aggregate F1" instance/induction_report.md || true
echo ""
echo "📄 Full report: instance/induction_report.md"
echo "📝 Changes: git diff btcopilot/personal/prompts.py"
echo ""
echo "Next steps:"
echo "  - Review report and git diff"
echo "  - If improved: git add btcopilot/personal/prompts.py instance/induction_report.md && git commit"
echo "  - If not improved: git checkout btcopilot/personal/prompts.py"
```

**Make executable**:
```bash
chmod +x btcopilot/training/scripts/run_induction.sh
```

---

### Phase 2: Enhancements (1-2 days)

**Optional improvements after Phase 1 proves effective**:

1. **Parallel Experimentation**
   ```bash
   # Run N variants in parallel git worktrees
   btcopilot/training/scripts/parallel_induction.sh --variants 3 --max-iterations 5
   ```
   - Creates 3 git worktrees
   - Runs Claude Code agent in each with different strategies
   - Compares results
   - Merges best variant

2. **Scheduled Runs**
   ```bash
   # Add to crontab
   0 2 * * * cd /path/to/theapp && btcopilot/training/scripts/run_induction.sh
   ```
   - Runs nightly when new GT cases are coded
   - Emails report to developer
   - Auto-commits if improvement ≥5%

3. **Interactive Mode**
   ```bash
   claude --prompt-file btcopilot/training/prompts/induction_agent_interactive.md
   ```
   - Agent asks for human approval before each edit
   - Useful for learning what works
   - Hybrid manual/automated approach

4. **Multi-Stage Induction**
   ```bash
   # Stage 1: Fix over-extraction (stricter rules)
   claude --prompt-file btcopilot/training/prompts/stage1_reduce_overextraction.md

   # Stage 2: Fix under-extraction (more examples)
   claude --prompt-file btcopilot/training/prompts/stage2_add_coverage.md

   # Stage 3: Refine SARF coding (variable-specific)
   claude --prompt-file btcopilot/training/prompts/stage3_sarf_precision.md
   ```

---

## Cost Comparison

| Approach | Monthly Cost | Time per Run | Infrastructure | Model |
|----------|--------------|--------------|----------------|-------|
| **Manual** | $0 | 20 min | None | Opus 4.5 |
| **CLI Agent** | $0 | 10 min | Shell script | Opus 4.5 |
| **API Automated** | $50-100 | 5 min | DB + UI + Celery | Haiku/GPT-4o-mini |

**CLI Agent wins on**:
- Cost (same as manual, $0)
- Quality (Opus 4.5 like manual)
- Speed (2x faster than manual)
- Simplicity (no infrastructure like manual)

**API Automated still better for**:
- Auto-triggering (fires on GT approval)
- Web dashboard visibility
- Hands-off operation at scale

---

## Migration Path

1. **Week 1**: Build Phase 1 (core agent + wrapper script)
2. **Week 2**: Run 3-5 times manually to validate
3. **Week 3**: Add scheduled runs (cron)
4. **Week 4**: Build parallel experimentation
5. **Month 2+**: Decide if worth building full API automation

**Decision point**: If running >10x/month and wanting auto-trigger, consider API approach. Otherwise, CLI agent is sufficient.

---

## Comparison to Other Approaches

### vs. Manual (Current MVP)

**Advantages**:
- ✅ Eliminates copy-paste tedium
- ✅ Autonomous iteration (no human in loop)
- ✅ Consistent methodology (agent follows same process)
- ✅ Documented decisions (report file)

**Disadvantages**:
- ❌ Slightly less control (agent decides next step)
- ❌ Requires trust in agent's judgment

### vs. API Automated (Future)

**Advantages**:
- ✅ Zero API costs
- ✅ Best model (Opus 4.5)
- ✅ No infrastructure (DB, UI, Celery)
- ✅ Simpler to build and maintain
- ✅ Full transparency (git diff + report)

**Disadvantages**:
- ❌ No auto-trigger (must run manually or via cron)
- ❌ No web dashboard
- ❌ Slightly slower (10 min vs. 5 min)

---

## Success Metrics

**Phase 1 MVP Success**:
- ✅ Agent completes 3+ iterations without errors
- ✅ F1 improves by ≥1% on test set
- ✅ Report accurately reflects changes
- ✅ Git diff shows targeted, sensible edits
- ✅ <15 min runtime for ~20 GT cases

**Ready for Production**:
- Have run 5+ times with consistent improvements
- Average F1 gain ≥3% per run
- No manual intervention needed
- Trust agent's decisions

**Consider API Approach Instead**:
- Running >10x per month
- Want auto-trigger on GT approval
- Want web dashboard for team visibility
- Budget for API costs ($50-100/mo)

---

## Files

**New Files** (to create):
- `btcopilot/training/prompts/induction_agent.md` - Meta-prompt for Claude Code
- `btcopilot/training/scripts/run_induction.sh` - Wrapper script
- `instance/induction_report.md` - Generated report (gitignored)

**Existing Files** (used):
- `btcopilot/training/export_gt.py` - GT export (unchanged)
- `btcopilot/training/test_prompts.py` - Test harness (unchanged)
- `btcopilot/personal/prompts.py` - Target for edits
- `instance/gt_export.json` - GT data (gitignored)

**Optional** (Phase 2):
- `btcopilot/training/scripts/parallel_induction.sh`
- `btcopilot/training/prompts/induction_agent_interactive.md`
- `btcopilot/training/prompts/stage1_reduce_overextraction.md`
- `btcopilot/training/prompts/stage2_add_coverage.md`
- `btcopilot/training/prompts/stage3_sarf_precision.md`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Agent makes bad edits | Git checkpoint before run, easy to revert |
| Agent gets stuck in loop | Max iterations = 10, convergence detection |
| F1 doesn't improve | Report explains why, manual analysis may be needed |
| Context loss during run | Key state in report + git, can resume |
| Agent breaks prompts.py | Test after each edit, revert if tests fail |
| Too slow with large GT | Start with subset, optimize prompt for speed |

---

## Troubleshooting

**"Claude Code not found"**:
- Install: [Claude Code installation instructions]
- Ensure `claude` in PATH

**"Induction report not generated"**:
- Check Claude Code output for errors
- Agent may have hit context limit (reduce GT size)
- Try with `--model opus` flag

**"F1 scores not improving"**:
- Review error patterns manually
- May need schema changes, not prompt changes
- Try interactive mode to guide agent

**"Agent making too many changes"**:
- Adjust meta-prompt to emphasize "ONE change at a time"
- Reduce max iterations

**"Git conflicts"**:
- Ensure clean working directory before run
- Use checkpoint mechanism in wrapper script

---

## Example Run

```bash
$ btcopilot/training/scripts/run_induction.sh

🚀 Starting automated prompt induction...

📊 Exporting ground truth...
✅ Exported 23 GT cases

💾 Creating checkpoint...
✅ Checkpoint: a1b2c3d

🤖 Running Claude Code induction agent...

[Claude Code output:]
I'll optimize extraction prompts for 23 GT cases. Using TodoWrite to track iterations.

Iteration 1/10: Analyzing errors...
- Over-extraction in Events: AI creates events for general characterizations
- Top error: "always been close" extracted as event (should be relationship pattern)

Editing prompts.py to clarify event definition...
Testing... F1: 0.823 → 0.847 (+0.024) ✅

Iteration 2/10: Analyzing remaining errors...
- Relationship triangles: Missing 3rd person in triangle coding
- Example: "Mom and Dad fight about me" only codes Mom↔Dad, misses child

Adding triangle example to DATA_EXTRACTION_PROMPT SECTION 3...
Testing... F1: 0.847 → 0.869 (+0.022) ✅

Iteration 3/10: Analyzing remaining errors...
- Symptom confidence: Over-confident on vague statements

Refining confidence scoring rules...
Testing... F1: 0.869 → 0.873 (+0.004) ✅

Iteration 4/10: Convergence check...
- F1 improvement <0.01 for 3 iterations
- Stopping early (convergence reached)

Generating report...
✅ Report written to instance/induction_report.md

✅ Induction complete!

📊 Results:
| Aggregate F1 | 0.823 | 0.873 | +0.050 |

📄 Full report: instance/induction_report.md
📝 Changes: git diff btcopilot/personal/prompts.py

Next steps:
  - Review report and git diff
  - If improved: git add btcopilot/personal/prompts.py instance/induction_report.md && git commit
  - If not improved: git checkout btcopilot/personal/prompts.py

$ git diff btcopilot/personal/prompts.py
[Shows precise, targeted changes to event definition and triangle examples]

$ git add btcopilot/personal/prompts.py instance/induction_report.md
$ git commit -m "Automated prompt induction (F1: 0.823 → 0.873)

- Events F1: 0.776 → 0.841 (clarified event vs. pattern distinction)
- Relationship F1: 0.745 → 0.798 (added triangle example)
- Symptom F1: 0.682 → 0.701 (refined confidence scoring)

Autonomous induction agent (4 iterations, 12 min runtime)"
```

---

## Next Steps

1. **Build Phase 1** (1-2 days)
   - Create `induction_agent.md` meta-prompt
   - Create `run_induction.sh` wrapper script
   - Test on current GT dataset

2. **Validate** (1 week)
   - Run 3-5 times manually
   - Compare results to manual iterations
   - Refine meta-prompt based on learnings

3. **Productionize** (optional)
   - Add scheduled runs (cron)
   - Build parallel experimentation
   - Consider interactive mode for exploration

4. **Decide** (after 1 month)
   - If working well and sufficient: keep CLI approach
   - If need auto-trigger + dashboard: build API automation
   - If not effective: investigate schema changes vs. prompt changes

---

## Summary

**CLI Agent = Automated Manual Approach**

- Same zero cost as manual
- Same model quality (Opus 4.5)
- Eliminates tedium via automation
- No infrastructure needed
- Bridges gap until API automation is justified

**Use this when**:
- Manual approach is repetitive
- Not ready to build API infrastructure
- Want to stay within Claude Code subscription
- Prefer simplicity and transparency

**Don't use this when**:
- Manual approach is working fine (don't over-engineer)
- Need auto-trigger on GT approval (use API approach)
- Want web dashboard for team (use API approach)
- Have budget for API and prefer hands-off operation
