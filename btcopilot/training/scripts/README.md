# Training Scripts

Automation tools for prompt optimization and testing.

## Quick Start: Automated Prompt Induction

Run autonomous prompt optimization in one command:

```bash
bash btcopilot/btcopilot/training/scripts/run_induction.sh
```

**What it does**:
1. Exports ground truth cases from database
2. Creates git checkpoint (safe to revert)
3. Runs Claude Code agent to:
   - Analyze error patterns
   - Propose improvements iteratively
   - Test each change
   - Generate detailed report
4. Shows results and next steps

**Runtime**: 5-15 minutes depending on GT dataset size

**Output**:
- `instance/induction_report.md` - Detailed analysis and results
- Modified `btcopilot/btcopilot/personal/prompts.py` - Improved prompts (if successful)

## How It Works

The script uses a meta-prompt (`../prompts/induction_agent.md`) that instructs Claude Code to:

1. **Analyze** error patterns in ground truth cases
2. **Propose** targeted prompt improvements (one at a time)
3. **Test** each change by running `test_prompts.py`
4. **Iterate** until F1 converges or max iterations reached
5. **Report** findings and recommendations

The agent uses Claude Code's tools autonomously:
- `Read` - Load GT export and current prompts
- `Edit` - Make surgical changes to prompts
- `Bash` - Run tests to validate
- `TodoWrite` - Track iteration progress
- `Write` - Generate report

## Prerequisites

1. **Ground truth cases**: Code at least 10-20 cases in training app first
   - Navigate to: http://127.0.0.1:5555/training/discussions
   - Review AI extractions and correct errors
   - Approve corrected cases

2. **Claude Code CLI**: Must be installed and in PATH
   - Check: `which claude`
   - Install if needed: [Claude Code installation docs]

3. **Clean working directory**: Uncommitted changes will be stashed

## Example Output

```
🚀 Starting Automated Prompt Induction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Step 1/4: Exporting ground truth...
✅ Exported 23 GT cases

💾 Step 2/4: Creating checkpoint...
✅ Checkpoint: a1b2c3d

🤖 Step 3/4: Running Claude Code induction agent...
This will take 5-15 minutes depending on dataset size

[Claude Code runs autonomously...]

✅ Induction complete!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Results Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Aggregate F1 | 0.823 | 0.873 | +0.050 |

✅ Changes made to prompts.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Generated Files:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Full report: instance/induction_report.md
  • Changes: git diff btcopilot/btcopilot/personal/prompts.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Next Steps:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Review the report:
   cat instance/induction_report.md

2. Review the changes:
   git diff btcopilot/btcopilot/personal/prompts.py

3a. If improved, commit:
    git add btcopilot/btcopilot/personal/prompts.py instance/induction_report.md
    git commit -m "Automated prompt induction (F1: 0.82 → 0.87)"

3b. If not improved, revert:
    git checkout btcopilot/btcopilot/personal/prompts.py
```

## When to Use

**Use CLI automation when**:
- Manual copy-paste feels repetitive (after 3-5 manual iterations)
- Want consistent methodology across runs
- Want documented decision trail
- Don't need auto-trigger or web dashboard yet

**Still use manual when**:
- First 1-3 iterations (learning what works)
- Exploring major changes to prompt structure
- Very small GT datasets (<10 cases)

**Consider API automation when**:
- Running >10x per month
- Want auto-trigger after GT approval
- Want web dashboard for team visibility
- Have budget for API costs ($50-100/mo)

## Troubleshooting

**"GT export failed"**:
- Code ground truth cases in training app first
- Check database connection
- Verify approved cases exist: `SELECT COUNT(*) FROM feedbacks WHERE approved=true`

**"No report generated"**:
- Check Claude Code output for errors
- Verify `instance/gt_export.json` is valid JSON
- Try with smaller GT subset first

**"F1 not improving"**:
- May need schema changes, not just prompt changes
- Review error patterns manually
- Consider collecting more diverse GT cases

**"Script syntax error"**:
- Ensure bash is available: `which bash`
- Check file permissions: `ls -la run_induction.sh`

## Related Documentation

- **[CLI Automation Details](../../../doc/PROMPT_INDUCTION_CLI.md)**: Full design doc
- **[Manual Approach](../../../doc/PROMPT_OPTIMIZATION_MANUAL.md)**: Current MVP process
- **[API Automation](../../../doc/PROMPT_INDUCTION_AUTOMATED.md)**: Future full automation
- **[F1 Metrics](../../../doc/F1_METRICS.md)**: Understanding evaluation metrics

## Cost Comparison

| Approach | Time | Cost | When to Use |
|----------|------|------|-------------|
| **Manual** | 20 min | $0 | Learning (first 1-3 times) |
| **CLI** | 10 min | $0 | Regular use (after manual phase) |
| **API** | 5 min | $50-100/mo | High frequency + auto-trigger |

**Recommendation**: Start with CLI automation after manual proves the concept.
