# MVP Task Review Tracker

Cross-ref: [MVP_DASHBOARD.md](../../../MVP_DASHBOARD.md) | Task logs: `T*.md` in this directory

Status: `pending` | `approved` | `rejected` | `revised`

| Task | Log | Summary | Files | Status | Notes |
|------|-----|---------|-------|--------|-------|
| T0-1 | [T0-1.md](T0-1.md) | EmotionalUnit guard for None _layer | `familydiagram/pkdiagram/scene/emotionalunit.py` | revised | Early return at top of update() |
| T0-2 | [T0-2.md](T0-2.md) | Marriage crash on corrupt pair_bond | `inspector.py` | revised | Root cause: MCP harness field name mismatch. Only inspector.py fix approved; 3 defensive reader fixes dropped |
| T1-3 | [T1-3.md](T1-3.md) | Reject null event descriptions in validation | `btcopilot/pdp.py`, `tests/schema/test_validation.py` | approved | |
| T1-5 | [T1-5.md](T1-5.md) | Already implemented | — | approved | No-op, `current_date` already in prompt |
| T2-2 | [T2-2.md](T2-2.md) | Arrange endpoint error handling | `btcopilot/pro/routes.py` | approved | |
| T2-3 | [T2-3.md](T2-3.md) | Show arrange error in QMessageBox | `familydiagram/.../documentcontroller.py` | approved | |
| T2-4 | [T2-4.md](T2-4.md) | Non-Inside/Outside triangle emotions | `scene.py`, `test_event_triangles.py` | rejected | Reverted — triangles are exclusively Inside/Outside |
| T2-6 | [T2-6.md](T2-6.md) | _log not defined on view delete | — | approved | No-op, cannot reproduce |
| T3-1 | [T3-1.md](T3-1.md) | Cluster label width constraint | `LearnView.qml` | approved | Code reviewed, committed |
| T3-2 | [T3-2.md](T3-2.md) | Already implemented | — | approved | No-op, selection feedback already exists |
| T3-3 | [T3-3.md](T3-3.md) | Use calculateOptimalZoom() | `LearnView.qml` | approved | Code reviewed, committed |
| T3-4 | [T3-4.md](T3-4.md) | Single-line SARF format | `PDPEventCard.qml` | approved | Code reviewed, committed |
| T3-5 | [T3-5.md](T3-5.md) | Rename User→Client, Assistant→Coach | `discussions.py`, `discussion.js` | approved | Code reviewed, committed |
| T3-6 | [T3-6.md](T3-6.md) | Already implemented | — | approved | No-op, `delayedScrollToBottom()` exists |
| T4-1 | [T4-1.md](T4-1.md) | Remove broad except Exception | `tasks.py`, `synthetic.py` | approved | Exceptions propagate, failed check reordered |
| T4-3 | [T4-3.md](T4-3.md) | DiscussionStatus enum + migration | `discussion.py`, migration | approved | 6 states, transitions at all mutation points |
| T4-5 | [T4-5.md](T4-5.md) | JSONDecodeError → ValueError | `synthetic.py` | approved | |
| T5-5 | [T5-5.md](T5-5.md) | SARF editor validation at save | `feedback.py`, `discussion.js` | approved | Code reviewed, committed |
