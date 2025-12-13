# Manual Prompt Optimization - Quick Start Guide

**Status**: CURRENT MVP APPROACH (as of 2025-12-07)

**Alternatives**:
- **[CLI Automation](PROMPT_INDUCTION_CLI.md)**: Automated iteration using Claude Code CLI ($0 cost, 10 min runtime)
- **[API Automation](PROMPT_INDUCTION_AUTOMATED.md)**: Full auto-trigger system with web UI ($50-100/mo)

---

## Quick Workflow

```bash
# 1. Export ground truth cases
uv run python -m btcopilot.training.export_gt

# 2. Open Claude Code and analyze (see below)

# 3. Test improved prompts
uv run python -m btcopilot.training.test_prompts

# 4. If improved, commit
git add btcopilot/personal/prompts.py
git commit -m "Improve extraction prompts (F1: X → Y)"
```

---

## Detailed Steps

### 1. Code Ground Truth Cases

Code GT in the training app (`/training/discussions`):
- Review AI extractions
- Correct errors in SARF editor
- Approve when correct

**Minimum**: 10-20 approved cases before optimizing prompts

### 2. Export GT Cases

```bash
cd /Users/patrick/theapp/btcopilot
uv run python -m btcopilot.training.export_gt
```

**Output**: `instance/gt_export.json`

**Format**:
```json
[
  {
    "statement_id": 123,
    "feedback_id": 45,
    "auditor_id": "expert@example.com",
    "statement_text": "User's message...",
    "speaker_name": "John",
    "discussion_context": "Full discussion history...",
    "ai_extraction": {
      "people": [...],
      "events": [...],
      "pair_bonds": [...],
      "delete": []
    },
    "gt_extraction": {
      // Corrected extraction
    },
    "comment": "Expert's feedback"
  }
]
```

### 3. Analyze with Claude Code

**Open Claude Code, paste this prompt**:

```
I have 20 ground truth cases for a family relationship extraction system. The AI extracts people, events, and clinical variables (symptom, anxiety, relationship, functioning) from user discussions.

Here's the GT export (AI extraction vs. ground truth):

[Paste contents of instance/gt_export.json]

Please analyze discrepancies between AI extractions and ground truth:

1. What patterns do you see in errors? (over-extraction, missed entities, SARF variable mismatches)
2. Which error types are most frequent?
3. What prompt improvements would address the top 2-3 error patterns?

Current prompts are in btcopilot/personal/prompts.py (I'll show you after your analysis).
```

**Claude Code will respond with error analysis**

**Then ask**:
```
Here are the current prompts:

[Paste contents of btcopilot/personal/prompts.py]

Based on your error analysis, propose specific improvements to:
- PDP_ROLE_AND_INSTRUCTIONS (extraction rules)
- PDP_EXAMPLES (example cases)

Focus on fixing the top 2 error patterns you identified.
```

**Claude Code will propose improved prompts**

### 4. Test Proposed Prompts

**Update `btcopilot/personal/prompts.py`** with Claude's suggestions

**Run test**:
```bash
uv run python -m btcopilot.training.test_prompts
```

**Output**:
```
Testing current prompts on 18 approved GT cases...

============================================================
OVERALL RESULTS (18 cases)
============================================================
Aggregate F1:     0.823
People F1:        0.891
Events F1:        0.776
Symptom F1:       0.682
Anxiety F1:       0.714
Relationship F1:  0.745
Functioning F1:   0.698
============================================================
```

**Compare to baseline** (run test before updating prompts to get baseline)

### 5. If F1 Improved, Commit

```bash
git add btcopilot/personal/prompts.py
git commit -m "Improve extraction prompts (F1: 0.78 → 0.82)

- Relationship F1: 0.72 → 0.81 (clarified triangle examples)
- Events F1: 0.75 → 0.83 (added timeframe requirements)

Analysis: AI was over-extracting general characterizations as events.
Fix: Added PDP_EXAMPLES showing WRONG vs. CORRECT event patterns."

git push
```

### 6. Deploy to Production

Follow your normal deployment process to get updated `prompts.py` to prod.

### 7. Repeat

As you code more GT cases:
1. Re-export: `uv run python -m btcopilot.training.export_gt`
2. Ask Claude Code to analyze new cases
3. Iterate on prompts
4. Test and commit improvements

---

## Tips for Claude Code Analysis

**Good prompts for Claude**:
- "What are the top 3 most frequent error types?"
- "Show me 2-3 specific examples of each error pattern"
- "Should I modify instructions, examples, or both?"
- "What's the smallest change that would fix the most errors?"

**Iterative refinement**:
- Start with 1-2 prompt changes at a time
- Test after each change
- If F1 drops, revert and try different approach
- Build on what works

**Focus areas**:
- **Over-extraction**: AI creates too many entities (tighten rules)
- **Under-extraction**: AI misses entities (add examples)
- **SARF mismatches**: Variables coded wrong (clarify definitions)
- **Relationship triangles**: Complex, often needs better examples

---

## Files

**Scripts**:
- `btcopilot/training/export_gt.py` - Export approved GT to JSON
- `btcopilot/training/test_prompts.py` - Compute F1 on GT

**Prompts** (what you edit):
- `btcopilot/personal/prompts.py` - Extraction prompts
  - `PDP_ROLE_AND_INSTRUCTIONS` - Rules for extraction
  - `PDP_EXAMPLES` - Example cases showing correct extraction

**GT Source**:
- Database: `feedbacks` table (`approved=True, feedback_type='extraction'`)
- Training app: `/training/discussions`

**Output**:
- `instance/gt_export.json` - Exported GT cases

---

## Cost Comparison

**Manual approach (current)**:
- $0/month (using $100/mo Claude Code subscription)
- Can use Opus 4.5 (best quality)
- 10-20 min per iteration
- Full control and insight

**Automated approach (future)**:
- $50-100/month (API costs)
- Less control
- Faster at scale
- See [PROMPT_INDUCTION_AUTOMATED.md](PROMPT_INDUCTION_AUTOMATED.md)

**Recommendation**: Stay manual until you've done 10+ successful iterations and the process feels repetitive. Then consider automation.

---

## Troubleshooting

**"No approved GT cases found"**:
- Code GT in training app first: `/training/discussions`
- Approve at least 10-20 cases before optimizing

**F1 scores don't improve**:
- May need schema changes, not just prompt changes
- Review specific errors with `--detailed` flag
- Ask Claude Code for deeper analysis of failure modes

**F1 scores get worse**:
- Revert prompt changes: `git checkout btcopilot/personal/prompts.py`
- Try smaller, more targeted changes
- Focus on one error type at a time

**Can't find export file**:
- Default location: `instance/gt_export.json`
- Specify custom path: `uv run python -m btcopilot.training.export_gt /path/to/output.json`

---

## Success Metrics

**MVP Success** (manual approach working):
- ✅ Can export GT cases without errors
- ✅ Claude Code provides useful error analysis
- ✅ Proposed prompt changes improve F1 by ≥5%
- ✅ Can iterate 3+ times with consistent improvements

**Ready for Automation** (consider building automated system):
- Have completed 10+ manual iterations
- F1 improvement plateauing (diminishing returns)
- GT dataset ≥50 cases
- Process feels repetitive and time-consuming
