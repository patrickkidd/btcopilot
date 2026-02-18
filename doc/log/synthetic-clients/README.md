# Synthetic Client Development Log

Chronological record of changes to the synthetic conversation system. Intended for psychologists, therapists, and researchers interested in how AI-generated client personas evolve toward (or drift from) realistic human behavior.

## Naming Convention

`YYYY-MM-DD_HH-MM--description.md` (UTC timestamps)

## Log Entries

| Date | Entry | Summary |
|------|-------|---------|
| 2026-02-18 | [05-14--evaluator-and-structural-enforcement](2026-02-18_05-14--evaluator-and-structural-enforcement.md) | Built ClientRealismEvaluator; discovered structural token limits beat prompt guidance for length control |
| 2026-02-18 | [16-42--cutoff-fix-and-prompt-refinement](2026-02-18_16-42--cutoff-fix-and-prompt-refinement.md) | Fixed mid-sentence truncation; evaluated Evan (discussion 55); refined anti-patterns for self-insight, rhetorical questions, verbal tics |

## MANDATORY Logging Rules

**Claude Code MUST create a log entry whenever ANY of the following occur:**

### Triggers (any one = new log entry)

1. **Prompt constant changes** — any edit to `_ANTI_PATTERNS`, `_CONVERSATIONAL_REALISM`, `_RESPONSE_LENGTH`, `_MEMORY_RULES`, `_TRAIT_BEHAVIORS`, `_ATTACHMENT_NARRATIVE`, `_EMOTIONAL_ARC`, `_ARC_MODIFIERS`, or `_HIGH_FUNCTIONING_BEHAVIORS` in `synthetic.py`
2. **Response mode / weight changes** — any edit to `_RESPONSE_MODES`, `_MODE_WEIGHTS`, or the mode selection logic in `simulate_user_response()`
3. **Structural mechanism changes** — changes to token limits, `max_output_tokens` usage, `_trim_to_sentence()`, or any other structural control on response length/shape
4. **Evaluator changes** — new dimensions, threshold adjustments, scoring formula changes in `ClientRealismEvaluator`
5. **Persona generation changes** — changes to `generate_persona()` prompt, Big Five derivation, or how traits/attachment styles map to behavior
6. **Qualitative observations** — when evaluating a synthetic discussion and noting patterns (realistic or unrealistic) in client behavior, even if no code changes follow
7. **Conceptual/psychological drift** — when a change shifts the *kind* of client the system produces (e.g., "clients now deflect more after vulnerability," "avoidant personas show less self-insight," "early-phase responses became more guarded"). These are the most important entries for researchers.

### What each entry must contain

1. **What changed** — code-level description of the modification
2. **Why** — what problem, observation, or hypothesis motivated the change
3. **Psychological rationale** — how the change maps to real clinical behavior. Examples:
   - "Real dismissive-avoidant clients don't narrate their own defense mechanisms — they intellectualize without recognizing it as avoidance"
   - "After disclosing something vulnerable, real clients often retreat to shorter, deflective responses — the system was producing consecutive long emotional responses instead"
   - "The rhetorical question ending ('Why does that matter?') is realistic for guarded clients but becomes formulaic when it appears every other turn"
4. **Results** — quantitative scores (ClientRealismEvaluator) if available, qualitative assessment always
5. **Clinical observations** — what a therapist would notice about the conversation quality. What feels right, what feels off, what a real client would do differently
6. **Sample turns** — representative before/after examples when the change is behavioral

### What NOT to log

- Pure infrastructure changes (DB schema, Flask routes, UI layout) unless they change what the client says
- Test refactoring that doesn't change conversation output
- Bug fixes in non-conversation code

## Audience

These logs are written for:
- **Psychologists/therapists** evaluating whether synthetic clients behave like real first-session coaching clients
- **Researchers** studying the gap between AI-generated and human conversational behavior
- **Future Claude Code sessions** that need to understand why the system generates conversations the way it does

Write entries assuming the reader understands clinical concepts (attachment styles, emotional arc, defense mechanisms, triangulation) but may not know the codebase.
