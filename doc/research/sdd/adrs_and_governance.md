# ADRs and Governance in the AI Era (March 2026)

## ADRs Renewed

Chris Swan (July 2025): ADRs are ideal for AI agents because they provide "enough structure to ensure key points are addressed, but in natural language, which is perfect for things based on Large Language Models."

Prediction: ADRs shift from elite-team practice to standard boilerplate as AI coding becomes dominant, especially for "agent swarms" needing coordination.

## Archgate: Executable ADRs

Most notable tool in this space. Apache-2.0 CLI that pairs ADR markdown with TypeScript rule files:

```
.archgate/adrs/
  001-use-typescript.md
  001-use-typescript.rules.ts  # exports automated checks
```

Creates a ratcheting governance loop:
1. AI agents load ADRs as context before writing code
2. Automated rules catch violations in CI
3. New violation patterns become permanent automated rules
4. MCP server provides live ADR access to editors

## Formal Verification

Academic work advancing on LLM-generated code verification:
- Astrogator: Formal specs from natural language to verify LLM output
- Dafny DbC: Multi-model approaches generate correct annotations (preconditions, postconditions, loop invariants) for 98.2% of programs within 8 repair iterations
- PREFACE: Reinforcement learning guides frozen LLMs toward formally verified Dafny code

## Spec Compliance Checking

**Semcheck** (Go CLI):
- LLMs verify alignment between code and spec documents
- Git pre-commit hooks and CI/CD integration
- Runs checks only for rules with modified files
- Validates documentation against code behavior (addresses doc-sync problem)

## InfoQ's SpecOps Framework

Five-capability model:
1. Spec authoring as primary engineering
2. Formal validation
3. Deterministic generation
4. Continuous conformance monitoring
5. Governed evolution with compatibility control

Five-layer execution: Specification → Generation → Artifact → Validation → Runtime

Treats code as disposable, regenerable artifact within a closed control loop.

## Document Lifecycle Gap

**No widely adopted lifecycle for vision → plan → as-built in software.**

The "as-built" concept remains primarily a construction/architecture industry practice (drawings reflecting what was actually built vs. designed). Software has not adopted this discipline at scale.

SDD tool lifecycles are all forward-only:
- Kiro: requirements.md → design.md → tasks.md
- Spec Kit: spec.md → plan.md → tasks/
- BMAD: Requirements → Architecture → Implementation → QA

None maintain backward-pointing "as-built" records. Augment's Intent auto-updating specs is the closest.

## Sources

- Swan: blog.thestateofme.com/2025/07/10/using-architecture-decision-records-adrs-with-ai-coding-assistants/
- Archgate: archgate.dev, github.com/archgate/cli
- Semcheck: semcheck.ai, github.com/rejot-dev/semcheck/
- InfoQ SpecOps: infoq.com/articles/spec-driven-development/
- Astrogator: arxiv.org/abs/2507.13290
- Dafny DbC: arxiv.org/html/2601.12845
- As-built definition: pagination.com/what-is-as-built-documentation-a-complete-guide/
