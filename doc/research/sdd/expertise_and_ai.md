# Software Engineering Expertise and AI Collaboration (March 2026)

## Competency Frameworks

### SFIA (Skills Framework for the Information Age)
Globally accepted standard. Version 9 (late 2024). Seven levels of responsibility along five attributes: Autonomy, Influence, Complexity, Knowledge, Business Skills. SFIA has published guidance on using its levels to analyze which tasks to assign to AI. sfia-online.org

### IEEE/ACM SWECOM
Software Engineering Competency Model incorporating SWEBOK v3, SE2014 curriculum, ISO/IEC/IEEE 12207. Defines skill areas, skills, and activities. SFIA has published a mapping between SFIA 8 and SWEBOK v3.

### Dreyfus Model of Skill Acquisition (1980)
Five stages (later six):

1. **Novice**: Context-free rules, step-by-step. Cannot exercise judgment.
2. **Advanced Beginner**: Applies rules to real situations. Recognizes situational elements but cannot prioritize.
3. **Competent**: Plans, sets goals. Conscious deliberation. Accepts responsibility.
4. **Proficient**: Intuitively grasps situation, consciously decides responses. Sees whole picture. Recognizes deviations before explicit indicators.
5. **Expert**: Acts intuitively without reflective decision-making. "When things are proceeding normally, experts don't solve problems and don't make decisions; they do what normally works."
6. **Mastery**: Highly motivated performers pushing beyond expertise.

Critical insight: **to advance to proficiency and expertise, the learner must let go of rule application.** Intuition is not guesswork — it is the effortless recognition of similarity to past patterns of experience. Expertise is skill-specific, not general.

### FAANG Engineering Levels
| Level | Key Differentiator |
|-------|--------------------|
| Entry (L3/E3) | Algorithms and coding ability. Needs guidance. |
| Mid (L4/E4) | Handles scope with less guidance. 1-5 yrs. |
| Senior (L5/E5) | **System design weighted heavily.** Operates independently. Most engineers plateau here. |
| Staff (L6/E6) | Cross-team/org influence. Solves extremely complex, ambiguous problems. Go-to architect. |
| Senior Staff (L7) | Rare. Counsels VPs. Owns multiple large systems. Impacts 50-100+ engineers. |

L4→L5 transition: "can I write correct code" → "can I design systems."
L5→L6 transition: "can I solve hard problems" → "can I identify which problems matter."

### Li et al. (2015) — "What Makes A Great Software Engineer?"
Microsoft Research, 59 experienced engineers, 13 divisions, 54 attributes identified. Great engineers: develop practical decision-making models from theory + experience, produce elegant software that anticipates needs, evaluate tradeoffs at multiple abstraction levels. faculty.washington.edu/ajko/papers/Li2015GreatEngineers.pdf

## Expertise Markers

### Pattern Recognition vs Rule Following
Cognitive psychology consistently shows pattern recognition is the foundation of expert performance. Fagerholm et al. (2022): comprehensive taxonomy of 311 papers found expertise fundamentally changes the cognitive processes involved in SE work.

### Cognitive Load and Chunking
Experts form schemas (chunks of related info in long-term memory). Each schema occupies one working memory slot even if it contains many pieces. Working memory holds ~4-7 chunks. Novice sees dozens of components; expert sees "event-driven pub/sub with CQRS" — one chunk — and immediately reasons about its properties and failure modes.

### When Experts Break Rules
Dreyfus model explicitly: advancement to proficiency requires abandoning rule-following. Not recklessness — result of internalizing enough experience to recognize when general rules don't apply to specific situations. Novice follows "always use ORM" as a rule. Expert knows when raw SQL is correct because they recognize specific characteristics making ORM counterproductive.

### Negative Expertise: Knowing What NOT To Do
Minsky (1994): "Expertise requires knowing what one must do, but also knowing what not to do. Much of human knowledge is negative."

Critical problem: **negative knowledge never appears in behavior.** Cannot observe what someone chose not to do. Expert value often lies in disasters prevented, architectures rejected, "clever" solutions refused — none appear in commit logs or metrics.

"The rise of AI commoditizes some skills while increasing value for others — knowing how to align a div decreases in value but knowing how to design and orchestrate data at scale safely increases in value." (Abstraction Capital)

## Architecture Expertise Specifically

### Expert Intuition in Architecture
Pretorius et al. (2024): systematic review, 26 studies from 3,909. Software designers switch between intuition and rationality, use both in parallel. When using intuition, designers perform situation assessment and recognition of satisfactory option based on tacit knowledge, unable to provide explicit rationale. Evidence from other fields shows intuition holds benefits for complex design decisions.

### ATAM (Architecture Tradeoff Analysis Method)
What distinguishes expert architects from competent ones:
- Systematically identify **sensitivity points** (small changes → large quality consequences)
- Identify **trade-off points** (decisions affecting multiple quality attributes)
- Distinguish **risks from non-risks** with high accuracy
- Understand business ramifications, not just technical

Neal Ford / Mark Richards: expert response to architecture questions is "It depends" — not evasiveness but genuine expertise understanding context determines correctness.

### Risk Assessment Scoping
Expert knows where risk concentrates (integration points, data consistency boundaries, authorization model). Does not waste review time on low-risk areas (static config, simple CRUD). Pattern recognition applied to code review triage.

## Expertise and AI Collaboration

### The Experience Asymmetry

**METR RCT (July 2025)**: 16 experienced open-source developers (5+ years on their repos, 22k+ stars, 1M+ LOC). AI-allowed developers were **19% slower.** Developers themselves estimated they were 20% faster — significant perception-reality gap. arxiv.org/abs/2507.09089

**Google internal RCT (2024)**: ~96 engineers, enterprise-grade task (10 files, ~474 LOC). AI group **21% faster.** But more constrained, well-defined task than METR.

**Multi-company RCT (Microsoft, Accenture, Fortune 100)**: ~5,000 developers. Average 26% productivity increase. **Newer developers: 35-39% speed-up. Seasoned developers: 8-16%.**

Pattern: AI helps most when developer lacks knowledge AI provides, helps least when developer already has it and AI introduces coordination overhead.

### The Specification Skill Argument
Scott Logic: "The developers who thrive in the AI era won't be those with the cleverest prompts. They'll be those who can think clearly, specify precisely, and verify thoroughly."

Including architectural context in prompts improved code generation accuracy from **30% usable to 85% production-ready** (Augment Code data).

Experts extract dramatically better AI output because they specify:
- Precise acceptance criteria
- Architectural constraints (patterns to follow AND avoid)
- Edge cases and failure modes (negative specification)
- Integration contracts and invariants

### AI Amplifying Novice Mistakes
CodeRabbit (Dec 2025, 470 real PRs): AI-generated code produces **1.7x more issues** (10.83 vs 6.45 per PR). 1.75x more logic errors, 1.64x more maintainability errors, 1.57x more security findings, 8x more excessive I/O.

GitHub Copilot: ~40% of generated code was vulnerable. 25.9% of 452 snippets had security weaknesses across 43 CWE categories.

Amplification mechanism: junior developers trust AI over own intuition because they lack foundational skills to evaluate output. 14/15 juniors described AI as helpful — highest satisfaction, least equipped to catch errors.

### The Perception Gap
2025 Stack Overflow: 46% don't trust AI accuracy (up from 31%). 66% report "almost right but not quite." 45% said debugging AI code is more work than worth.

JetBrains 2025 (24,534 respondents): 85% use AI regularly. Top concerns: code quality (23%), limited understanding of complex code (18%), negative effect on coding skills (11%).

## The "10x Engineer" in the AI Era

### The Productivity Paradox
Faros AI: 10,000+ developers, 1,255 teams. High AI adoption: 21% more tasks, 98% more PRs. **But PR review time increases 91%.** Correlation between AI adoption and performance evaporates at company level. Gains neutralized by review bottlenecks, brittle testing, slow pipelines (Amdahl's Law).

### What "10x" Means Now
1. **AI compresses the implementation gap.** Speed variance between novice and expert narrows with AI assistance.
2. **AI widens the judgment gap.** Knowing *what* to build, *what NOT* to build, *how to validate* becomes relatively more valuable.
3. **AI creates new failure modes.** Expert ability to catch AI-introduced defects becomes a new 10x multiplier.
4. **Bottleneck shifts upstream and downstream.** 91% review time increase means effective review is the constraint. Requires pattern recognition, negative knowledge, architectural judgment — expert work.

### The Uncomfortable Conclusion
If negative expertise never appears in behavior, and AI's primary measurable effect is on behavior (code output velocity), then **AI productivity metrics systematically fail to capture the dimension of expertise that matters most.**

## Sources
- SFIA: sfia-online.org/en/about-sfia/how-sfia-works
- SFIA AI guidance: sfia-online.org/en/tools-and-resources/ai-skills-framework/
- IEEE SWECOM: ieeecs-media.computer.org/media/education/swebok/swecom.pdf
- Dreyfus model: leadingsapiens.com/dreyfus-model/
- Rousse & Dreyfus: philarchive.org/archive/ROURTS
- FAANG levels: tryapt.ai/blog/faang-levels-explained-google-meta-amazon
- Li et al.: faculty.washington.edu/ajko/papers/Li2015GreatEngineers.pdf
- Fagerholm et al. 2022: dl.acm.org/doi/full/10.1145/3508359
- Cognitive Load in SE: kleinnerfarias.github.io/pdf/articles/icpc-2019.pdf
- NSF engineering intuition: par.nsf.gov/servlets/purl/10191028
- Minsky negative expertise: abstraction.vc/blog/vibecoding-negative-expertise-and-the-future-of-engineering/
- Pretorius et al. 2024: onlinelibrary.wiley.com/doi/full/10.1002/smr.2664
- ATAM: arxiv.org/html/2505.00688v1
- METR RCT: arxiv.org/abs/2507.09089, metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
- Google RCT: arxiv.org/html/2410.12944v2
- Multi-company RCT: addyo.substack.com/p/the-reality-of-ai-assisted-software
- CodeRabbit: coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report
- Copilot security: cyber.nyu.edu/2021/10/15/ccs-researchers-find-github-copilot-generates-vulnerable-code-40-of-the-time/
- Stack Overflow 2025: survey.stackoverflow.co/2025/
- JetBrains 2025: blog.jetbrains.com/research/2025/10/state-of-developer-ecosystem-2025/
- Faros AI: faros.ai/blog/ai-software-engineering
- Scott Logic: blog.scottlogic.com/2025/12/15/the-specification-renaissance-skills-and-mindset-for-spec-driven-development.html
- Augment Code spec prompting: augmentcode.com/guides/spec-driven-prompt-engineering-for-developers
