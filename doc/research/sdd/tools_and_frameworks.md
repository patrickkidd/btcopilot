# SDD Tools and Frameworks (March 2026)

## Tier 1: Industry-Backed

### Kiro (AWS/Amazon)
- IDE with requirements.md → design.md → tasks.md lifecycle
- Linear, forward-only progression
- No backward reconciliation (no as-built concept)
- GA as of mid-2025
- kiro.dev

### GitHub Spec Kit
- CLI scaffolding for .specify/ directory structure
- Open source (github/spec-kit)
- Lightweight; focused on scaffolding not enforcement

### Augment Code Intent
- Multi-agent workspace with living specs
- Coordinator → Implementor (parallel, isolated worktrees) → Verifier
- Closest to "spec stays in sync with code" vision
- augmentcode.com/product/intent

### Tessl
- Spec-as-source with 10k+ spec registry
- Vision: code is disposable, regenerated from specs
- Most ambitious; full vision still in development
- tessl.io

## Tier 2: Open Source / Community

### BMAD Method (github.com/bmad-code-org/BMAD-METHOD)
- 21 specialized AI agents simulating agile team roles (Analyst, PM, Architect, Developer, QA)
- Maximum depth, enterprise-scale ambition
- Each agent has own instruction set and handoff protocols

### OpenSpec (openspec.dev, github.com/Fission-AI/OpenSpec)
- Delta specs (ADDED, MODIFIED, REMOVED) for brownfield evolution
- Token-efficient; designed for iterative change
- Supports 20+ AI tools via slash commands

### Spec Kitty (github.com/Priivacy-ai/spec-kitty)
- Spec Kit fork with git worktree orchestration
- Built-in parallel feature isolation

### Archgate (archgate.dev)
- Executable ADRs: markdown + TypeScript rule files
- ADRs in .archgate/adrs/ with companion .rules.ts automated checks
- MCP server provides live ADR access to Claude Code, Cursor, etc.
- Ratcheting governance: AI loads ADRs as context → rules catch violations in CI → new patterns become permanent rules
- Apache-2.0 license

### Semcheck (semcheck.ai, github.com/rejot-dev/semcheck/)
- Go CLI using LLMs to verify alignment between code and spec documents
- Pre-commit hooks and CI/CD integration
- Runs checks only for rules with modified files
- Supports OpenAI, Anthropic, Gemini, Cerebras, Ollama

## Tier 3: Standards

| Standard | Adoption | Scope |
|----------|----------|-------|
| AGENTS.md (agents.md) | 60,000+ repos, Linux Foundation | Cross-tool agent instruction format |
| CLAUDE.md | Claude Code ecosystem | Anthropic-specific instruction surface |
| Cursor Rules | Cursor ecosystem | .mdc files with glob scoping |

## Academic

- Piskala 2026 (arxiv.org/abs/2602.00180): Formal taxonomy with case studies
- Griffin & Carroll 2026 (InfoQ): SpecOps framework, five-layer execution model
- Constitutional SDD (arxiv.org/html/2602.02584): Embedding security principles into spec layer
- Astrogator (arxiv.org/abs/2507.13290): Formal specs from NL for LLM output verification
- Dafny DbC (arxiv.org/html/2601.12845): 98.2% correct annotations within 8 repair iterations

## Comparative Analysis

Community research repo comparing 6 tools: github.com/cameronsjo/spec-compare
Deep comparison of BMAD vs spec-kit vs OpenSpec vs PromptX: redreamality.com/blog/-sddbmad-vs-spec-kit-vs-openspec-vs-promptx/

## Key Observation

The governance layer (Archgate, Semcheck, CodeScene MCP) seems more grounded than the generation layer (Kiro, Spec Kit). Enforcement and drift detection are concrete, measurable problems. "Spec generates code" remains aspirational for complex systems.
