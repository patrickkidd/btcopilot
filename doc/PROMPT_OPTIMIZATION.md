# Prompt Optimization Process

**Status**: CURRENT — Interactive Claude Code sessions with comprehensive documentation.

**Supersedes**: `PROMPT_OPTIMIZATION_MANUAL.md`, `PROMPT_INDUCTION_CLI.md`, `PROMPT_INDUCTION_AUTOMATED.md` (all archived — those strategies were never adopted).

---

## How It Works

Patrick gives Claude Code an optimization objective in an interactive session. Claude experiments, measures, and documents findings. Patrick steers and approves. No CLI automation, no API infrastructure, no autonomous agents.

**Why interactive over autonomous**: Prompt optimization for this domain requires human judgment about clinical semantics, experiment design pivots, and real-time hypothesis generation. Autonomous agents can't do this well.

---

## Session Workflow

### 1. Objective

Patrick defines the goal: improve a metric, test a model, fix an error pattern, evaluate an architecture change, etc.

### 2. Read Context First

Before any changes:
- **Strategy doc**: [PROMPT_ENG_EXTRACTION_STRATEGY.md](PROMPT_ENG_EXTRACTION_STRATEGY.md) — cumulative lessons, what worked/failed, known blockers
- **Engineering log**: [PROMPT_ENGINEERING_LOG.md](PROMPT_ENGINEERING_LOG.md) — decision history
- **F1 timeseries**: [f1_timeseries.json](f1_timeseries.json) — historical scores
- **Recent induction reports**: `doc/induction-reports/` — what was tried recently

### 3. Establish Baseline

Run extraction on GT discussions and record F1 scores before changing anything.

**Harness**: `btcopilot/training/run_extract_full_f1.py` for full-extraction mode (6 GT discussions).

```bash
uv run python btcopilot/btcopilot/training/run_extract_full_f1.py
```

### 4. Experiment

Design and run experiments. This varies by objective:
- **Prompt changes**: Edit prompts, re-run F1, compare
- **Model evaluation**: Use `/tmp/run_experiments.py` pattern with monkey-patching for A/B testing
- **Architecture changes**: Test structural changes (e.g., single-pass vs split extraction)
- **Config tuning**: Thinking budget, temperature, token limits

**Rules during experimentation**:
- One variable at a time when possible
- Multi-run averages (2-3 minimum) for stochastic comparisons
- Revert changes that hurt F1
- Log negative results as thoroughly as positive ones

### 5. Document Everything

This is the most important step. See "Documentation Requirements" below.

---

## Where Prompts Live

| File | Purpose |
|------|---------|
| `btcopilot/personal/prompts.py` | Default prompts (open source, public) |
| `fdserver/prompts/private_prompts.py` | **Production overrides** (private repo, confidential) |

Production prompts are loaded via `FDSERVER_PROMPTS_PATH` env var. The fdserver overrides completely replace btcopilot defaults. All prompt editing targets `fdserver/prompts/private_prompts.py`.

**Prompt structure** (three constants, concatenated at runtime in `pdp.py`):
- `DATA_EXTRACTION_PROMPT` — SECTION 1 (data model) + SECTION 2 (rules). Contains `{current_date}` variable.
- `DATA_EXTRACTION_EXAMPLES` — SECTION 3 (error pattern examples, literal JSON, no variables)
- `DATA_EXTRACTION_CONTEXT` — Runtime context with `{diagram_data}`, `{conversation_history}`, `{user_message}`

**2-pass split architecture** (since T7-18):
- Pass 1 prompt: People + PairBonds + structural events (birth/death/married/etc.)
- Pass 2 prompt: Shift events + SARF variables (symptom/anxiety/relationship/functioning)
- Both in `fdserver/prompts/private_prompts.py`

---

## Documentation Requirements

**The protocol**: [btcopilot/training/prompts/induction_agent.md](../btcopilot/training/prompts/induction_agent.md) defines the authoritative logging/reporting format. Follow its documentation spec even in interactive sessions.

### What Must Be Created/Updated After Every Session

1. **Induction report** in `doc/induction-reports/<timestamp>[--description]/`
   - `<timestamp>.md` — Full report: methodology, results table, key findings, recommendations
   - `<timestamp>_log.jsonl` — Machine-readable iteration log (optional for interactive sessions, required for automated runs)

2. **Strategy doc update**: [PROMPT_ENG_EXTRACTION_STRATEGY.md](PROMPT_ENG_EXTRACTION_STRATEGY.md)
   - Add to "Things that worked" or "Things that failed"
   - Update F1 baselines if they changed
   - Correct any stale entries discovered during the session
   - Add new key insights

3. **Engineering log update**: [PROMPT_ENGINEERING_LOG.md](PROMPT_ENGINEERING_LOG.md)
   - Decision entry with rationale, alternatives considered, results

4. **F1 timeseries update**: [f1_timeseries.json](f1_timeseries.json)
   - Append data point(s) with final F1 scores
   - This feeds the admin/auditor dashboard chart

### Quality Bar for Documentation

Document at a level of detail sufficient for:
- **Research**: Could be cited in a paper or technical report
- **Resume/CV**: Demonstrates systematic methodology and quantitative rigor
- **Future self**: Someone (including Claude) can understand what was tried, why, and what the results mean without re-running experiments

---

## Prompt Editing Rules

From [induction_agent.md](../btcopilot/training/prompts/induction_agent.md):

- **ADD nuance, don't replace** — Each instruction represents careful tuning
- **One change at a time** — Test after every edit
- **Revert if worse** — If F1 drops, undo immediately
- **15-example budget** in SECTION 3 — Replace least effective before adding new
- **Confidentiality** — Never copy real names/quotes from GT into prompts. Invent generic examples.
- **SARF definitions are source of truth** — Prompt wording must match `doc/sarf-definitions/*.md`

---

## Key Files

| File | Purpose |
|------|---------|
| `fdserver/prompts/private_prompts.py` | Production prompts (edit target) |
| `btcopilot/personal/prompts.py` | Default prompts (open source fallback) |
| `btcopilot/training/run_extract_full_f1.py` | F1 evaluation harness (full-extraction) |
| `btcopilot/training/prompts/induction_agent.md` | Authoritative protocol for documentation/logging |
| `doc/PROMPT_ENG_EXTRACTION_STRATEGY.md` | Cumulative strategy — read first, update after |
| `doc/PROMPT_ENGINEERING_LOG.md` | Decision log |
| `doc/f1_timeseries.json` | Historical F1 data (feeds dashboard) |
| `doc/induction-reports/` | Per-session reports and logs |
| `doc/sarf-definitions/*.md` | Authoritative SARF variable definitions |
| `doc/specs/DATA_MODEL.md` | Schema docs (PDPDeltas, Person, Event, etc.) |

---

## Historical Context

Three strategies were considered in Dec 2025:

1. **Manual copy-paste** (`PROMPT_OPTIMIZATION_MANUAL.md`) — Export GT, paste into Claude, iterate. Too tedious.
2. **CLI autonomous agent** (`PROMPT_INDUCTION_CLI.md`) — `claude --prompt-file induction_agent.md` runs autonomously. Never adopted — interactive steering is more effective for this domain.
3. **API automated system** (`PROMPT_INDUCTION_AUTOMATED.md`) — Celery + web UI + auto-trigger. Never built — premature infrastructure.

What actually works: interactive Claude Code sessions where Patrick and Claude collaborate on experiment design, execution, and documentation. The `induction_agent.md` protocol is retained as the documentation standard, not as an autonomous agent script.
