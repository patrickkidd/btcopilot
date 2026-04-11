# Conversational Model Quality Plan

**Created**: 2026-03-16
**Updated**: 2026-04-11
**Definition of done**: User can switch between models with friendly names and help text explaining behavioral differences, each produces human-verified conversational quality, regression metrics exist for all supported models, and development is automatically logged.

---

## Background

### Why This Exists

The personal app added user-selectable conversational models (Opus and Gemini Flash) starting 2026-03-11. On 2026-03-12 (`ef5641e`), the default switched from Gemini Flash to Claude Opus 4.6 — but the prompts had been written for Flash and were never revalidated. Opus with Flash-era prompts produces verbose, bullet-heavy, multi-question responses. Users switching between models will see wildly different quality levels. Both models need validated prompts, and the user needs to understand what they're choosing.

### Timeline

| Date | Commit | What |
|------|--------|------|
| 2026-03-11 | `5195517` | Built unified model routing (`response_text_sync`), chat was hardcoded to Gemini before this |
| 2026-03-12 | `ef5641e` | Switched default from Gemini Flash to Opus, minor prompt additions (domain knowledge, thinking budget) — **no prompt revalidation** |
| 2026-03-13 | `758325f` | Added model-specific addenda — misdiagnosed Opus as "too terse" (it's actually too verbose) |
| 2026-03-13 | `c0ce096` | Added `model` param to chat API, enabling user selection |
| 2026-03-14 | `d9effef` | Introduced synthetic client bug ("Trail off on hard topics") — contaminated all test runs |
| 2026-03-15 | — | Exp1 prompt rewrite for Opus (core + Opus addendum); Exp2 thinking=0 rejected |
| 2026-03-16 | `9fc6db2` | Exp1 committed to fdserver after eyeball validation; synthetic client fallback fix committed |
| 2026-04-11 | — | Gemini eyeball validation: old addendum bad, guideline rewrite improved FM3/FM1, FM2/FM4/FM5 remain |

### Experiment History

Full details in `doc/log/synthetic-clients/2026-03-15_19-00--opus-conversational-prompt-tuning.md` and `doc/log/synthetic-clients/2026-04-11_10-00--gemini-eyeball-validation.md`.

| Experiment | Scope | Result |
|------------|-------|--------|
| Exp1: Core + Opus rewrite | Terminal directive, phase counts, pivot logic | Shipped — Opus quality dramatically improved |
| Exp2: Thinking=0 | Disable extended thinking | Rejected — sentence completion, context loss, no pivots |
| Gemini old addendum | 5 rule-based lines against new core | Bad — topic stagnation, reformulation loops, fragment completion, zero variety |
| Gemini guideline rewrite | Voice/approach framing instead of rules | Better — fixed fragment completion, improved pivoting, but still reformulation loops and no response variety |

---

## Current State

### Prompt Assembly

```
fdserver/prompts/private_prompts.py
  get_conversation_flow_prompt(model) →
    _CONVERSATION_FLOW_CORE          (shared, rewritten in Exp1, VALIDATED with Opus)
    + _CONVERSATION_FLOW_OPUS        (Opus addendum, rewritten in Exp1, VALIDATED)
    or _CONVERSATION_FLOW_GEMINI     (guideline rewrite 2026-04-11, PARTIALLY VALIDATED)
```

### Model Selection Flow

```
QML ModelSettingsPage → personalApp.setResponseModel("opus-4.6")
  → QSettings persistence
  → POST /personal/discussions/{id}/statements { model: "opus-4.6" }
  → llmutil.resolve_model("opus-4.6") → "claude-opus-4-6"
  → response_text_sync(model="claude-opus-4-6") → claude_text() or gemini_text()
  → get_conversation_flow_prompt(model) → core + model-specific addendum
```

### Validation Status

| Model | Prompt status | Eyeball validated? | Known issues |
|-------|--------------|-------------------|--------------|
| Opus 4.6 | Exp1 rewrite, shipped | Yes (2026-03-16) | None observed |
| Gemini 2.5 Flash | Guideline rewrite, uncommitted | Partially (2026-04-11) | FM2: reformulation loops, FM4: no response variety, FM5: off-domain pivots |

### Gemini Failure Modes (from 2026-04-11 eyeball)

| FM | Description | Status | Metric |
|----|-------------|--------|--------|
| FM1 | Topic stagnation (all turns on one topic) | Improved — pivots sooner | Max consecutive turns on same topic (fail >3) |
| FM2 | Reformulation loop (rephrasing same question) | Still present | Consecutive semantically similar AI questions (fail >2) |
| FM3 | Fragment completion (echoing user's unfinished words) | Fixed | Regex: AI contains "..." + user's last words (any = fail) |
| FM4 | Zero response type variety | Still present | Response entropy <0.5 = fail |
| FM5 | Off-domain pivot (medical/non-family questions) | New | Manual tag or keyword check for non-family topics |

**Confounding factor**: Synthetic client generates fallback evasive responses on ~60% of turns, giving the coach nothing to work with. Gemini coaching quality may look better with a real human user who gives substantive answers. Needs real human eyeball test.

### Synthetic Client Infrastructure

| Component | Status |
|-----------|--------|
| Personas (Sarah, Marcus, Jennifer) | Working |
| ConversationSimulator | Working |
| QualityEvaluator metrics | Working but unreliable with broken client |
| Gemini synthetic client | Broken — generates stubs ~50% of turns; sub-8-word fallback masks worst failures but produces flat evasive filler that confounds coach evaluation |

### Artifacts

| Path | Contents |
|------|----------|
| `doc/log/synthetic-clients/baselines/` | Contaminated (pre-client-fix) |
| `doc/log/synthetic-clients/baseline2/` | Clean baseline, original prompts |
| `doc/log/synthetic-clients/experiment1b/` | Clean, Exp1 prompts |
| `doc/log/synthetic-clients/experiment2/` | Contaminated, thinking=0 (rejected) |
| `doc/log/synthetic-clients/eyeball-comparison/` | Validation transcripts (Opus + Gemini) |
| `doc/log/synthetic-clients/2026-03-15_19-00--opus-conversational-prompt-tuning.md` | Opus experiment log |
| `doc/log/synthetic-clients/2026-04-11_10-00--gemini-eyeball-validation.md` | Gemini validation log |

---

## Burndown

### 1. Gemini prompt validation — IN PROGRESS
- [x] Run eyeball with old addendum — bad (topic stagnation, reformulation, fragment completion)
- [x] Rewrite addendum as guidelines instead of rules
- [x] Re-run eyeball — partial improvement (FM3 fixed, FM1 improved, FM2/FM4/FM5 remain)
- [x] Log all failure modes with proposed metrics
- [ ] **Real human eyeball test** — synthetic client confounds results, need Patrick to chat with Gemini coach manually and assess
- [ ] Iterate on addendum if human test reveals issues distinguishable from client noise

### 2. User-facing model names — IMPLEMENTED
- [x] Names decided: **Premium** (Opus) / **Standard** (Gemini)
- [x] Help text added to each model with behavioral descriptions
- [x] Updated `AVAILABLE_MODELS` in `familydiagram/pkdiagram/personal/personalappcontroller.py` — added `description` field
- [x] Updated `ModelSettingsPage.qml` — description text below name, dynamic row height
- [x] Renamed settings menu item "Model" → "Coaching Style" in `AccountDrawer.qml` and `PersonalContainer.qml`
- [x] Page header updated: "Model" → "Coaching Style"
- [x] Footer text updated to match
- [ ] Visual verification in app (needs build + manual check)

### 3. Regression metrics — DEFINED, NOT IMPLEMENTED
- [ ] Decide: fix synthetic client or accept eyeball-only?
- [ ] Implement metrics from FM table (topic stagnation, reformulation, fragment completion, entropy, off-domain)
- [ ] Define pass/fail thresholds after clean baseline runs
- [ ] Create runnable regression script per model
- [ ] Document as pre-deploy check

### 4. Docs
- [x] Correct CHAT_FLOW.md ("Opus tends terse" → "Opus tends verbose")
- [x] Log Opus experiment findings
- [x] Log Gemini validation findings
- [ ] Add prompt induction rule: prefer guidelines over rules for LLM behavior shaping

### 5. Development logging
- [x] Manual dev log convention in `doc/log/synthetic-clients/` — adequate for now
- [ ] Decide if automation needed beyond manual timestamped entries

---

## Prompt Engineering Lesson Learned

**Prefer guidelines over rules for LLM behavior shaping.** Rule-based constraints ("if X then do Y", "do NOT do X") produce brittle compliance that breaks on edge cases. Guideline-based framing ("you're curious about the whole picture, not any single detail") lets the model infer appropriate behavior across situations. Validated in the Gemini addendum iteration: rules produced worse results than guidelines on every failure mode. This principle should be added to the prompt induction instructions.