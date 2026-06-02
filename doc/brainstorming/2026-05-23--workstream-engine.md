# Workstream Engine — Vision & Architecture Brainstorm
*Started 2026-05-23. Captures everything from the workstream management session.*

---

## The Core Problem

Parallel AI coding workstreams need:
1. **Isolation** — each session, worktree, server, DB, and fixture set is truly independent
2. **Determinism** — stage transitions, rule enforcement, and output validation are code-enforced, not instruction-dependent
3. **Visibility** — a single UI showing all active workstreams, their stage, metadata, and story arc
4. **Self-improvement that scales** — corrections accumulate in structured, prunable rules, not append-only markdown
5. **Narrow inference** — AI does only what requires judgment; everything mechanical is code

The recurring failure mode: every enforcement path currently bottoms out in "Claude reads this instruction and decides to follow it." That's probabilistic all the way down.

---

## The Ideal (walk backward from this)

### The UI Patrick Wants

A **colored stage indicator** in the CC session UI (e.g. status line or plugin panel). Click it → metadata panel for the current workstream showing:

**Brainstorming/Planning**
- Acceptance criteria on the table
- Open questions
- Tentative plan
- Risks / blockers / blast radius of the tentative plan
- State files stored in repo (timestamped, e.g. `btcopilot/doc/plans/2026-05-23--FD-NNN/`)
- Output artifact: Jira ticket

**Implementation**
- Autonomous agentic black box (minimal human interaction is the goal)
- TODO burn-down status
- Blockers to autonomous running + measurement of long-horizon runability
- Wall-clock ETA with telemetry feedback loop (estimates must improve over time — current estimations are terrible)
- Worktree locations on disk; guarantee origin clones are untouched
- Agent-predicted failure modes (FMs) from scanning code diff
- Output artifact: PR(s)

**Testing**
- **Isolation proof**: where worktrees live, where sandboxed folders live, how dev servers are guaranteed untouched, how fixture data generation is comprehensive and methodology is sound
  - PDP card changes → complete sandboxed mock diagram file with comprehensive people, events, PDP deltas
  - UI state mgmt (open/reopen diagram) → sandboxed user account created from scratch with necessary diagram files
  - These isolation + fixture rules are critical to success
- Human script in Arrange/Act/Assert format (≤7 items)
- Human-discovered FMs (failure modes) filed as child Jira tickets
- Validation status per bug: agentic-verified vs. human-verified (human is final gate)
- Grind session steering: how the current agent is burning down remaining bugs while human walks the script simultaneously
- Output artifact: test log + verified bug list

**Review**
- PR diff summary
- Acceptance criteria coverage check
- Blocking vs. non-blocking issues
- Output artifact: approved PR

---

## The Determinism Gap (current state)

```
┌─────────────────────────────────────────────────────┐
│  TIER 1: CLAUDE'S BEHAVIOR  (probabilistic)          │
│                                                      │
│  CLAUDE.md          — domain knowledge               │
│  SKILL.md           — routing logic + stage flow     │
│  rules/*.json       — injected into sub-agent prompt │
│                                                      │
│  All text Claude reads and may or may not follow.    │
└──────────────────────────┬──────────────────────────┘
                           │ Claude decides to call
┌──────────────────────────▼──────────────────────────┐
│  TIER 2: ORCHESTRATOR.PY  (deterministic)            │
│                                                      │
│  State machine      — registry.json reads/writes     │
│  validate()         — schema checks on JSON output   │
│  start-sandbox()    — actually starts the server     │
│  kanban()           — renders state                  │
│                                                      │
│  Real code, but only runs if Claude calls it.        │
└─────────────────────────────────────────────────────┘
```

**Root cause:** Tier 2 is only as reliable as Tier 1 decides to invoke it. The skill says "call validate after sub-agent returns" — but that's markdown. Nothing forces it.

**What would fix it:** move invocation out of Claude's discretion into the harness (hooks or MCP server).

---

## Rules Enforcement Gap

Currently:
- Rule text in JSON → injected into sub-agent prompt (probabilistic)
- Validator checks known output fields in hardcoded Python (deterministic if called)
- No automatic connection between a rule and its validator check
- Adding a rule to JSON does nothing to validation without a paired Python change

Better design: **self-describing rules with a `check` field**:
```json
{
  "id": "T002",
  "category": "human_script",
  "rule": "Each step must have arrange, act, assert keys",
  "check": {"path": "human_script[*]", "required_keys": ["arrange", "act", "assert"]}
}
```
Validator reads rules JSON and runs checks automatically. Adding a rule with a `check` field automatically enforces it.

Still probabilistic: rules that can't be expressed as output JSON properties (e.g. "use realistic fixture names").

---

## Architecture Options (walking backward from the ideal)

### Option A: MCP Server (strongest determinism)

A custom MCP server that wraps entire stage lifecycles:

```
Claude calls: ws_run_stage(ticket="FD-NNN", stage="testing")

MCP server:
  1. Reads registry (deterministic)
  2. Starts sandbox server (deterministic)
  3. Spawns sub-agent via CC Agent SDK (deterministic spawn)
  4. Validates sub-agent JSON output against schema (deterministic)
  5. Retries sub-agent if validation fails (deterministic)
  6. Returns validated result to Claude only when PASS (deterministic)

Claude's only job: call the tool, present result to user.
```

Claude never sees intermediate steps. True encapsulation. The MCP server is the enforcement layer.

**Tools exposed:**
- `ws_create(ticket, repos, summary)` → creates workstream in registry
- `ws_status(ticket?)` → rich markdown panel or kanban
- `ws_run_stage(ticket, stage?)` → runs current/specified stage end-to-end
- `ws_advance(ticket)` → transitions to next stage
- `ws_add_rule(stage, category, rule, check?)` → adds rule + optional validator
- `ws_update(ticket, field, value)` → updates workstream metadata
- `ws_log_fm(ticket, description, severity, verified_by)` → log a failure mode

**What this buys:**
- Skill becomes 20 lines: "call ws_run_stage, present result"
- All enforcement is in server code
- Rules with `check` fields auto-validate
- No CC restart to update business logic (just restart MCP server process)
- Telemetry hooks naturally (timestamp every transition in SQLite)

**What it costs:**
- Real build: ~1-2 weeks for MVP
- MCP server process to manage
- CC restart needed to pick up tool definition changes (not logic changes)

### Option B: PostToolUse Hook (partial determinism)

A hook fires when sub-agent writes output file → runs validator → blocks Claude if FAIL.

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.file_path' | grep -q 'ws_out_' && python .claude/ws/orchestrator.py validate-from-path $(jq -r '.tool_input.file_path') || true"
      }]
    }]
  }
}
```

Partial: enforces validation automatically when output file is written, but sub-agent still has to write to the right path.

### Option C: CC Plugin (status line + MCP bundled)

A CC plugin that provides:
- MCP server (all tools above)
- Status line command showing `[FD-340 | testing | 2 blockers]`
- Skills (thin wrappers calling MCP tools)

This is the full solution bundled. Plugin can be published, used at Micron.

**Status line limitation:** text only, not a clickable button. But persistent and visible. Could show: `● FD-340 testing | 2 blockers | ETA ~40min`.

**For interactive panel:** companion web server (served by MCP server on localhost) opened via a skill. `/ws FD-340` → opens `http://localhost:PORT/ws/FD-340` in browser showing full metadata panel.

### Option D: Temporal / Durable Execution (long-horizon runability)

For the "wall-clock ETA" and "long-horizon autonomous running" requirements, Temporal provides:
- Every state transition recorded as an event (perfect audit trail)
- Workflows survive process crashes, restarts, network failures
- Human-in-the-loop approval gates as first-class concept
- Fan-out to parallel sub-agents, reconverge
- ETA estimation from historical workflow durations

This is used by OpenAI Codex in production for the same reasons. Overkill for single-project use; exactly right for "day job at Micron" scale.

---

## Telemetry & ETA

Current estimations are poor because there's no historical data. Fix:

Every stage transition → write to `registry.json`:
```json
{
  "FD-340": {
    "stage_history": [
      {"stage": "planning", "entered": "2026-05-20T10:00:00", "exited": "2026-05-20T10:30:00"},
      {"stage": "implementing", "entered": "2026-05-20T10:30:00", "exited": "2026-05-21T14:00:00"},
      {"stage": "testing", "entered": "2026-05-21T14:00:00", "exited": null}
    ]
  }
}
```

After N workstreams, a simple regression gives per-stage median durations. Show as ETA in status line. Improve over time. Can segment by: repos in scope, number of ACs, LOC changed.

---

## Isolation Guarantees (testing stage)

Must be provable, not asserted. For each test run:

| Concern | Guarantee mechanism |
|---------|-------------------|
| Origin clones untouched | `git -C ~/theapp/<repo> status` must be clean; enforced by validator |
| Worktree isolated | TestInstance imports from worktree path in registry, not global |
| Sandbox server isolated | Ephemeral Flask + SQLite on dynamic port (ephemeral_server=True) |
| Fixture data complete | Schema-driven fixture generator per test scenario type |
| No cross-contamination | `close_all_instances()` before every launch |

**Fixture generation methodology** (per scenario type):
- PDP card changes → generate complete diagram: ≥3 people, ≥2 pair bonds, ≥1 shift event, all PDP card types (add, edit, delete, pair bond event, shift), edge cases (name+gender change simultaneously, delete person who is also in a pair bond being edited)
- UI state mgmt flows → fresh user account + diagram(s) with specific structural properties the flow requires
- These generators should be code, not ad-hoc per-test fixture construction

---

## Self-Improvement Architecture

**Current (broken):** append-only Known Corrections in skill markdown → grows forever, never pruned, probabilistically read

**Target:**
```
rules/<stage>.json          — machine-readable, prunable
  rule.id                   — addressable
  rule.category             — groupable
  rule.rule                 — text for LLM prompt injection
  rule.check (optional)     — JSON schema for automatic validation
  rule.added                — datestamp
  rule.supersedes (optional) — ID of rule this replaces
```

When Patrick corrects:
1. MCP server or orchestrator calls `add_rule(stage, category, text, check?)`
2. If it supersedes an old rule, marks the old one and optionally removes it
3. No skill file changes. Ever.

Rules that can't be expressed as `check` schemas remain probabilistic but are at least organized, addressable, and prunable.

---

## What Stays Probabilistic (honest ceiling)

Even with MCP server + self-describing rules:
- Whether fixture *content* is semantically correct (realistic names, right edge cases)
- Whether the sub-agent's reasoning about code changes is sound
- Whether "blast radius" assessment is accurate
- Anything that requires domain judgment

The goal is: **push everything mechanical to code, leave only judgment to the LLM.**

---

## Possible Products

1. **Open-source CC plugin** — workstream engine for CC users, published to marketplace
2. **MCP server library** — `workstream-mcp`, usable by any CC/Cursor/Copilot installation
3. **Micron internal tool** — same architecture, enterprise deployment via managed settings
4. **Temporal-backed SaaS** — multi-user workstream orchestration with durable execution, web dashboard, team kanban

The MCP server approach generalizes. The rules schema, stage machine, and isolation guarantees are project-agnostic. The project-specific knowledge lives in `rules/*.json` and `CLAUDE.md` — swappable per project.

---

## Open Questions

- Can CC plugin status line render colored text / icons? (need to test)
- Can a CC plugin open a browser tab / serve a web UI? (likely via MCP tool)
- Is Temporal worth the operational overhead for single-developer use, or only at Micron scale?
- Should fixture generators be part of the MCP server, or project-specific scripts the MCP server calls?
- How do we handle the case where a sub-agent needs human input mid-stage? (Temporal has this natively; MCP server needs a polling/notification pattern)
- What's the right granularity for telemetry — per-stage, per-AC, per-file-changed?

---

## Current Implementation (as of 2026-05-23)

Built so far:
- `~/theapp/.claude/ws/orchestrator.py` — state machine, rules CRUD, validation, sandbox mgmt, kanban
- `~/theapp/.claude/ws/registry.json` — workstream state store
- `~/theapp/.claude/ws/rules/{implementing,testing,review}.json` — structured rules migrated from old skills
- `~/theapp/.claude/skills/workstream/SKILL.md` + `ws/SKILL.md` — thin routing skill, zero domain knowledge

Gap: skill invokes orchestrator probabilistically. Next step: MCP server wraps stage lifecycle so Claude calls one tool per stage.

---

## Session 2 Decisions (2026-05-23 continuation)

These decisions were locked in before the build started. Rationale for each is below.

### The `next` Field Pattern

Every MCP tool response includes a `next` field — a hardcoded Python string that tells the top-level agent what to do next. This is the key mechanism for keeping the skill file small and keeping routing deterministic.

The `next` field is NOT LLM-generated. It is a Python constant returned by the state machine based on current workstream state. Examples:
- ticket not found → `"not_found: call ws_create(), then ask Patrick in ONE message: repos, schema changes, constraints, test hardware"`
- implementing, no PRs → `"spawn_implementing: use rules_text and prompt template from skill, spawn implementing sub-agent"`
- testing, sandbox not started → `"start_sandbox: call ws_start_sandbox(ticket), then spawn_testing"`

This collapses the skill file to ~40 lines regardless of rule accumulation. The skill reads `next` and follows it. No routing logic lives in the skill.

### Top-Level Agent Is Not a Dumb Router

The frontier model has two jobs:
1. **Workflow navigation** (low intelligence): read the `next` field, follow it
2. **Context synthesis** (frontier-level): read Patrick's complaint + Jira ACs + git diff → construct a precise sub-agent prompt

The MCP server offloads #1 so the frontier model focuses on #2. This is the correct division of labor. The MCP server provides structured ingredients (state, rules text); the frontier model provides synthesis (what to fix, which ACs need special attention, what the diff is doing).

The "prompt skeleton" anti-pattern: early design had the MCP server returning a `prompt_skeleton` with gaps for the frontier model to fill. This was dropped. The MCP server returns data only. The skill owns the prompt shape. There is no prompt construction in the MCP server.

### HTTP Over stdio

stdio forces a CC window restart for every server code change. HTTP (SSE transport via FastMCP) allows:
- Code change → kill + restart just the server process
- `uvicorn --reload` detects file changes and hot-reloads automatically
- CC session stays live throughout

Tool definition changes (adding/removing tools) still require CC restart since CC caches the tool list at connect time. But tool definitions will be stable after initial build.

Implementation: `FastMCP.sse_app()` returns a Starlette app. Run via `uvicorn mcp_server:app --reload`. Server exposed at `http://127.0.0.1:8890/sse`.

### SQLite Over JSON Files

`registry.json` and `rules/*.json` are replaced by a single SQLite DB at `.claude/ws/ws.db`. Rationale:
- Persists across CC sessions and CC window restarts
- Cross-workstream queries natural (kanban, telemetry, ETA regression)
- Rules CRUD is atomic (no partial-write corruption)
- Stage history and telemetry are proper relational data, not embedded JSON arrays
- Sandbox PID tracking survives uvicorn --reload cycles

On first startup, the server seeds rules from the existing JSON files if the `rules` table is empty.

### Self-Learning Is Always Hot

`ws_add_rule` writes to the `rules` table immediately. `ws_enter` reads from the DB on every call — no in-memory cache of rules. New rule is in the next sub-agent prompt in the same CC session, no restart needed.

This is the correct flow:
1. Patrick corrects something
2. Top-level agent calls `ws_add_rule(stage, category, rule)`
3. DB updated immediately
4. Next `ws_enter` call returns `rules_text` including the new rule
5. Next sub-agent spawn gets it in its prompt

Changes to the server's own Python logic (state machine, validation code) require a server restart — with `uvicorn --reload`, that's automatic on file save.

### Dynamic Sandbox Management

The fixed `.mcp.json` entries for `btcopilot-flask` and `familydiagram-testing` are artifacts of the single-workstream era. The workstream MCP server replaces `btcopilot-flask` by managing sandbox Flask processes dynamically per ticket:
- `ws_start_sandbox(ticket)` looks up the worktree from SQLite and starts an isolated Flask process on a dynamic port
- Multiple concurrent workstreams each get their own sandboxed port
- Sandbox PIDs stored in SQLite so they survive server restarts

`familydiagram-testing` is deferred: the Qt app testing tools are still needed and can't be replaced dynamically yet. That entry stays in `.mcp.json` for now, but its path should be updated to point to the correct worktree per active workstream. Full dynamic management of familydiagram-testing is a follow-up.

### The Narrowed Probabilistic Seam

The only remaining instruction-dependent step is: "write your JSON output to `/tmp/ws_out_FD-NNN.json`." This is a much narrower seam than injecting 18 rules as prose.

The PostToolUse hook on `Write` fires deterministically when that file is written. The hook calls `ws_validate` via HTTP. If validation fails, the hook returns `{"continue": false, "stopReason": "..."}` — harness-level enforcement, not instruction-level.

The hook is implemented as a thin script `validate_hook.py` (not inline shell) that reads stdin, extracts the file path, checks if it matches `ws_out_FD-*.json`, calls `ws_validate`, and either exits 0 (pass) or prints the JSON stop payload and exits 1 (fail).
