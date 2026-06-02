# Dev Workflow Notes

Living log of lessons learned from the Jira-ticket → PR methodology. Add dated entries as new sessions surface new patterns or corrections.

---

## 2026-05-21 — FD-333 session

### MCP vs. direct TestInstance import

MCP tools (`familydiagram-testing` server) cannot be used for worktree testing. Root `.mcp.json` hardcodes the main clone path — launching via MCP always runs the main clone, not the worktree build. Workaround: import TestInstance directly.

```python
import sys
sys.path.insert(0, '/Users/patrick/theapp/familydiagram/.worktrees/FD-NNN')
from mcpserver.mcp_server import TestInstance, LoginState
```

### `committed_deletes` renamed to `delete` on PDP

`delete` is not a reserved keyword in Python (only `del` is) and is valid as a JS object property via dot notation (`item.delete`). The rename is safe. Do not revert to `committed_deletes`.

### `committed_edits` removed from PDP architecture

`committed_edits` field no longer exists. Positive-ID entries in `pdp.people`, `pdp.events`, and `pdp.pair_bonds` ARE the committed edits — `apply_deltas` stages them there automatically. Do not add `committed_edits` back.

### Fixture philosophy: meaningful over minimal

Minimal fixtures (1 Update + 1 Delete) show look-and-feel only. For real verification, fixtures must cover range:
- Multiple update types: name, gender, date
- Multiple deletes
- All entity types: person, event, pair_bond

Single-case fixtures produce false confidence — they will pass even when the full range of behavior is broken.

### Screenshot timing: `open_pdp_sheet` is async

`open_pdp_sheet` returns before the drawer animation completes. Sleep 0.8s before taking a screenshot or the drawer will be partially open. This applies in headed mode (`headless=False`). In headless/offscreen mode, take screenshots immediately.

### Script size target: under 80 lines

TestInstance handles server lifecycle, port allocation, bridge connection, and sandbox cleanup. There is no need for subprocess management, socket polling, or teardown boilerplate in the test script. If the script exceeds 80 lines, something is being done manually that TestInstance already handles.

### Per-card vs. bulk PDP actions

- `pdpAcceptButton` / `pdpRejectButton` — operate on the current SwipeView card
- `acceptAllButton` (in drawer header) — accepts all remaining cards at once

Both are needed for complete coverage: per-card for verifying individual item behavior, bulk for verifying the "accept all" fast path.

### SwipeView delegate traversal: `currentItem` must be searched first

The bridge's `_findQmlItemInChildren` uses `childItems()` recursively. SwipeView with a Repeater instantiates ALL delegates upfront (lazy loading is not the default). Without special handling, searching by objectName would find the FIRST card's button regardless of which card is currently visible.

Fix: check `item.property("currentItem")` before iterating `childItems()`. SwipeView exposes its active page via this property. Searching it first ensures the bridge finds the button on the currently-visible card.

### QML card buttons need objectName in all card types

`pdpAcceptButton` / `pdpRejectButton` must be set on ALL card component variants — not just `PDPPersonCard`. `committedEditCardComponent` and `committedDeleteCardComponent` also need these objectNames for the bridge to click them.

### Badge counter must include `pdp.delete`

`PersonalContainer.qml` computes the badge count from `pdp.people + pdp.pair_bonds + pdp.events`. It must also add `pdp.delete.length` or the badge will be lower than the actual card count in PDPSheet.

### `acceptAllPDPItems` must handle committed edits and deletes

The original implementation only collected negative-ID items (`person.id < 0`) and returned early if none existed. When the remaining queue is all committed edits (positive-ID people/events) or committed deletes, it silently did nothing.

Fix: collect `positiveEditIds` and `deleteIds` in addition to `negativeIds`. In the `applyChange` callback: call `commit_pdp_items(negativeIds)`, then `accept_committed_edit(eid)` for each, then `accept_committed_delete(did)` for each — all in a single `save()` call. After save: `_syncCommittedEditToScene`, `_removeCommittedItemsFromScene`, `pdpChanged.emit()`.

### `get_app_state` vs. `get_personal_state` for scene counts

`get_app_state` returns only login/view state for the Personal app — no scene data. Use `get_personal_state` with `component: "all"` to get `scene.personCount` and `scene.eventCount`.

## 2026-05-22 — jira-pr: mandatory Jira comment must include TestInstance import path

**What happened**: `/testing` session for FD-314/315/317 concluded the changes weren't in the codebase. The MCP `familydiagram-testing` server derives `project_root` from its own config file path — it was pointing at `~/worktrees/FD-333/familydiagram`, so the testing session launched the wrong code and found none of the three changed QML files. The session offered to update `.mcp.json`, which would have required a Claude Code restart and disturbed unrelated work.

**Root cause**: The Jira ticket comment only contained the PR URL. The `/testing` skill had no signal about the worktree path or that it should use TestInstance directly.

**Fix**: Step 6 of jira-pr SKILL.md now mandates a structured Jira comment on every ticket immediately after PR creation, containing: branch, worktree path, PR URL, repo scope, and an explicit "Testing note" with the TestInstance import path. Known Corrections updated to prohibit suggesting `.mcp.json` changes to the testing session.
