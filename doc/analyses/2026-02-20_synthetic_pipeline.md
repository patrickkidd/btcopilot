# Synthetic Discussion Generation Pipeline Analysis

**Date:** 2026-02-20

## Current State: ~85% Complete, Fragile Under Automation

All major components exist and connect. Works in controlled manual conditions. Breaks under real usage (Celery failures, no error recovery, no auto-extraction trigger).

## What Works
- Persona generation (web form → LLM → SyntheticPersona table)
- Conversation simulation (ConversationSimulator.run() alternates user/AI)
- PDP extraction during chat (ask() → pdp.update() per statement)
- GT coding workflow (SARF editor → auditor review → approval)
- F1 metric calculation (dashboard shows scores with synthetic filter)
- Diagram integration (synthetic discussion → diagram with PDP)

## What Doesn't Work

### No Error Handling in Celery Task (CRITICAL)
- `training/tasks.py:128-150`: `simulator.run()` not wrapped in try/catch
- LLM timeout mid-conversation → task crashes → discussion orphaned in DB
- No cleanup of half-created discussions

### No Auto-Extraction Trigger
- `training/tasks.py:145-151`: After generation completes, extraction is NOT auto-queued
- If `skip_extraction=True`, user must manually trigger extraction (but no mechanism exists)
- Missing: `celery.send_task("extract_next_statement")` after generation

### No Discussion State Machine
- Only has `extracting` boolean. Need full states:
  pending → generating → failed → pending_extraction → extracting → ready_for_coding

### Quality/Coverage Evaluators Not Integrated
- QualityEvaluator and CoverageEvaluator exist in `tests/personal/synthetic.py:1103+`
- NOT called in Celery task. `result.quality` always None.
- Dashboard can't show quality scores for synthetics.

### No Generated Persona Validation
- `synthetic.py:945-970`: `json.loads()` on LLM response with no error handling
- Invalid JSON → crash → user sees 500 error

### No Progress Feedback in Web UI
- Task status endpoint returns state but no per-turn progress
- User sees "Generating..." with no indication of progress (turn 5/20, etc.)

## Key Files
| Component | File |
|-----------|------|
| Celery task | `btcopilot/training/tasks.py:78-151` |
| ConversationSimulator | `btcopilot/tests/personal/synthetic.py:680-848` |
| Web routes | `btcopilot/training/routes/synthetic.py` |
| Persona model | `btcopilot/personal/models/syntheticpersona.py` |
| Chat orchestration | `btcopilot/personal/chat.py:24-80` |
| Quality evaluator | `btcopilot/tests/personal/synthetic.py:1103+` |

## Test Coverage
### Exists
- Unit tests for prompt structure, trait behaviors, quality heuristics
- E2E tests for single/multiple persona conversations (marked slow)

### Missing
- Web endpoint tests (`/synthetic/generate`, `/synthetic/task/<id>`)
- Celery error recovery tests
- Extraction auto-trigger tests
- Persona JSON validation tests
- F1 calculation with synthetic GT (end-to-end)

## Fix Priority
1. Add error handling + cleanup in Celery task (~4 hours)
2. Auto-trigger extraction after generation (~2 hours)
3. Implement Discussion.status state machine (~6 hours)
4. Validate persona JSON (~1 hour)
5. Integrate quality/coverage evaluators (~4 hours)
