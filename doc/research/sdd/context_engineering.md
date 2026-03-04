# Context Engineering Patterns (March 2026)

## The Paradigm Shift

Karpathy (mid-2025): Think of an LLM as a CPU and the context window as RAM. "Context engineering" replaces "prompt engineering" as the consensus term. The art is filling the context window with *just the right information* for the next step.

## Hierarchical Document Loading

Three converging patterns:
- **CLAUDE.md**: Per-directory overrides, nearest file takes precedence
- **Cursor Rules**: .mdc files with glob-scoped applicability
- **AGENTS.md**: Nested files with directory-level specificity

All support hierarchical overrides. None formalize the *indexing* pattern where a root file explicitly maps to authoritative docs per domain (what this project's CLAUDE.md does).

## Summarization Strategies

- **TreeRAG / Hierarchical Summarization** (RAGFlow): LLMs construct tree-like directory summaries (Chapter → Section → Subsection → Key Paragraph). Bridges fine-grained search with coarse-grained reading.
- **Auto-compaction**: Claude Code runs auto-compact at 95% context capacity using recursive summarization. Users can customize: "When compacting, always preserve the full list of modified files."
- **Subagent delegation**: Parallel subagents for research tasks, keeping main context clean.

## CodeScene's Active Feedback Approach

Rather than loading docs into context, expose quality metrics as MCP tools:
- `code_health_review` — snippet-level during generation
- `pre_commit_code_health_safeguard` — staged files
- `analyze_change_set` — full branch comparison

Converts passive documentation into active feedback loops.

## Addy Osmani's Spec Structure (O'Reilly, Jan 2026)

Recommended spec structure for AI agents:
1. Commands
2. Testing
3. Project structure
4. Code style
5. Git workflow
6. Boundaries (three-tier: Always / Ask First / Never)

Key insights:
- "The curse of instructions" — model performance drops as simultaneous directives increase
- "LLM-as-a-Judge" for subjective quality criteria
- YAML-based conformance suites as machine-checkable contracts

## Skills / Workflows as Code

### Claude Code Skills (early 2026)
- Slash commands and skills merged: `.claude/commands/review.md` and `.claude/skills/review/SKILL.md` both create `/review`
- Automatic invocation (Claude loads when relevant) vs. manual-only (`disable-model-invocation: true`)
- Side-effect control for dangerous operations
- Subagent parallelization (3 agents analyzing 50k lines in ~45s vs 3min sequential)
- MCP integration with 200+ community servers

### BMAD's Multi-Agent Approach
21 specialized agents embodying role-based workflows. Each has own instruction set and handoff protocols — encoding agile team workflow as executable agent config.

### OpenSpec's Artifact-Guided Workflow
Command-based: `/opsx:propose` → explore → apply → archive. Delta specs for brownfield.

## Sources

- Karpathy: x.com/karpathy/status/1937902205765607626
- Prompting Guide: promptingguide.ai/guides/context-engineering-guide
- CodeScene: codescene.com/blog/agentic-ai-coding-best-practice-patterns-for-speed-with-quality
- Osmani: addyosmani.com/blog/good-spec/
- Claude Code skills: code.claude.com/docs/en/skills
- Claude Code best practices: code.claude.com/docs/en/best-practices
- RAGFlow TreeRAG: ragflow.io/blog/rag-review-2025-from-rag-to-context
- Skills merge: medium.com/@joe.njenga/claude-code-merges-slash-commands-into-skills-dont-miss-your-update-8296f3989697
- Claude Code customization: alexop.dev/posts/claude-code-customization-guide-claudemd-skills-subagents/
