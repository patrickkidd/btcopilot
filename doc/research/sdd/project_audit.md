# Project Documentation Audit (March 2026)

Classification of all existing docs against SoR / Process Artifact / Agent Instruction / Reference taxonomy.

## Category A: System of Record (Living)

### Vision Docs
| File | Subsystem | Status |
|------|-----------|--------|
| btcopilot/doc/plans/PATTERN_INTELLIGENCE_VISION.md | Pattern discovery | Deferred post-MVP |
| btcopilot/doc/PLAN_TAB_VISION.md | Plan tab | Deferred post-MVP |
| btcopilot/doc/IRR_STUDY_VISION.md | IRR clinical validation | Deferred post-MVP |

**Missing vision docs**: Extraction pipeline, Personal app overall, Pro app overall, session/sync architecture, training app, synthetic pipeline. Vision-level intent scattered across analyses and decision log entries.

### As-Builts
| File | Subsystem | Status |
|------|-----------|--------|
| familydiagram/doc/asbuilts/TRIANGLE_VIEW.md | Triangle visualization | Current |
| familydiagram/doc/asbuilts/LEARN_VIEW.md | Learn tab clusters/SARF | Current |
| familydiagram/doc/asbuilts/TIMELINE_CLICK_IMPLEMENTED.md | Timeline event selection | Current (minimal) |

**Zero as-builts for btcopilot.** Missing: session/sync, scene system, Flask API, auth, PDP drawer, chat system, synthetic pipeline, training app, QObjectHelper, extraction pipeline, auto-arrange.

### Data Model / API Specs
| File | Subsystem | Status |
|------|-----------|--------|
| btcopilot/doc/specs/DATA_MODEL.md | DiagramData, Person, Event, PairBond, PDPDeltas | Living, well-maintained |
| btcopilot/doc/specs/PDP_DATA_FLOW.md | Extraction pipeline, sparse deltas, apply_deltas | Living, updated 2026-02-26 |
| btcopilot/doc/SARF_GROUND_TRUTH_TECHNICAL.md | GT coding workflow, approval state machine | Living but stale (2025-12-21) |
| btcopilot/doc/F1_METRICS.md | F1 calculation, entity matching | Living, updated 2026-03-03 |
| btcopilot/doc/CHAT_FLOW.md | Chat-only architecture | Current |
| familydiagram/doc/specs/DATA_SYNC_FLOW.md | Five sync functional requirements | Current |

### Developer Guides
| File | Subsystem | Status |
|------|-----------|--------|
| btcopilot/doc/PROMPT_ENGINEERING_LOG.md | Model selection, known issues, lessons | Living, updated 2026-03-03 |
| btcopilot/doc/PROMPT_ENG_EXTRACTION_STRATEGY.md | Extraction prompt strategy | **Living but NOT INDEXED in btcopilot/CLAUDE.md** |

## Category B: Process Artifacts (Frozen)

### Decision Log
- btcopilot/decisions/log.md — Append-only, entries frozen after creation. Key entries: single-prompt pivot (2026-02-24), PairBond first-class (2026-02-14), Patrick sole GT coder (2026-02-24).

### Brainstorming
- btcopilot/doc/brainstorming/2026-02-14-gt_strategy_mvp.md — GT strategy options analysis (resolved by decision log 2026-02-24)
- familydiagram/doc/brainstorming/TIMELINE_VIGNETTES.md — Timeline ideation
- familydiagram/doc/brainstorming/triangle-visualization.md — Triangle view ideation (superseded by as-built)

### Implementation Plans
| File | Status |
|------|--------|
| btcopilot/doc/plans/ADD_NOTES_TO_PDP.md | Deferred post-MVP |
| btcopilot/doc/plans/SYNTHETIC_CLIENT_PERSONALITIES.md | Frozen spec |
| btcopilot/doc/plans/LEARN_TAB_EVALUATION.md | Frozen plan |
| btcopilot/doc/plans/GT_STRATEGY_REALIGNMENT.md | Frozen plan |
| btcopilot/doc/plans/SARF_GRAPH_FOCUSED_MODE.md | Frozen plan |
| btcopilot/doc/plans/REPRODUCTIVE_SCENARIOS.md | Frozen spec |

### Analysis Snapshots (2026-02-20 suite)
All frozen point-in-time assessments:
- 2026-02-20_pdp_extraction_and_delta_acceptance.md
- 2026-02-20_personal_app_beta_readiness.md (40% ready)
- 2026-02-20_auto_arrange.md
- 2026-02-20_diagram_viewing_and_sync.md
- 2026-02-20_server_api_and_data_model.md
- 2026-02-20_synthetic_pipeline.md
- 2026-02-20_bugs_and_todos_inventory.md

### Prompt Engineering Experiment Logs
- btcopilot/doc/induction-reports/2025-12-16_*/ (8+ directories with .md + _log.jsonl)
- btcopilot/doc/induction-reports/2026-03-03_08-20-00--full-extraction/
- btcopilot/doc/log/synthetic-clients/2026-02-18_*.md

### IRR Calibration
- btcopilot/doc/irr/meetings/2026-02-16-sarah-round1-calibration-notes.md
- btcopilot/doc/irr/meetings/2026-02-23-sarah-round1-calibration-meeting2-notes.md

## Category C: Agent Instructions

### CLAUDE.md Files (Index + Rules)
- /Users/patrick/theapp/CLAUDE.md — Project-level routing
- btcopilot/CLAUDE.md — Backend rules, testing, prompt induction protocol
- familydiagram/CLAUDE.md — Qt/QML rules, MCP testing, as-built triggers
- familydiagram/pkdiagram/scene/CLAUDE.md — Scene system architecture rules

### Workflow Protocols
- btcopilot/btcopilot/training/prompts/induction_agent.md — 2600+ line prompt engineering protocol (should be a skill?)
- btcopilot/doc/log/synthetic-clients/README.md — Synthetic client logging rules
- btcopilot/doc/irr/README.md — IRR study workflow
- familydiagram/doc/agents/ui-planner.md — UI prototyping process (mandatory before UI work)

## Category D: Reference / Domain Knowledge (Static)

### Bowen Theory / Clinical
- btcopilot/CONTEXT.md — Domain model overview (delegates to specs)
- btcopilot/doc/specs/BOWEN_THEORY.md — Core constructs, SARF variables, constraints
- btcopilot/doc/specs/PSYCHOLOGICAL_FOUNDATIONS.md — Clinical underpinnings
- btcopilot/doc/sarf-definitions/01-functioning.md through 12-definedself.md — Exhaustive variable definitions
- btcopilot/doc/basic-series/Basic-Series-*.md (7 files) — Bowen theory foundational concepts
- btcopilot/doc/SARF_EXTRACTION_REFERENCE.md — Reference definitions (marked "too verbose for prompts")

### Visual / Design Specs
- btcopilot/doc/FAMILY_DIAGRAM_VISUAL_SPEC.md — SVG rendering spec (Draft v1.0)
- btcopilot/doc/FAMILY_DIAGRAM_LAYOUT_ALGORITHM.md — Layout algorithm
- familydiagram/doc/UI_STYLE_SPEC.md — UI constants, colors, spacing, typography
- btcopilot/doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md — Persona rules (anti-patterns, realism, texture)

### Infrastructure
- familydiagram/doc/INFRASTRUCTURE.md — Build system, deployment
- familydiagram/doc/RELEASE_PROCESS.md — Release workflow
- familydiagram/doc/build-decisions-macos.md, build-decisions-windows.md — Platform build decisions

## Issues Found

### Duplication / Unclear Relationships
- PROMPT_INDUCTION_AUTOMATED.md vs PROMPT_INDUCTION_CLI.md vs induction_agent.md — three similar docs, unclear which is authoritative
- F1_METRICS.md vs F1_DASHBOARD.md — unclear if separate concerns or duplication
- SARF_EXTRACTION_REFERENCE.md vs sarf-definitions/*.md — former marked "too verbose," may be redundant
- PLAN_TAB_VISION.md vs PLAN_TAB_ARCHITECTURE.md — both deferred, should archive

### Missing from Index
- PROMPT_ENG_EXTRACTION_STRATEGY.md is a critical living doc NOT indexed in btcopilot/CLAUDE.md

### Staleness Risk
| Doc | Last Updated | Concern |
|-----|-------------|---------|
| SARF_GROUND_TRUTH_TECHNICAL.md | 2025-12-21 | May be stale after PairBond F1 fixes (2026-03-03) |
| FAMILY_DIAGRAM_VISUAL_SPEC.md | 2024-12-24 | 3+ months old |
| CONTEXT.md | Unknown | Very short, delegates to external docs |

### SoR Content Trapped in Process Artifacts
- Decision log entry about single-prompt pivot (2026-02-24) captures ADR-worthy rationale
- Analysis snapshots contain as-built-worthy content that hasn't been promoted
- Brainstorming docs contain vision-level intent not extracted into vision docs
