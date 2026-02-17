# Synthetic Client Personalities: Implementation Plan

**Spec**: [doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md](../specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md)
**Status**: Draft — iterating before execution

---

## Problem

The synthetic client system produces AI-sounding conversations because:
- Prompts use abstract personality labels with generic instructions
- 7 hardcoded personas can't vary — same backgrounds every time
- 3 personas (Sarah, Marcus, Jennifer) are already coded/frozen
- No persistent eval infrastructure — quality/coverage results are ephemeral
- No client-side evaluation at all

## Solution: Three Workstreams

**A. Behavioral prompt spec** — rewrite prompt architecture per the spec
**B. Dynamic persona generation** — form-driven, LLM-generated, DB-persisted
**C. Eval framework** — persisted, multi-dimensional, designed for eventual human use

---

## Workstream A: Behavioral Prompt Spec

### A1. `AttachmentStyle` enum

```python
class AttachmentStyle(enum.StrEnum):
    Secure = "secure"
    AnxiousPreoccupied = "anxious_preoccupied"
    DismissiveAvoidant = "dismissive_avoidant"
    FearfulAvoidant = "fearful_avoidant"
```

Added to `Persona` dataclass as required field (no default — every persona must have one).

### A2. Module-level prompt constants

Private constants replacing inline prompt text. Budget: ~2050 chars total instructions (backgrounds can be up to 5.5K within 8K limit).

| Constant | Spec Section | ~Chars | Description |
|----------|-------------|--------|-------------|
| `_ANTI_PATTERNS` | 1.1 | 500 | No organized paragraphs, no therapy-speak, no self-aware analysis, no volunteering, no emotion lists, no same openers |
| `_CONVERSATIONAL_REALISM` | 1.2+1.3+1.4 merged | 350 | First-session confusion, mid-thought corrections, trailing off, losing thread, hedging, circling back |
| `_RESPONSE_LENGTH` | 1.6 | 250 | Factual=short, emotional=long+messy, caught off guard=short, max 5-6 sentences, min 1-5 words |
| `_MEMORY_RULES` | 1.7 | 250 | Core facts consistent but interpretation shifts, vivid vs vague vs blank, reconcile contradictions |
| `_TRAIT_BEHAVIORS[trait]` | 2.x per trait | 150-200 each | Concrete behavioral examples per trait (only relevant ones included) |
| `_ATTACHMENT_NARRATIVE[style]` | 6.3 | ~80 each | One sentence describing narrative structure for the attachment style |

Derive the actual condensed text from the corresponding spec sections. Keep within char budgets. Emotional arc (spec 1.5) goes in `simulate_user_response()` instead — it depends on turn number.

### A3. Rewrite `system_prompt()` method

Current location: `Persona.system_prompt()` in `btcopilot/btcopilot/tests/personal/synthetic.py`. Replace the three-tier conditional (high-functioning vs trait-based vs trait-less) with single assembly:

1. Identity + background + presenting problem
2. Universal constants (`_ANTI_PATTERNS`, `_CONVERSATIONAL_REALISM`, `_RESPONSE_LENGTH`, `_MEMORY_RULES`)
3. Relevant `_TRAIT_BEHAVIORS` entries only (for this persona's traits)
4. `_ATTACHMENT_NARRATIVE` line for this persona's attachment style
5. Closing: "Respond only as {name}. Do not include meta-commentary."

The old `consistency_rules` block is absorbed into `_MEMORY_RULES`. The old "Response Variety (CRITICAL)" block is already handled by opener-tracking in `simulate_user_response()`.

### A4. Update `simulate_user_response()` function

Current location: `simulate_user_response()` in same file. Changes:

- Add `turn_num` and `max_turns` params (with defaults `0` and `20` for backward compat with tests)
- Inject emotional arc phase reminder before the conversation history:
  - Turns 1-5: "You are in the early phase. You're still testing the waters — be more guarded than open. Keep answers shorter and more surface-level."
  - Turns 6-15: "You are opening up. You're starting to share things you didn't plan to say. Answers get longer on emotional topics."
  - Turns 15+: "You are in deep territory. You may hit a wall on something painful or have a breakthrough. Emotional responses are less controlled."
- Add trait-based arc modifiers:
  - Defensive → "Your defensive side means the arc is slower — you may not fully open up until much later."
  - Oversharing → "Your oversharing means you give too much too fast early on."
  - Evasive → "You open up on the presenting problem but stay closed on other topics."
  - Emotional → "Your emotional arc is volatile — swings between deeply engaged and pulling back."
- Update caller in `ConversationSimulator.run()` to pass `turn_num, self.max_turns`

---

## Workstream B: Dynamic Persona Generation

### B1. Deprecate frozen personas, delete prototypes

- Sarah, Marcus, Jennifer → `DEPRECATED_PERSONAS` list (already coded/frozen, preserved as reference examples for the generation prompt)
- Linda, James, Elena, David — **delete entirely** (prototypes no longer needed)
- `PERSONAS` list becomes empty — the web form is the sole path for new personas

**Test impact**: `test_synthetic.py` references `PERSONAS[0]` and `PERSONAS` in unit tests. Rewrite tests to construct minimal `Persona` objects inline with the new required `attachmentStyle` field. Tests should exercise the new prompt architecture and dynamic generation — no tests should depend on deprecated personas. The deprecated personas are retained as data artifacts only, not for test execution.

### B2. `SyntheticPersona` DB model

New file: `btcopilot/btcopilot/personal/models/syntheticpersona.py`

```python
class SyntheticPersona(db.Model, ModelMixin):
    __tablename__ = "synthetic_personas"

    name = Column(Text, unique=True, nullable=False)
    background = Column(Text, nullable=False)
    traits = Column(JSON, nullable=False)           # list of trait value strings
    attachment_style = Column(Text, nullable=False)  # AttachmentStyle value
    presenting_problem = Column(Text, nullable=False)
    data_points = Column(JSON, nullable=True)       # [{category, keywords}]
    sex = Column(Text, nullable=False)              # "male" / "female"
    age = Column(Integer, nullable=False)
```

`ModelMixin` provides `id`, `created_at`, `updated_at`. Requires alembic migration.

Export from `btcopilot/btcopilot/personal/models/__init__.py`.

**Constructing `Persona` from DB row:**

```python
def to_persona(self) -> Persona:
    return Persona(
        name=self.name,
        background=self.background,
        traits=[PersonaTrait(t) for t in self.traits],
        attachmentStyle=AttachmentStyle(self.attachment_style),
        presenting_problem=self.presenting_problem,
        dataPoints=[
            DataPoint(DataCategory(dp["category"]), dp["keywords"])
            for dp in (self.data_points or [])
        ],
    )
```

**`Discussion.synthetic_persona` column**: Keep the existing JSON copy behavior — store a snapshot of the persona data in the Discussion row for reproducibility. Also add a nullable `synthetic_persona_id` FK to `synthetic_personas` for linkage. Both fields coexist: the FK for querying, the JSON for immutability.

### B3. `generate_persona()` function

New function in `synthetic.py`: `generate_persona(traits, attachment_style, sex, age) -> Persona`

**Persona generation is synchronous** in the route handler (not Celery). Rationale: the LLM call takes 10-30s, but the result is needed immediately to construct the `Persona` before kicking off the conversation. The route returns the persona_id, then the conversation generation goes to Celery.

Steps:
1. Query existing `SyntheticPersona.name` values to build exclusion list
2. Call `gemini_text_sync()` with structured prompt requesting **JSON output** containing:
   - **Sex-appropriate unique first name** (excluded names passed in prompt to avoid collisions)
   - **Full family background** in the same format as deprecated personas (family tree with names/ages, nodal events with emotional process, relationship patterns)
   - **Presenting problem** matching traits/attachment style/sex/age per spec sections 4.1, 6.2, 6.4
   - **DataPoints**: family member names mapped to `DataCategory` values (for coverage evaluation)
3. Parse JSON response, validate required fields
4. Save to `SyntheticPersona` table
5. Return `Persona` object via `to_persona()`

**Big Five integration in the generation prompt**: The form does NOT expose Big Five directly. Instead, the generation prompt uses Big Five as an internal coherence check — it includes instructions like: "The selected traits [{traits}] with attachment style [{attachment_style}] correspond to approximately [derived Big Five profile]. Ensure the generated background and presenting problem are consistent with this personality profile." The mapping from traits+attachment → approximate Big Five profile is hardcoded in the generation prompt template (e.g., Defensive+DismissiveAvoidant ≈ low-A, low-N; Oversharing+AnxiousPreoccupied ≈ high-N, high-E, high-A). See spec section 6.1 for the full mapping rationale.

**Few-shot examples**: Include 1-2 deprecated persona backgrounds in the generation prompt as format examples (truncated to save tokens).

### B4. Web UI form

Replace persona dropdown in `synthetic_index.html` with generation form:

| Field | Type | Options |
|-------|------|---------|
| Traits | Multi-select checkboxes | PersonaTrait enum values |
| Attachment Style | Dropdown | 4 AttachmentStyle values |
| Sex | Dropdown | Male / Female |
| Age Range | Dropdown | 20s / 30s / 40s / 50s |
| Max Turns | Number input | Keep existing (default 25) |
| User | Dropdown | Keep existing |
| Include Extraction | Checkbox | Keep existing |

Flow:
1. User fills form, clicks Generate
2. `POST /generate-persona` — synchronous, takes 10-30s (show spinner)
3. Returns `persona_id` + generated persona name
4. Immediately `POST /generate` with `persona_id` — kicks off Celery task
5. Poll for progress (existing mechanism)

Also: collapsible section listing previously generated personas from DB (name, traits, attachment style, date) with button to re-generate a conversation with that persona.

### B5. Route + task updates

**Routes** (`btcopilot/btcopilot/training/routes/synthetic.py`):
- `POST /generate-persona` — accepts `{traits, attachment_style, sex, age}`, calls `generate_persona()`, returns `{persona_id, name}`
- Update `POST /generate` — accept `persona_id` param, load `SyntheticPersona` from DB
- `GET /` — query `SyntheticPersona` table, pass to template for listing

**Task** (`btcopilot/btcopilot/training/tasks.py`):
- `generate_synthetic_discussion` accepts `persona_id` (new primary path)
- Loads `SyntheticPersona` → calls `to_persona()` → passes to `ConversationSimulator`
- Stores `synthetic_persona_id` FK on the `Discussion` row
- Legacy `persona_name` path falls back to `DEPRECATED_PERSONAS` lookup (for existing coded conversations)

---

## Workstream C: Eval Framework

### C1. Eval data model

New file: `btcopilot/btcopilot/personal/models/evalresult.py`

```python
class EvalRubric(db.Model, ModelMixin):
    __tablename__ = "eval_rubrics"

    name = Column(Text, nullable=False)            # "therapist", "client"
    version = Column(Integer, nullable=False)
    target = Column(Text, nullable=False)           # "therapist" or "client"
    dimensions = Column(JSON, nullable=False)       # [{name, description, weight, scoring}]
    # UniqueConstraint(name, version)


class EvalResult(db.Model, ModelMixin):
    __tablename__ = "eval_results"

    discussion_id = Column(Integer, ForeignKey("discussions.id"), nullable=False)
    rubric_id = Column(Integer, ForeignKey("eval_rubrics.id"), nullable=False)
    scores = Column(JSON, nullable=False)           # {dimension_name: {score, evidence}}
    total_score = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)

    discussion = relationship("Discussion")
    rubric = relationship("EvalRubric")
```

Versioned rubrics so old results remain interpretable as rubrics evolve. Same schema works for automated evals now and human-rater evals later.

Requires alembic migration (3 new tables total: `synthetic_personas`, `eval_rubrics`, `eval_results`).

### C2. Therapist rubric (`therapist_v1`)

Evaluates the AI coach. Dimensions map to clinical competencies for eventual human trainee assessment.

| Dimension | Method | Source |
|-----------|--------|--------|
| `robotic_patterns` | Regex penalty | Existing `QualityEvaluator._detect_patterns()` |
| `repetitive_starters` | Count penalty | Existing `QualityEvaluator._count_starters()` |
| `verbatim_echo` | Rate × penalty | Existing `QualityEvaluator._calculate_echo_rate()` |
| `question_density` | Avg penalty | Existing `QualityEvaluator._count_questions()` |
| `topic_coverage` | % categories covered | Existing `CoverageEvaluator` |
| `multigenerational_exploration` | LLM-scored | Did coach explore grandparents, cross-gen patterns? |
| `emotional_attunement` | LLM-scored | Did coach validate emotions without formulaic responses? |
| `pacing` | LLM-scored | Did coach match client's emotional pace? |

### C3. Client rubric (`client_v1`)

Evaluates synthetic client realism. Dimensions are constructs designed for eventual psychometric validation.

| Dimension | Method | Source |
|-----------|--------|--------|
| `therapy_speak` | Regex | Clinical jargon in client turns |
| `organized_delivery` | Heuristic + LLM | Structured backstory dumps, lists |
| `first_session_behavior` | Presence check | Confusion about process, surprise at questions |
| `emotional_arc` | LLM-scored | Tone shift across conversation thirds |
| `trait_consistency` | LLM-scored | Behaviors match assigned traits throughout |
| `narrative_coherence` | LLM-scored | Narrative structure matches attachment style |

### C4. Evaluator classes

New file: `btcopilot/btcopilot/tests/personal/evaluators.py`

- `TherapistEvaluator` — absorbs existing `QualityEvaluator` + `CoverageEvaluator` methods as dimension scorers. Creates/looks up `EvalRubric(name="therapist", version=1)`. Persists `EvalResult` to DB.
- `ClientEvaluator` — new. Creates/looks up `EvalRubric(name="client", version=1)`. Persists `EvalResult` to DB.

Both: score each dimension, compute weighted total, create `EvalResult` linked to `Discussion`.

Existing `QualityEvaluator` and `CoverageEvaluator` classes in `synthetic.py` are replaced by `TherapistEvaluator`. Old classes can be deleted.

### C5. Integration

- Celery task runs both evaluators after conversation completes, persists results
- Task result returns structured eval data: `{eval_results: [{rubric_name, total_score, passed, scores: {dim: {score, evidence}}}]}`
- Template shows per-dimension breakdown for both therapist and client evals in the result notification

---

## Documentation Updates

**Already done** (in current session):
- `btcopilot/CLAUDE.md` doc index: added `Synthetic client personas, evals` and `Feature/behavior specs` rows
- Top-level `CLAUDE.md` routing table: added same rows
- Fixed broken `PROMPT_ENGINEERING_CONTEXT.md` → `PROMPT_ENGINEERING_LOG.md` ref
- `btcopilot/README.md`: Phase 12 section with full description, Novel Contributions entry

**Still needed:**
- Create `btcopilot/doc/specs/EVAL_FRAMEWORK_SPEC.md` documenting the psychometric roadmap (section below)

---

## Psychometric Roadmap (document in EVAL_FRAMEWORK_SPEC.md, not implemented in code)

The eval framework is designed so that:

1. **Therapist evals → human trainee assessment**: Same dimensions applied to conversations where a human trainee replaces the AI coach. Rubric versioning enables calibration against AI baseline.

2. **Client evals → psychometric instruments**: Dimensions like narrative coherence, emotional arc, therapy-speak could become formal psychometric constructs if validated via:
   - Inter-rater reliability (human raters score same transcripts)
   - Test-retest reliability (same persona config generates similar scores)
   - Construct validity (dimensions discriminate between attachment styles)

3. **Validation protocol**: Generate N conversations per attachment style × trait combination → compute scores → test discrimination → if significant, the rubric has construct validity.

---

## Risks

1. **Generated persona quality** — LLM may produce inconsistent backgrounds. Mitigation: structured JSON output, validation, few-shot examples from deprecated personas.
2. **LLM-scored dimensions cost** — 3-6 extra Gemini calls per conversation. Mitigation: async in Celery, use Flash model.
3. **Scope** — this is large. If needed, defer LLM-scored eval dimensions (C2/C3 LLM rows) to phase 2 and ship with automated (regex/heuristic) dimensions only.

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `btcopilot/btcopilot/tests/personal/synthetic.py` | `AttachmentStyle` enum, prompt constants, `system_prompt()`, `simulate_user_response()`, `generate_persona()`. Sarah/Marcus/Jennifer → `DEPRECATED_PERSONAS`. Linda/James/Elena/David deleted. `PERSONAS` empty. |
| `btcopilot/btcopilot/personal/models/syntheticpersona.py` | **New** — `SyntheticPersona` model with `to_persona()` method |
| `btcopilot/btcopilot/personal/models/evalresult.py` | **New** — `EvalRubric`, `EvalResult` models |
| `btcopilot/btcopilot/personal/models/__init__.py` | Export new models |
| `btcopilot/btcopilot/personal/models/discussion.py` | Add nullable `synthetic_persona_id` FK column |
| `btcopilot/btcopilot/tests/personal/evaluators.py` | **New** — `TherapistEvaluator`, `ClientEvaluator` |
| `btcopilot/btcopilot/training/routes/synthetic.py` | New `POST /generate-persona`, update `POST /generate` and `GET /` |
| `btcopilot/btcopilot/training/tasks.py` | Accept `persona_id`, load from DB, run evals, persist results |
| `btcopilot/btcopilot/training/templates/synthetic_index.html` | Generation form replacing persona dropdown |
| `btcopilot/btcopilot/tests/personal/test_synthetic.py` | Rewrite tests to use inline `Persona` objects with new fields. Remove all `PERSONAS[0]` refs. Add `generate_persona` test (mocked LLM). Add evaluator tests for new dimensions. |
| Alembic migration | 3 new tables (`synthetic_personas`, `eval_rubrics`, `eval_results`) + `discussions.synthetic_persona_id` FK |
| `btcopilot/doc/specs/EVAL_FRAMEWORK_SPEC.md` | **New** — psychometric roadmap |

## Verification

1. Unit tests pass: `uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -k "not e2e" -v`
2. Migration: `uv run alembic upgrade head`
3. Web UI: fill form → persona generates with unique sex-appropriate name → conversation runs → eval results display per-dimension
4. Manual transcript review for naturalness (compare against old transcripts)
5. DB check: `synthetic_personas` and `eval_results` tables populated correctly
