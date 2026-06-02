# Workstream Engine — Implementation Plan
*2026-05-23. Execute in a fresh CC session. Work in origin clones (meta-workstream, no worktree needed).*

## Context

Full architecture brainstorm and ACs:
- `btcopilot/doc/brainstorming/2026-05-23--workstream-engine.md`
- `btcopilot/doc/brainstorming/2026-05-23--workstream-engine-acs.md`

Current state (to be replaced):
- `.claude/ws/orchestrator.py` — CLI state machine, superceded by MCP server
- `.claude/ws/registry.json` — flat JSON state store, superceded by SQLite
- `.claude/ws/rules/{implementing,testing,review}.json` — migrate content to SQLite
- `.claude/skills/workstream/SKILL.md` — rewrite to ~40 lines calling MCP tools
- `.claude/skills/ws/SKILL.md` — keep as one-liner alias

---

## Architecture Decisions (locked in)

- **HTTP MCP server** (not stdio) so logic changes hot-reload without CC restart
- **FastMCP + uvicorn `--reload`** — file change → server reloads automatically
- **SQLite for all state** — workstream records, rules, stage history, FMs. Persists across CC sessions and CC restarts.
- **`next` field** — every MCP tool response includes a hardcoded routing string. Skill follows it. No LLM in the MCP server.
- **PostToolUse hook on Write** — fires when sub-agent writes `/tmp/ws_out_FD-*.json`, calls `ws_validate`, blocks turn if FAIL
- **Dynamic sandbox management** — `ws_start_sandbox` / `ws_stop_sandbox` look up worktree from SQLite per ticket. Multiple concurrent workstreams each get their own sandboxed port.
- **`btcopilot-flask` and `familydiagram-testing` entries in `.mcp.json` are superseded** — the workstream server manages app launch/sandbox dynamically. Remove them once the new server is working.

---

## Phase 1 — MCP Server

### File location
`/Users/patrick/theapp/.claude/ws/mcp_server.py`

### Dependencies
Root `pyproject.toml` already has `mcp>=1.0.0`. Also needs `uvicorn`. Check:
```bash
grep -E "uvicorn|fastapi" /Users/patrick/theapp/pyproject.toml
```
Add `uvicorn` if missing:
```bash
uv add uvicorn --directory /Users/patrick/theapp
```

### Run command (for .mcp.json registration)
```bash
uv run --directory /Users/patrick/theapp uvicorn \
  --app-dir /Users/patrick/theapp/.claude/ws \
  mcp_server:app \
  --host 127.0.0.1 --port 8890 --reload
```

### SQLite schema

```sql
CREATE TABLE IF NOT EXISTS workstreams (
    ticket TEXT PRIMARY KEY,
    summary TEXT,
    stage TEXT NOT NULL DEFAULT 'planning',
    repos TEXT NOT NULL DEFAULT '[]',        -- JSON array
    worktree TEXT,
    blast_radius TEXT,
    pr_urls TEXT DEFAULT '{}',               -- JSON object
    jira_comment_posted INTEGER DEFAULT 0,
    sandbox_port INTEGER,
    tasks_remaining TEXT DEFAULT '[]',       -- JSON array
    open_questions TEXT DEFAULT '[]',        -- JSON array
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS stage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket TEXT NOT NULL,
    stage TEXT NOT NULL,
    entered TEXT NOT NULL,
    exited TEXT
);

CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,              -- e.g. "I001", "T001"
    stage TEXT NOT NULL,              -- implementing | testing | reviewing
    category TEXT NOT NULL,
    rule TEXT NOT NULL,
    check_schema TEXT,                -- optional JSON schema for auto-validation
    added TEXT NOT NULL,
    supersedes TEXT                   -- id of replaced rule
);

CREATE TABLE IF NOT EXISTS failure_modes (
    id TEXT PRIMARY KEY,
    ticket TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,           -- High | Med | Low
    repro TEXT,
    screenshot TEXT,
    verified_by TEXT,                 -- 'agentic' | 'human' | null
    created_at TEXT
);
```

DB file: `/Users/patrick/theapp/.claude/ws/ws.db`

### Seed rules on first run
On startup, if `rules` table is empty, migrate from existing JSON files:
- `.claude/ws/rules/implementing.json`
- `.claude/ws/rules/testing.json`
- `.claude/ws/rules/review.json`

Each JSON file has `rules[]` array with `{id, category, rule, added}` shape — insert directly.

### Tools to implement

**`ws_enter(ticket: str | None) → WSEnterResult`**

The reset button. Called at the top of every `/ws` invocation.

Returns:
```json
{
  "found": true,
  "ticket": "FD-NNN",
  "stage": "testing",
  "state": { ...full workstream row... },
  "rules_text": "R001: ...\nR002: ...",
  "next": "<routing instruction string>"
}
```

`next` values (hardcoded Python, NOT generated):
- ticket is None or not found → `"not_found: call ws_create(), then ask Patrick in ONE message: repos in scope, schema changes, constraints, test hardware"`
- `planning` → `"planning: fetch Jira ticket, ask Patrick clarifying questions, create worktrees, call ws_advance()"`
- `implementing`, no pr_urls → `"spawn_implementing: use rules_text and prompt template from skill, spawn implementing sub-agent"`
- `implementing`, pr_urls exist, jira_comment_posted → `"grind_implementing: PRs exist, present human script inline, iterate until Patrick signs off, then ws_advance()"`
- `testing`, sandbox_port null → `"start_sandbox: call ws_start_sandbox(ticket), then spawn_testing"`
- `testing`, sandbox_port set → `"spawn_testing: sandbox on port {port}, use rules_text and prompt template from skill, spawn testing sub-agent"`
- `reviewing` → `"spawn_reviewing: use rules_text and prompt template from skill, spawn reviewing sub-agent"`
- `done` → `"done: workstream complete"`

`rules_text` is a formatted string: one rule per line, `{id}: {rule}`.
Only include rules for the current stage.

---

**`ws_create(ticket: str, repos: list[str], summary: str) → {ok: bool, next: str}`**

Insert row into `workstreams`. Insert first `stage_history` entry (`planning`, entered=now, exited=null).

---

**`ws_advance(ticket: str) → {new_stage: str, next: str}`**

Transition to next stage. Stages in order: `planning → implementing → testing → reviewing → done`.

Write `exited` on current `stage_history` row. Insert new row for next stage.

---

**`ws_update(ticket: str, **kwargs) → {ok: bool}`**

Update any fields on the workstream row. Accepted kwargs: `blast_radius`, `pr_urls` (dict), `jira_comment_posted` (bool), `sandbox_port` (int), `tasks_remaining` (list), `open_questions` (list), `worktree` (str).

---

**`ws_add_rule(stage: str, category: str, rule: str, check_schema: str | None = None) → {id: str, ok: bool}`**

Auto-generate ID: stage prefix (`I`/`T`/`R`) + next available number. Insert into `rules`.
No server restart needed — `ws_enter` reads from DB on every call.

---

**`ws_remove_rule(stage: str, rule_id: str) → {ok: bool}`**

Delete from `rules`.

---

**`ws_log_fm(ticket: str, description: str, severity: str, repro: str, screenshot: str | None = None, verified_by: str | None = None) → {id: str}`**

Insert into `failure_modes`. Auto-generate ID: `FM-{ticket}-{n}`.

---

**`ws_validate(ticket: str, stage: str, output_path: str) → {pass: bool, failures: list[str]}`**

Read JSON from `output_path`. Run validation:

*implementing*: require `pr_urls` (non-empty dict), `jira_comment_posted: true`, `blast_radius` (non-empty string), `human_test_script` (list, 1–7 items, each has `arrange`/`act`/`assert`).

*testing*: require `sandbox_confirmed: true`, `human_script` (list, 1–7 items, each has `arrange`/`act`/`assert`), `test_results` (non-empty list), `bugs` (list, may be empty).

*reviewing*: require `verdict` (`APPROVED` or `NEEDS_WORK`), `blocking_issues` (list), `non_blocking_issues` (list).

Also run any rules with `check_schema` set for the given stage — validate against the output JSON.

---

**`ws_start_sandbox(ticket: str, port: int = 8889) → {ok: bool, port: int}`**

Look up `worktree` from DB for `ticket`. Start sandboxed btcopilot Flask server:
```python
env = {**os.environ}
load_env(env)  # reads ~/theapp/.env
env['FLASK_CONFIG'] = 'testing'
subprocess.Popen(
    ['uv', 'run', 'flask', '--app', 'btcopilot.app:create_app', 'run', '--port', str(port)],
    cwd=f"{worktree}/btcopilot",
    env=env
)
```
Update `sandbox_port` in DB.

---

**`ws_stop_sandbox(ticket: str) → {ok: bool}`**

Kill the sandboxed Flask process for this ticket's port. Clear `sandbox_port` in DB.

---

**`ws_kanban() → {markdown: str}`**

Return markdown table of all non-done workstreams. Columns: Ticket, Summary, Stage, Blockers, Tasks, PRs.

---

**`ws_detail(ticket: str) → {markdown: str, state: dict}`**

Return full workstream state as both structured JSON and formatted markdown. Include: stage history, open questions, tasks remaining, PR URLs, FM list with validation status, blast radius.

---

## Phase 2 — Register + Hook

### `.mcp.json` entry
```json
"workstream": {
  "type": "http",
  "url": "http://127.0.0.1:8890/mcp"
}
```

Remove or comment out `btcopilot-flask` and `familydiagram-testing` entries — the workstream server replaces them dynamically.

### PostToolUse hook in `.claude/settings.json`

Add to the `PostToolUse` hooks array:
```json
{
  "matcher": "Write",
  "hooks": [{
    "type": "command",
    "command": "python3 -c \"\nimport json, sys, subprocess, re\ndata = json.load(sys.stdin)\npath = data.get('tool_input', {}).get('file_path', '')\nm = re.search(r'ws_out_(FD-\\\\d+)\\\\.json', path)\nif not m: sys.exit(0)\nticket = m.group(1)\nimport urllib.request\nreq = urllib.request.Request('http://127.0.0.1:8890/mcp', ...)\n# call ws_validate via HTTP\n\"",
    "timeout": 30
  }]
}
```

**Simpler approach**: the hook calls a thin Python script at `.claude/ws/validate_hook.py` instead of inline Python. The script reads stdin, extracts the file path, calls `ws_validate` via HTTP, and exits non-zero with a `stopReason` JSON payload if validation fails.

Hook command:
```bash
uv run --directory /Users/patrick/theapp python /Users/patrick/theapp/.claude/ws/validate_hook.py
```

`validate_hook.py` behavior:
1. Read stdin JSON, extract `tool_input.file_path`
2. If path doesn't match `ws_out_FD-*.json` → exit 0 silently
3. Extract ticket from filename
4. Infer stage from `ws_enter(ticket)` response
5. POST to `http://127.0.0.1:8890/mcp` → `ws_validate(ticket, stage, output_path)`
6. If `pass: true` → exit 0
7. If `pass: false` → print `{"continue": false, "stopReason": "Validation failed: {failures}"}` and exit 1

---

## Phase 3 — Rewrite Skill

Replace `.claude/skills/workstream/SKILL.md` entirely. Target: ~40 lines, zero domain knowledge.

```markdown
---
name: workstream
description: Single entry point for the full workstream lifecycle.
argument-hint: "[FD-NNN | kanban | FD-NNN detail]"
---

## Entry

/ws (no args) or /ws kanban → call ws_kanban(), render result.
/ws FD-NNN detail → call ws_detail(FD-NNN), render result.
/ws FD-NNN → call ws_enter(FD-NNN), follow next field below.

## Self-learning

When Patrick corrects anything: call ws_add_rule(stage, category, rule).
Say "Added as {id}". Never modify this skill file.

## Routing (follow next field from ws_enter)

not_found → call ws_create(), ask Patrick: repos, schema changes, constraints, test hardware (ONE message, wait for answers)

planning → fetch Jira ticket (curl with ATLASSIAN_TOKEN from ~/theapp/.env), create worktrees,
           call ws_advance(ticket)

spawn_implementing → load rules_text from ws_enter result. Fetch Jira ACs. Read git diff.
    Spawn implementing sub-agent (Sonnet) with:
    - rules_text injected verbatim
    - Jira ACs
    - worktree path + repos in scope
    - instruction to write output JSON to /tmp/ws_out_{ticket}.json
    [Full sub-agent prompt template — see below]

grind_implementing → PRs exist. Present human_test_script inline. Await Patrick sign-off.
    Patrick complaint → fix in worktree → relaunch → repeat.
    Sign-off → ws_advance(ticket)

start_sandbox → call ws_start_sandbox(ticket), then re-enter spawn_testing

spawn_testing → load rules_text. Fetch Jira ACs. Read git diff.
    Spawn testing sub-agent (Sonnet) with:
    - rules_text injected verbatim
    - Jira ACs
    - worktree path, sandbox port
    - instruction to write output JSON to /tmp/ws_out_{ticket}.json
    [Full sub-agent prompt template — see below]

spawn_reviewing → load rules_text. Fetch PR diff.
    Spawn reviewing sub-agent with rules_text + PR URL + Jira ACs.

## Sub-agent prompt templates

### Implementing
[Keep current template from existing SKILL.md — the ws_enter rules_text replaces the hardcoded rules block]

### Testing
[Keep current template from existing SKILL.md — the ws_enter rules_text replaces the hardcoded rules block]

### Reviewing
[Keep current template from existing SKILL.md]
```

---

## Phase 4 — Smoke Test

1. Start the MCP server: `uv run uvicorn --app-dir .claude/ws mcp_server:app --host 127.0.0.1 --port 8890 --reload`
2. Verify CC picks up the tools (check MCP tool list in CC)
3. Create test workstream: `/ws FD-000` → should call `ws_create`, ask questions
4. Advance through stages: verify `next` field routing at each transition
5. Verify `ws_kanban` renders correctly
6. Write a dummy `/tmp/ws_out_FD-000.json` with missing fields → verify hook fires and blocks

---

## Files to Delete After Phase 4 Passes

- `.claude/ws/orchestrator.py`
- `.claude/ws/registry.json`
- `.claude/ws/rules/implementing.json`
- `.claude/ws/rules/testing.json`
- `.claude/ws/rules/review.json`

Data from the JSON files is migrated to SQLite on first server startup.

---

## Open Questions (resolve before or during build)

1. **HTTP MCP registration format**: verify CC supports `"type": "http"` in `.mcp.json` — check CC docs or test against a simple FastMCP HTTP server first.
2. **uvicorn --reload in production**: `--reload` is a dev flag. For stable daily use, consider a `watchfiles`-based reload wrapper instead so it doesn't reload on unrelated file changes.
3. **Sandbox process ownership**: the MCP server process spawns Flask subprocesses. If the MCP server restarts (due to `--reload`), the Flask processes are orphaned. Need a PID store in SQLite and cleanup on restart.
4. **`familydiagram-testing` replacement**: the workstream server manages `ws_start_sandbox` for btcopilot, but the familydiagram Qt app still needs the testing MCP tools (`launch_app`, `screenshot`, etc.) — those cannot be removed from `.mcp.json` yet. They should eventually be registered dynamically per worktree. Defer to a follow-up.
