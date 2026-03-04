# SDD Industry Landscape (March 2026)

## The SDD Movement

Spec-driven development hit the Thoughtworks Technology Radar in 2025 and received academic formalization in a February 2026 arXiv paper (Piskala, arxiv.org/abs/2602.00180). Core idea: well-crafted specifications as the primary artifact AI agents implement against.

## Fowler's Three-Level Taxonomy

Martin Fowler's team published the most rigorous taxonomy (martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html):

1. **Spec-first**: Specification precedes AI coding; discarded afterward. Essentially detailed prompting.
2. **Spec-anchored**: Specifications persist post-development, guide ongoing evolution. Living documents.
3. **Spec-as-source**: Specifications ARE the primary artifact; humans modify only specs, AI generates code. Code marked `// GENERATED FROM SPEC - DO NOT EDIT`.

Fowler's conclusion: "spec-driven development isn't very well defined yet" — experiencing semantic diffusion. Uses *Verschlimmbesserung* (making worse while trying to improve) to describe risk of current tooling.

## Agent Instruction Surfaces

Three formats have emerged:

| Format | Scope | Key Feature |
|--------|-------|-------------|
| **CLAUDE.md** (Anthropic) | Per-directory hierarchical loading | Best practices: 100-200 lines max, subdirectory overrides |
| **AGENTS.md** (Linux Foundation) | Cross-platform standard, 60,000+ GitHub repos | Supported by Copilot, Codex, Gemini CLI, Cursor, Aider |
| **Cursor Rules** (.cursor/rules/*.mdc) | Glob-scoped per-file rules | Deprecated .cursorrules for individual .mdc files |

Visual Studio Magazine (Feb 2026) crystallized: "In Agentic AI, It's All About the Markdown." Three roles: documentation (explains to humans), instruction (constrains agents), skill (bundles instructions with resources).

## Living Spec Patterns

**Augment Code Intent** — most developed living spec implementation:
- Coordinator agent breaks specs into tasks
- Implementor agents execute in parallel within isolated git worktrees
- Verifier checks results against original spec
- Spec auto-reflects what was actually built

## Critical Voices

Scott Logic's hands-on evaluation of Spec Kit: "a sea of markdown documents, long agent run-times and unexpected friction." Conclusion: "while SDD is an interesting thought experiment, I am not sure it is a practical approach."

Thoughtworks explicitly rejects waterfall equivalence, arguing SDD enables shorter feedback loops.

The Specification Renaissance (Scott Logic, Dec 2025): "AI coding assistants have exposed an uncomfortable truth: many people struggle to articulate what they actually want to build. We've spent decades optimizing for implementation speed whilst specification skills have atrophied."

## Sources

- Thoughtworks Technology Radar: thoughtworks.com/radar/techniques/spec-driven-development
- Thoughtworks blog: thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices
- Fowler taxonomy: martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- GitHub Spec Kit: github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- Piskala 2026: arxiv.org/abs/2602.00180
- VS Magazine: visualstudiomagazine.com/articles/2026/02/24/in-agentic-ai-its-all-about-the-markdown.aspx
- Scott Logic evaluation: blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html
- Scott Logic renaissance: blog.scottlogic.com/2025/12/15/the-specification-renaissance-skills-and-mindset-for-spec-driven-development.html
- Augment Intent: augmentcode.com/product/intent
