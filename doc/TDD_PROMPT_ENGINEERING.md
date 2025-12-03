# Test-Driven Prompt Development

Best practices for improving complex system prompts without introducing regressions.

## The Core Problem

Complex system prompts face similar challenges to large codebases:
- Changes in one section can affect behavior elsewhere
- Lack of isolation between behavioral rules
- No explicit interfaces between prompt sections
- Difficult to predict side effects of edits

Unlike code, prompts lack modular architecture where components have clear boundaries and explicit interfaces. Every instruction potentially affects the entire response space.

## Test-Driven Prompt Development

Create a prompt test suite similar to code tests:

**Document specific behavioral scenarios** with expected outcomes:
- Keep examples of good/bad responses for critical interactions
- Version control your prompt changes
- Test critical behaviors after each modification

**Suggested structure**:
```
btcopilot/doc/prompts/
├── system_prompt.md          # The actual prompt
├── test_scenarios.md         # Expected behaviors
└── regression_tests.md       # Known failure cases to avoid
```

**Test scenarios should cover**:
- Greeting and session initiation
- Assessment phase transitions
- Intervention delivery patterns
- Crisis/safety responses
- Session resumption after interruption
- Edge cases and boundary conditions

## Modular Prompt Architecture

Break monolithic prompts into sections with clear boundaries:

**Section organization**:
- Each section handles one behavioral domain
- Use clear section headers
- Document dependencies between sections
- Make changes to isolated sections when possible

**Example structure for therapeutic chat**:
1. Role & Tone
2. Session Management (greeting, resuming)
3. Assessment Phase Rules
4. Intervention Phase Rules
5. Safety & Ethics
6. Technical Constraints

**For each section, document**:
- **What**: The behavior it controls
- **Why**: The reasoning/constraints driving it
- **Dependencies**: What other sections it interacts with
- **Examples**: Sample inputs/outputs

## Version Control with Semantic Commits

Track prompt changes like code:
- One change per commit with clear description
- Tag versions before major changes
- Document what behavior changed and why
- Keep a CHANGELOG.md for the prompt

**Example commit messages**:
```
feat(assessment): Add emotional acknowledgment before questions

fix(session): Check for interrupted assessments on resume

refactor(intervention): Simplify language in delivery rules

docs(safety): Clarify crisis protocol escalation
```

## Constraint-Based Editing

When requesting changes from Claude Code or other AI assistants:

❌ **Vague**: "Make the bot more empathetic"
✅ **Specific**: "In the assessment phase only, when user shares emotional content, add acknowledgment before proceeding to next question. Don't change intervention phase behavior."

❌ **Broad**: "Fix the session resumption logic"
✅ **Targeted**: "Modify lines 45-62 (session resumption section) to check for interrupted assessments. Leave the new session greeting unchanged."

**Key principles**:
- Reference specific line numbers or section names
- Limit scope to one behavioral domain
- Specify what should NOT change
- Provide concrete examples of desired behavior

## Behavioral Anchors

Establish non-negotiable behaviors that should never change:
- Safety protocols
- Core clinical model adherence
- Privacy/confidentiality rules
- Crisis response patterns

**Document these as "invariants"** that should be preserved across all edits. Include them in a dedicated section or separate file that editors review before making changes.

## Prompt Diff Reviews

Before deploying prompt changes:
1. Generate a diff of the old vs new prompt
2. Review each changed line for potential side effects
3. Ask: "What other behaviors might this phrasing affect?"
4. Test with edge cases that might expose interactions
5. Check for conflicts with documented invariants

**Side effect checklist**:
- Does this change tone or formality level?
- Could this affect session state transitions?
- Does this introduce ambiguity with existing rules?
- Are there conditional statements that might now conflict?

## Progressive Refinement

Avoid big-bang rewrites:
- Make small, incremental changes
- Test each change in isolation
- Build up complex behaviors from simple primitives
- Roll back immediately if regressions appear

**Incremental change workflow**:
1. Identify smallest atomic change
2. Make the change
3. Test critical paths
4. Commit if successful, revert if not
5. Repeat for next change

## Mitigation Strategies

Since prompts lack isolation and explicit interfaces:

**1. Explicit prioritization**:
```
Rule X overrides Rule Y when in conflict.
Safety protocols take precedence over engagement goals.
```

**2. Conditional scoping**:
```
Only during assessment phase: [rules]
When user indicates crisis: [override all other rules]
```

**3. Concrete examples**:
Show don't tell for complex behaviors. Include example conversations inline.

**4. Negative examples**:
```
Never do X, even when Y.
Don't ask follow-up questions during intervention delivery.
```

**5. State-based rules**:
Make behavioral rules conditional on explicit session state rather than implicit context.

## A/B Testing Framework

For significant changes:
1. Run both old and new prompts in parallel
2. Compare outputs on standardized test cases
3. Measure specific behavioral metrics
4. Only switch if improvement is clear

**Metrics to track**:
- Session completion rate
- User satisfaction indicators
- Clinical model adherence
- Safety protocol compliance
- Response time/length

## Integration with Technical Specs

For systems with technical specifications (like CHAT_FLOW.md):

**1. Keep the spec as source of truth**:
- Technical spec documents intended behavior
- System prompt implements the spec
- Test scenarios verify implementation matches spec

**2. Generate test conversations** from each section of the spec

**3. Version the system prompt alongside** the technical spec

**4. Create a validation script** that checks if prompt behaviors match spec

**5. When modifying prompts**, reference specific sections of the technical spec rather than describing desired behavior from scratch

## Validation Process

The weakness: Unlike code, you can't easily write automated tests that verify prompt behavior.

**Manual validation approaches**:
1. Maintain curated set of test conversations
2. Manually review after changes
3. Use scoring rubric for key behaviors
4. Track regression patterns over time

**Semi-automated approaches**:
1. Use LLM-as-judge to evaluate responses against criteria
2. Extract structured data from responses for validation
3. Check for presence/absence of required elements
4. Compare similarity to known-good responses

## Recommended Workflow

For this project's therapeutic chat system:

1. **Maintain CHAT_FLOW.md as behavioral specification**
2. **Create test_scenarios.md** with example conversations for each phase
3. **Version system prompt** in version control with semantic commits
4. **Before changes**: Review relevant sections of CHAT_FLOW.md
5. **During changes**: Use constraint-based editing, limit scope
6. **After changes**:
   - Generate diff and review for side effects
   - Test against scenarios for changed sections
   - Test critical paths (safety, crisis, assessment→intervention)
7. **Commit with clear description** of behavioral change
8. **Monitor for regressions** in subsequent sessions

## Example Test Scenario Format

```markdown
## Scenario: New Session Greeting

### Context
- No prior session history
- User is new to the system

### Input
User: "Hello"

### Expected Behavior
1. Warm, empathetic greeting
2. Brief explanation of how chat works
3. Invitation to share what brought them here
4. No assessment questions yet

### Example Good Response
"Hello! I'm glad you're here. I'm here to listen and help you work through
whatever is on your mind. This is a safe space where you can share at your
own pace. What would you like to talk about today?"

### Example Bad Response
"Hi. On a scale of 1-10, how distressed are you feeling right now?"
(Too abrupt, jumps to assessment without building rapport)
```

## References

- See [btcopilot/doc/CHAT_FLOW.md](CHAT_FLOW.md) for technical specification
- See project CLAUDE.md for testing and development practices
