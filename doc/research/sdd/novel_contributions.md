# Novel Contributions: What This Project Does That Nobody Has Named

## 1. SoR vs Process Artifact Distinction with Lifecycle Rules

**Industry state**: No framework distinguishes between living system-of-record docs and frozen process artifacts with explicit lifecycle rules. SDD tools treat all specs as either disposable (spec-first) or permanent (spec-anchored), with no middle ground.

**What this project does**: Explicit taxonomy where:
- SoR docs (vision, ADR, as-built, data model specs) are living — agent must update with every relevant code change
- Process artifacts (brainstorming, decision log entries, analysis snapshots, experiment logs) are frozen after commit
- Agent instructions (CLAUDE.md, workflow protocols) are meta-level — living but governing behavior not describing system

**Why it matters**: Eliminates the "all docs rot equally" problem. Maintenance effort concentrates on SoR docs only. Process artifacts are explicitly disposable context that served their purpose at creation time.

## 2. Promotion Pattern: Process Artifact → SoR

**Industry state**: No formalized pattern for extracting durable knowledge from ephemeral process artifacts into permanent SoR docs.

**What this project does**: Decision log entries contain ADR-worthy rationale. Analysis snapshots contain as-built-worthy content. Brainstorming docs contain vision-level intent. The promotion operation extracts the durable insight and integrates it into the appropriate SoR doc.

**Example**: Decision log entry (2026-02-24) about single-prompt pivot → should become an ADR capturing the architectural rationale, tradeoffs evaluated, and metrics that informed the decision. The decision log entry remains frozen; the ADR becomes the living record.

## 3. Document Lifecycle Progression

**Industry state**: SDD tools have forward-only flows (Kiro: requirements → design → tasks). Construction industry has as-built documentation. Nobody connects the two.

**What this project does**: brainstorming → vision → plan → as-built, where each stage has different properties:
- Brainstorming: frozen snapshots, timestamped, explicitly ephemeral
- Vision: living SoR, captures intent and strategy
- Plan: frozen artifact from implementation phase
- As-built: living SoR, captures what was actually implemented

**Why it matters**: The backward link from "what we built" to "what we intended" enables drift detection. Without as-builts, the only way to know if code matches intent is to read all the code.

## 4. Agent Instruction Surface as Index

**Industry state**: CLAUDE.md, AGENTS.md, Cursor Rules all support hierarchical overrides. None formalize the indexing pattern.

**What this project does**: CLAUDE.md files serve as routers to authoritative docs per domain. The root CLAUDE.md maps to package-level CLAUDE.md files, which map to specific doc files. The instruction surface is a navigation layer, not a content layer.

**Why it matters**: Keeps any single file concise (context window friendly) while maintaining comprehensive coverage. The agent can load the relevant index first, then pull in specific docs as needed.

## 5. Correction-Driven Self-Learning

**Industry state**: No framework formalizes agents updating their own instruction/knowledge files based on user corrections.

**What this project does**: Mandatory correction detection protocol — when user corrects the agent, the agent must update the relevant doc file BEFORE continuing. "Documented in [file] to prevent recurrence."

**Why it matters**: Creates a feedback loop where agent mistakes improve the documentation, which prevents future mistakes. The documentation gets better specifically in the areas where the agent is weakest.

## 6. Workflow-as-Executable-Protocol

**Industry state**: BMAD has 21 specialized agents with role-based workflows. OpenSpec has command-based workflows. Claude Code has skills.

**What this project does**: induction_agent.md is a 2600-line protocol that encodes not just steps but audit trail requirements (mandatory JSONL logging, run folders, final reports, strategy doc updates). The protocol is both instruction and compliance framework.

**Why it matters**: Workflows without audit trails produce knowledge that evaporates. The protocol ensures every prompt engineering experiment is captured, including failures, enabling cumulative learning.
