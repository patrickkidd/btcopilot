# Bugs & TODOs Inventory

**Date:** 2026-02-20

## Critical Crashes (Blocking MVP)

| Bug | File | Trigger |
|-----|------|---------|
| emotionalunit.py AttributeError (NoneType.id) | `scene/emotionalunit.py:34` | Adding PDP item with parent refs |
| pickle TypeError on version conflict | `server_types.py:295` | Save after version conflict dialog |
| `_log not defined` | familydiagram views | Re-opening after deleting views with person |

## Data Integrity Bugs

| Bug | Severity |
|-----|----------|
| Accepting Conflict event doesn't set childOf properly | High |
| Accepting Separated event creates extra grandparents | High |
| Pro app applyChange overwrites Personal data on conflict | High (data loss) |
| Event.description can be null (warns, doesn't reject) | Medium |
| Event.dateTime can be null (breaks timeline + F1) | Medium |
| Uncommitted person picker warning broken | Medium |
| Adding pair-bond event adds duplicate pair-bond to scene | Medium |
| Chat response race condition (async overwrite) | Medium |
| Undo doesn't persist to server | Low |

## UI/UX Issues (Personal App)

| Issue | Severity |
|-------|----------|
| Cluster graph text overlaps | High |
| No selection indication on cluster graph | Medium |
| Empty space to right of clusters | Medium |
| SARF extraction should show direction ("Symptom: Up") | Medium |
| No scroll-to-bottom on chat submit | Medium |
| "User" still shown after person delta (should be "Client") | Low |
| Rename "Assistant" to "Coach" | Low |
| Number of AI responses badge shows wrong count | Low |
| Date editor UX issues | Low |
| Chat window height not optimized | Low |

## UI/UX Issues (Pro App)

| Issue | Severity |
|-------|----------|
| Can't clear SARF variable in event | High |
| _do_addItem missing relationshipTriangle symbols | High |
| Baseline view doesn't work in new diagrams | Medium |
| Can't add people to view then activate (still hidden) | Medium |
| Click event in timeline should highlight people in diagram | Medium |
| Outside move should only show Event.relationshipTargets | Low |
| Only show isDateRange for shift events | Low |

## Extraction Issues

| Issue | Severity |
|-------|----------|
| Event F1 = 0.09 (prompt lacks examples) | Critical |
| SARF variable F1 = 0.11 (non-functional) | Critical |
| PairBond F1 = 0.0 (no extraction examples in prompt) | High |
| Conversation history not effectively reused | Medium |
| No date estimation for vague temporal references | Medium |
| Current date not included in prompt | Low |

## GT/F1 Issues

| Issue | Severity |
|-------|----------|
| 40% of GT events structurally unmatchable | Critical |
| Per-statement F1 indistinguishable across 6 prompt iterations | Critical |
| Cumulative F1 not implemented | High |
| Only 3 discussions coded (need 20-30) | High |
| f1_metrics.py workarounds mask broken GT | Medium |
| No SARF editor validation (allows broken GT) | Medium |

## Synthetic Pipeline Issues

| Issue | Severity |
|-------|----------|
| No error handling in Celery task | High |
| No auto-extraction trigger after generation | High |
| No Discussion.status state machine | Medium |
| Quality/coverage evaluators not integrated | Medium |
| No persona JSON validation | Low |

## Existing Plans

| Plan | File | Status |
|------|------|--------|
| GT Strategy Realignment | `btcopilot/doc/plans/GT_STRATEGY_REALIGNMENT.md` | Phase 1 not started |
| Add Notes to PDP | `btcopilot/doc/plans/ADD_NOTES_TO_PDP.md` | Ready to implement |
| Learn Tab Evaluation | `btcopilot/doc/plans/LEARN_TAB_EVALUATION.md` | Literature complete, needs domain expert |
| Synthetic Client Personalities | `btcopilot/doc/plans/SYNTHETIC_CLIENT_PERSONALITIES.md` | In progress |
| Pattern Intelligence Vision | `btcopilot/doc/plans/PATTERN_INTELLIGENCE_VISION.md` | Brainstorming |
| SARF Graph Focused Mode | `btcopilot/doc/plans/SARF_GRAPH_FOCUSED_MODE.md` | Proposed |

## Skipped Tests

Files with `skip`/`xfail` markers:
- `tests/personal/synthetic.py`
- `tests/conftest.py`
- `tests/pro/test_licensing.py`
- `tests/pro/copilot/test_model.py`
- `tests/pro/copilot/test_ingest.py`
- `tests/pro/test_diagrams.py`
- `tests/training/test_pdp_content.py`
- `tests/training/routes/test_discussions.py`
- `tests/training/test_ask_content.py`

## Recent Git Pattern

Heavy focus on infrastructure/config, MCP servers, test collection fixes. No sustained feature implementation. Commit messages suggest thrashing ("Updates", "more", "stuff").
