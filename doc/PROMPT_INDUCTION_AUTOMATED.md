# Automated Prompt Induction System - Future Roadmap

**Status**: NOT IMPLEMENTED - Future enhancement after manual MVP proves effective

**Current Approach**: Manual iteration with Claude Code (see `export_gt.py`, `test_prompts.py`)

**When to build this**: After 5-10 manual prompt improvement cycles demonstrate consistent F1 gains

---

## Goal

Fully automated system to optimize PDP extraction prompts via Claude API meta-prompting. GT coding triggers automatic prompt re-induction with real-time web UI visibility.

**Automated Workflow**: Code GT → Auto-detect F1 drop → Run induction → Review results in dashboard → Export/deploy

---

## Three-Phase Implementation Plan

### Phase 1: Core Induction Engine with Web UI (2-3 weeks)

**Deliverables**:
- Manual-trigger induction via web dashboard
- Real-time progress monitoring (Server-Sent Events)
- PromptVersion/InductionRun database tracking
- Export winning prompts to `prompts.py`

**Components**:

1. **`btcopilot/training/induction.py`** - Core engine
   - `split_gt_dataset(feedbacks)` → 80/20 train/val, stratified by entity counts, leave-one-out if <20
   - `analyze_validation_errors(results)` → Extract error patterns for Claude meta-prompting
   - `propose_prompt_variant(errors, history, llm)` → Claude analyzes and proposes improvements
   - `evaluate_prompt_variant(variant, val_set, llm)` → Re-extract and compute F1
   - `is_converged(history, threshold=0.01, patience=3)` → Detect F1 plateau
   - `run_induction(max_iterations=20)` → Main loop, yields progress via SSE
   - `export_production_prompts(version_id)` → Write to `prompts.py` with metadata

2. **`btcopilot/training/routes/induction.py`** - Web UI
   - `GET /training/induction` → Dashboard (run history, current status, trigger button)
   - `POST /training/induction/trigger` → Start new run, stream SSE progress
   - `GET /training/induction/run/<run_id>` → Run details (iteration chart, F1 breakdown)
   - `GET /training/induction/versions/<id>` → View prompt version
   - `POST /training/induction/export/<version_id>` → Export to `prompts.py`

3. **`btcopilot/training/templates/induction/`** - UI templates
   - `dashboard.html` → Run list, trigger button, latest F1 scores
   - `run_detail.html` → Single run view with iteration chart (Chart.js)
   - `version_detail.html` → Prompt viewer with diff from baseline

4. **Database Models** (`btcopilot/training/models.py`)
```python
class PromptVersion(db.Model, ModelMixin):
    version_hash = Column(String(64), unique=True)
    instructions = Column(Text, nullable=False)
    examples = Column(Text, nullable=False)

    # F1 Metrics
    validation_f1 = Column(Float)
    train_f1 = Column(Float)
    people_f1 = Column(Float)
    events_f1 = Column(Float)
    symptom_f1 = Column(Float)
    anxiety_f1 = Column(Float)
    relationship_f1 = Column(Float)
    functioning_f1 = Column(Float)

    # Metadata
    gt_dataset_hash = Column(String(64))
    gt_dataset_size = Column(Integer)
    induction_run_id = Column(String(64))
    parent_version_id = Column(Integer, ForeignKey("prompt_versions.id"))
    is_production = Column(Boolean, default=False)
    notes = Column(Text)

class InductionRun(db.Model, ModelMixin):
    run_id = Column(String(64), unique=True)
    trigger_type = Column(String(20))  # "manual" or "auto"
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    baseline_f1 = Column(Float)
    final_f1 = Column(Float)
    improvement = Column(Float)
    status = Column(String(20))  # "running", "completed", "failed"
```

**Success Criteria**:
- ✅ Manual trigger works from UI
- ✅ Real-time progress visible (SSE streaming)
- ✅ ≥1 iteration shows >1% F1 improvement on test dataset
- ✅ Export to `prompts.py` preserves functionality
- ✅ <30 min runtime for ~20 GT cases

### Phase 2: Auto-Trigger & F1 Monitoring (1-2 weeks)

**Prerequisite**: Phase 1 deployed and validated with 3+ successful manual runs

**Deliverables**:
- Celery task triggered after GT approval
- F1 threshold detection
- Exponential backoff to prevent infinite loops

**Components**:

1. **`btcopilot/training/induction_monitor.py`** - Celery tasks
```python
@celery.task
def check_f1_threshold():
    """Check if system F1 dropped below threshold, trigger re-induction."""
    metrics = calculate_system_f1()
    threshold = current_app.config.get("AUTO_INDUCTION_F1_THRESHOLD", 0.75)

    if metrics.aggregate_micro_f1 < threshold:
        if should_trigger_auto_induction():
            trigger_induction.delay()

@celery.task
def trigger_induction():
    """Run induction in background via Celery."""
    with app.app_context():
        run_induction(max_iterations=20)

def should_trigger_auto_induction() -> bool:
    """Backoff logic: check cooldown, prevent loops."""
    recent_runs = InductionRun.query.filter(
        InductionRun.trigger_type == "auto",
        InductionRun.started_at > datetime.now() - timedelta(days=7)
    ).order_by(InductionRun.started_at.desc()).all()

    # Cooldown check
    if recent_runs:
        hours_since_last = (datetime.now() - recent_runs[0].started_at).total_seconds() / 3600
        if hours_since_last < current_app.config["AUTO_INDUCTION_COOLDOWN_HOURS"]:
            return False

    # Prevent loops: if last 3 runs showed <0.5% improvement each, stop
    if len(recent_runs) >= 3:
        improvements = [r.improvement for r in recent_runs[:3]]
        if all(imp < 0.005 for imp in improvements):
            return False

    return True
```

2. **Hook into Feedback approval** (`btcopilot/training/routes/feedback.py`)
```python
@feedback_bp.route("/approve/<int:feedback_id>", methods=["POST"])
def approve_feedback(feedback_id):
    # ... existing approval logic ...

    from btcopilot.training.induction_monitor import check_f1_threshold
    check_f1_threshold.delay()

    return jsonify({"success": True})
```

3. **Config** (`.env` or `btcopilot/app.py`)
```python
AUTO_INDUCTION_F1_THRESHOLD = 0.75
AUTO_INDUCTION_MIN_GT_SIZE = 20
AUTO_INDUCTION_COOLDOWN_HOURS = 24
```

**Success Criteria**:
- ✅ Auto-trigger fires correctly after GT approval
- ✅ F1 threshold detection works
- ✅ Zero infinite loops (backoff prevents spam)
- ✅ Monthly API costs <$100

### Phase 3: Production Observability & Polish (1-2 weeks)

**Prerequisite**: Phase 2 running in production with ≥3 successful auto-runs

**Deliverables**:
- Email notifications after runs
- Prompt diff viewer
- Statistical significance tests
- Export/import functionality
- Admin controls (pause auto-trigger, reset backoff)

**Components**:

1. **Email Notifications** (`btcopilot/training/email_notifications.py`)
```python
def send_induction_report(run: InductionRun, winner: PromptVersion):
    """Email summary after run completion."""
    subject = f"Prompt Induction Complete: F1 {run.baseline_f1:.3f} → {run.final_f1:.3f}"
    body = f"""
    Induction run {run.run_id} completed.

    Baseline F1: {run.baseline_f1:.3f}
    Final F1: {run.final_f1:.3f}
    Improvement: +{run.improvement:.3f}

    Top improvements:
    - Relationship F1: {winner.relationship_f1:.3f}
    - Events F1: {winner.events_f1:.3f}

    View details: {url_for('induction.run_detail', run_id=run.run_id, _external=True)}
    """
    send_email(subject, body, recipients=["dev-team@example.com"])
```

2. **Prompt Diff Viewer** (UI enhancement)
   - Side-by-side comparison of prompt versions
   - Highlight changes (insertions/deletions)
   - Show which error patterns each change addressed

3. **Admin Controls** (`btcopilot/training/routes/induction.py`)
   - `POST /training/induction/pause` → Disable auto-trigger temporarily
   - `POST /training/induction/reset-backoff` → Reset exponential backoff
   - `GET /training/induction/config` → View current config (thresholds, cooldowns)

**Success Criteria**:
- ✅ Email notifications delivered within 1 min
- ✅ Diff viewer shows accurate changes
- ✅ Admin can pause/resume auto-trigger
- ✅ F1 improvement ≥5% over baseline (cumulative)

---

## Induction Algorithm

```
1. Load approved GT from Feedback table
2. Split: 80/20 train/val (stratified by entity count quartiles)
3. Baseline: Evaluate current prompts.py on validation set
4. Loop (max 20 iterations OR F1 plateau):
   a. Error analysis: Identify patterns (over-extraction, missed entities, SARF mismatches)
   b. Claude meta-prompt: Analyze errors, propose variant (instructions/examples/both)
   c. Evaluate variant on validation set
   d. Track best (highest val F1, tie-break on train F1, then simplicity)
   e. Check convergence: F1 improvement <0.01 for 3 consecutive iterations
5. Save winner to DB (is_production=True)
6. Display in UI with export button
```

**Claude Meta-Prompt Template**:
```
You are optimizing extraction prompts for a family relationship coding system.

Current Prompts:
- Instructions: {current_instructions}
- Examples: {current_examples}

Performance on Validation Set (N={val_size}):
- Aggregate F1: {baseline_f1:.3f}
- People F1: {people_f1:.3f}
- Events F1: {events_f1:.3f}
- Relationship F1: {relationship_f1:.3f}

Common Error Patterns:
{error_analysis}

Previous Iterations (avoid repeating):
{iteration_history}

Task: Propose ONE targeted change to improve F1. Choose ONE strategy:
A) Modify examples (add/remove/refine)
B) Refine instructions (clarify rules)
C) Both

Output JSON:
{
  "strategy": "A" | "B" | "C",
  "rationale": "Why this addresses the errors (2-3 sentences)",
  "instructions": "Full updated PDP_ROLE_AND_INSTRUCTIONS",
  "examples": "Full updated PDP_EXAMPLES"
}

Constraints:
- Preserve existing good behavior
- Keep instructions <3000 tokens
- Focus on TOP 2 error patterns
```

**Convergence**: Stop if F1 delta <1% for 3 iterations OR 20 iterations max

**Winner Selection**: Highest validation F1 → highest train F1 → fewest tokens

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | Dev DB only (same as main app) | Need FKs to GT, lightweight, simpler |
| Git | Manual export/commit (Phase 1), auto-export option (Phase 3) | Code review for prompts like code changes |
| Environment | Dev-only (Phase 1), prod optional (Phase 2-3) | Safety, no risk to prod extractions in MVP |
| Execution | Synchronous + SSE (Phase 1), Celery (Phase 2) | No complexity until auto-trigger needed |
| Train/Val Split | 80/20 random, stratified | Avoid temporal bias, balanced entities |
| Optimization Target | Instructions + Examples together | Tightly coupled, single optimization |
| Prompt Storage | DB + file fallback | DB for metadata, prompts.py for deployment |
| LLM | Configurable (gpt-4o-mini, Claude Haiku/Sonnet) | Use existing btcopilot.llm client |

---

## Deployment Architecture

### Phase 1 (Dev-Only)
```
Development:
  - Induction runs here (manual trigger from UI)
  - PromptVersion/InductionRun tables
  - Export to prompts.py, commit to git
  - Deploy to prod

Production:
  - Uses prompts.py from git (no induction system)
```

### Phase 2-3 (Prod Integration)
```
Development:
  - Test new prompt versions before deploying

Production:
  - Induction can run here (auto-triggered by GT approval)
  - PromptVersion tables track history
  - Auto-export option OR manual review/commit
```

---

## API Costs

**Phase 1 (Manual Trigger)**:
- Per run: $10-40 (gpt-4o-mini: $2-5, Claude Sonnet: $10-40)
- Monthly: $20-200 (2-5 manual runs)

**Phase 2-3 (Auto-Trigger)**:
- Monthly: $50-300 (5-10 auto-runs + manual experiments)

**Cost Optimization**:
- Use gpt-4o-mini for meta-prompting (cheaper, "good enough")
- LLM call caching (don't re-extract unchanged statements)
- Reduce max iterations (10 instead of 20 for quick wins)
- Use Haiku if Claude API required

---

## Success Metrics

**Phase 1**:
- Manual runs complete without errors
- ≥1 iteration shows >1% F1 improvement
- Export works, deployed prompts improve production F1
- <30 min runtime for ~20 GT cases

**Phase 2**:
- Auto-trigger fires correctly after GT approval
- F1 monitoring works
- Zero infinite loops
- Monthly costs <$100

**Phase 3**:
- Email notifications working
- F1 improvement ≥5% over original baseline (cumulative)
- System stable in production for 1 month

---

## Migration from Manual MVP

When transitioning from manual Claude Code approach to automated system:

1. **Port manual insights**: Review git history of prompt changes, identify successful patterns
2. **Seed PromptVersion**: Create baseline version from current `prompts.py`
3. **Validate on existing GT**: Run Phase 1 system on full GT dataset, verify F1 matches manual results
4. **Gradual rollout**: Use Phase 1 manually for 2-3 runs before enabling Phase 2 auto-trigger
5. **Monitor costs**: Track actual API usage vs. projections, adjust max iterations if needed

---

## Critical Files

**Core Logic**:
- `btcopilot/training/induction.py` - Main engine
- `btcopilot/training/induction_monitor.py` - Auto-trigger (Phase 2)
- `btcopilot/training/routes/induction.py` - Web UI
- `btcopilot/training/models.py` - PromptVersion, InductionRun

**Dependencies**:
- `btcopilot/training/f1_metrics.py` - Reuse `calculate_statement_f1()`
- `btcopilot/personal/prompts.py` - Current prompts, export target
- `btcopilot/pdp.py` - Extraction engine
- `btcopilot/schema.py` - PDPDeltas schema
- `btcopilot/training/analysis_utils.py` - Error analysis patterns

**UI**:
- `btcopilot/training/templates/induction/dashboard.html`
- `btcopilot/training/templates/induction/run_detail.html`
- `btcopilot/training/templates/induction/version_detail.html`

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Small GT dataset (<20) prevents improvement | Use leave-one-out CV; prioritize GT collection |
| LLM proposes invalid JSON | Validation + retry (max 3 attempts) |
| F1 doesn't improve after 20 iterations | Manual error analysis; may need schema changes not prompt fixes |
| API costs exceed budget | Cap iterations; cache calls; use cheaper model |
| Overfitting to validation set | Track train F1; prefer simpler prompts |
| Infinite auto-trigger loops | Exponential backoff + max 3 consecutive runs |
| Prompt regression in production | Phase 1 manual review before deploy; A/B testing |

---

## Future Enhancements (Post-Phase 3)

- **A/B testing**: Deploy two prompt versions, compare F1 on live traffic
- **Active learning**: Prioritize which cases to code next based on current model weaknesses
- **Ensemble prompts**: Use multiple prompt variants, vote on extractions
- **Cross-validation**: K-fold instead of single train/val split
- **Bootstrap confidence intervals**: Statistical significance for F1 improvements
- **Prompt evolution tree**: Visualize lineage of prompt changes over time
- **Integration with fdserver**: Share prompt improvements across btcopilot instances
