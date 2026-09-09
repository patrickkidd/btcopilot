# Isolating the Personal app from the Pro and Training apps

Read-only review of btcopilot PR #136 and fdserver PR #30, 2026-09-08. No code changed.
Question: how to keep daily churn on the chat-first Personal app off the Pro desktop app and
the Training app.

## 1. Touch map — 249 files in btcopilot, 6 in fdserver

| Bucket | Files | What is in it |
|---|---|---|
| web (new browser app) | 114 | 60 source/config, 54 approved screenshots |
| personal-only backend + tests | 67 | 34 live modules, 15 dead ones under `personal/archive/`, 27 tests |
| **shared with Pro** | 29 | list below |
| **shared with Training** | 1 | `training/routes/__init__.py` |
| **schema / public boundary** | 1 | `schema.py` |
| migrations | 7 | section 3 |
| infra/config | 3 | new CI workflow, `.gitignore`, `pyproject.toml` |
| docs and tools | 26 | `doc/chat-first/`, `doc/DRAWABILITY.md`, decision log |

Nine test files moved between buckets, so the counts sum slightly above 249. Shared-with-Pro
by name: `schema.py`, `app.py`, `diagramjson.py` (new), `diagrams/migrate_json.py` (new),
`auth.py` split into an eleven-module `auth/` package, `pro/routes.py`,
`pro/models/{diagram,user,license,preferences}.py`, and eight Pro/schema tests that changed
because the Pro storage format changed. Edges out of Personal: 17 modules import the shared
schema, 7 the Pro diagram model, one each the Pro access-right, preference-key and user
models and the Training metrics module. Edges back in: `pro/routes.py` imports two Personal
modules; ~25 Training modules import Personal models.

## 2. What a Personal-app change can break today, worst first

1. **Every Pro diagram is being rewritten from pickle to JSON in place.** The Pro save path
   converts through a brand-new encoder and a one-shot script converts every existing row. A
   bug in that encoder, written for the chat app, silently damages the only copy of every Pro
   user's family diagram. No migration step, no backup step.
2. **Pro's save endpoint runs Personal code** — it imports the Personal package and writes a
   row to the Personal change table; an exception there fails the desktop save.
3. **The shared schema dropped things the desktop app uses.** The cluster pattern list is
   deleted and the cluster record reshaped; the desktop app imports that list in its cluster
   model and reads a deleted field in its vignette card, and the chat-defaults helper now
   returns two values instead of three. The desktop build breaks on pickup.
4. **Three new columns and a foreign key on the shared users table**, plus new columns on statements and discussions, on the one production database Pro uses.
5. **One migration chain** — a prototype revision cannot be reverted without moving Pro's chain, and a broken one blocks a Pro migration.
6. **Training reads Personal models directly in ~25 modules** — reshaping a statement, discussion or speaker for the chat app breaks Training, with no warning until runtime.
7. **Sign-in became a package and lost the "is this the personal app" check**, changing what the 403 handler does for non-desktop clients.

## 3. Migrations added

| Revision | Tables touched | Read by |
|---|---|---|
| `e1f2a3b4c5d6` | users (preferences, birthdate), discussions (title) | Pro, Training |
| `f1a2b3c4d5e6` | changes, interactions (both new) | Personal only |
| `a3b4c5d6e7f8` | web_sessions, invitations, login_codes (all new) | Personal only |
| `b4c5d6e7f8a9` | statements (views) | Training |
| `c5d6e7f8a9b0` | discussions (title_set_by_user) | Training |
| `d6e7f8a9b0c1` | users (current_diagram_id + foreign key to diagrams) | Pro, Training |
| `e7f8a9b0c1d2` | statements (kind, cluster_id) | Training |

Tests stay under `btcopilot/tests/{personal,pro,schema,training}`; the browser app has its
own unit tests plus 21 screenshot tests with 54 approved images, all run by CI.

## 4. Three ways to isolate

| | A. Package boundary inside btcopilot | B. Own server, own tables | C. Own repository |
|---|---|---|---|
| Shape | Personal owns its routes, models, prompts; one adapter module is the only place touching Pro and the shared schema; a lint rule in CI enforces it | Personal runs as a second service deployed from fdserver with its own tables, sharing only the schema file and the diagram converter | Personal becomes a separate package depending on btcopilot as a library, browser app inside it |
| Cost | 1-2 days, mechanical | 1-2 weeks, plus a ruling on who owns the diagrams table | 2-4 weeks, plus a btcopilot release for every shared change |
| Blast radius | Same database, process and deploy — a bad Personal change can still take the Pro API down | Personal cannot take the Pro API down; a bad migration still can unless the databases split too | Nothing shared but a released library version |
| Does NOT protect | shared tables, the single migration chain, the shared schema file, the diagram storage format | the shared schema file, the diagram converter, and the diagrams table if Personal keeps writing it | the same two, and it slows the daily loop the project exists to run |

## 5. Recommendation

Take A now, after pulling three things out of the Pro app's path. B once the chat app's
shape stops moving; C is the wrong trade while the goal is speed.

1. Restore the deleted cluster pattern list and cluster fields in the shared schema, or land
   the matching desktop change in the same pull request. Rule from here: no symbol the
   desktop app reads changes without its desktop change beside it.
2. Take the Personal import out of `pro/routes.py` — write the change row from a hook the
   Personal package registers, or drop it and derive it from Personal's own reads.
3. Split the pickle-to-JSON storage change into its own pull request with its own migration, a dry run against a copy of production counting conversions and failures, and a way back. It is a Pro storage change, not a chat-app change.
4. Add one adapter module inside Personal as the only importer of Pro models and the shared schema; repoint the ~25 Personal modules at it.
5. Put the Personal-only tables on their own migration branch so a prototype revision never sits in front of a Pro revision, then add the import-linter contract to the existing CI.
6. Freeze the statement, discussion and speaker models for the chat work, or move them somewhere both apps own, before Training breaks silently.

Until those land, prototyping rounds stop: editing anything under `btcopilot/pro/`,
`schema.py` or `btcopilot/auth/` in the same pull request as a chat feature; adding columns
to users, diagrams or statements; changing how a diagram is stored; renaming anything
Training imports. Delete `btcopilot/personal/archive/` — 15 files, no blueprint registers
them, no CI job runs their tests.
