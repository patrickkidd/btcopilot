# MVP Task Review Tracker

Patrick's approval log for MVP Dashboard tasks. Each row records a Claude Code implementation attempt, Patrick's review decision, and any revision notes. Tasks require explicit Patrick approval before the dashboard is updated. "No-op" entries are tasks that were already done or couldn't be reproduced — logged here to prevent re-investigation.

Cross-ref: [MVP_DASHBOARD.md](../../../MVP_DASHBOARD.md) | Task logs: `T*.md` in this directory

Status: `pending` | `approved` | `rejected` | `revised`

| Task | Log | Summary | Files | Status | Notes |
|------|-----|---------|-------|--------|-------|
| T0-1 | [T0-1.md](T0-1.md) | EmotionalUnit guard for None _layer | `familydiagram/pkdiagram/scene/emotionalunit.py` | revised | Early return at top of update() |
| T0-2 | [T0-2.md](T0-2.md) | Marriage crash on corrupt pair_bond | `inspector.py` | revised | Root cause: MCP harness field name mismatch. Only inspector.py fix approved; 3 defensive reader fixes dropped |
| T1-3 | [T1-3.md](T1-3.md) | Reject null event descriptions in validation | `btcopilot/pdp.py`, `tests/schema/test_validation.py` | approved | Prior session commit; cosmetic diff reverted |
| T1-5 | [T1-5.md](T1-5.md) | Already implemented | — | approved | No-op, `current_date` already in prompt |
| T2-2 | [T2-2.md](T2-2.md) | Arrange endpoint error handling | `btcopilot/pro/routes.py` | approved | Code reviewed, committed |
| T2-3 | [T2-3.md](T2-3.md) | Show arrange error in QMessageBox | `familydiagram/.../documentcontroller.py` | approved | Prior session commit; pending Patrick review |
| T2-4 | [T2-4.md](T2-4.md) | Non-Inside/Outside triangle emotions | `scene.py`, `test_event_triangles.py` | rejected | Reverted — triangles are exclusively Inside/Outside |
| T2-6 | [T2-6.md](T2-6.md) | _log not defined on view delete | — | approved | No-op, cannot reproduce |
| T3-1 | [T3-1.md](T3-1.md) | Cluster label width constraint | `LearnView.qml` | approved | Code reviewed, committed |
| T3-2 | [T3-2.md](T3-2.md) | Already implemented | — | approved | No-op, selection feedback already exists |
| T3-3 | [T3-3.md](T3-3.md) | Use calculateOptimalZoom() | `LearnView.qml` | approved | Code reviewed, committed |
| T3-4 | [T3-4.md](T3-4.md) | Single-line SARF format | `PDPEventCard.qml` | approved | Code reviewed, committed |
| T3-5 | [T3-5.md](T3-5.md) | Rename User→Client, Assistant→Coach | `discussions.py`, `discussion.js` | approved | Code reviewed, committed |
| T3-6 | [T3-6.md](T3-6.md) | Already implemented | — | approved | No-op, `delayedScrollToBottom()` exists |
| T4-1 | [T4-1.md](T4-1.md) | Remove broad except Exception | `tasks.py`, `synthetic.py` | approved | Code reviewed, committed |
| T4-3 | [T4-3.md](T4-3.md) | DiscussionStatus enum + migration | `discussion.py`, migration | approved | Code reviewed, committed |
| T4-5 | [T4-5.md](T4-5.md) | JSONDecodeError → ValueError | `synthetic.py` | approved | Code reviewed, committed |
| T5-5 | [T5-5.md](T5-5.md) | SARF editor validation at save | `feedback.py`, `discussion.js` | approved | Code reviewed, committed |
| T1-1 | — | PairBond extraction examples in fdserver prompt | `fdserver/prompts/private_prompts.py` | approved | 2026-02-24 staleness audit: 2 labeled examples (`[PAIR_BOND_EXTRACTION]`, `[PAIR_BOND_WITH_MARRIAGE_EVENT]`) + trigger rules already present. Done ~Feb 2026. |
| T1-2 | — | Event extraction examples in fdserver prompt | `fdserver/prompts/private_prompts.py` | approved | 2026-02-24 staleness audit: 18 labeled examples covering over/under-extraction, births, shifts, anxiety, distance, death, duplicates, SARF, triangles. Done ~Feb 2026. |
| T5-4 | — | Revert f1_metrics.py workarounds | — | approved | 2026-02-24 staleness audit: No workarounds exist to revert. Code cleanly skips unmatchable events (lines 625-626, 653-655). Task is N/A. |
| T5-6 | — | Cumulative F1 metric | `btcopilot/training/f1_metrics.py` | approved | 2026-02-24 staleness audit: `calculate_cumulative_f1()` and `calculate_all_cumulative_f1()` fully implemented. Wired into admin (line 271) and audit (line 99) routes. |
| T0-2 | — | Not a bug — pair bond inference is correct | — | pending | 2026-02-24: Investigated. `isPairBond()` correctly includes Separated/Divorced — those events imply the couple had a pair bond. Original MCP harness bug was fixed earlier (inspector.py). Added regression tests: `test_separated_event_infers_pair_bond`, `test_divorced_event_infers_pair_bond`. No code change needed. |
| T0-5 | — | Fix birth event child resolution crash | `btcopilot/schema.py` | pending | 2026-02-24: `_create_inferred_birth_items` Case 2 created spouse but not child, leaving `event.child=None`. Scene crashed at `eventsFor(item.child())`. Fix: Case 2 now creates inferred child. Tests: `test_birth_with_person_only_creates_inferred_child`, `test_accept_all_birth_with_person_only_no_crash`. |
