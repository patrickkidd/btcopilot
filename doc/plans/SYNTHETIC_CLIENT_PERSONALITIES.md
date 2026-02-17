# Synthetic Client Personalities: Implementation Plan

**Spec**: [doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md](../specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md)
**Status**: Draft — iterating before execution

---

## Problem

The synthetic client system produces AI-sounding conversations because:
- Prompts use abstract personality labels with generic instructions
- 7 hardcoded personas can't vary — same backgrounds every time
- 3 personas (Sarah, James, Marcus) are already coded/frozen
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

| Constant | Spec Section | ~Chars |
|----------|-------------|--------|
| `_ANTI_PATTERNS` | 1.1 | 500 |
| `_CONVERSATIONAL_REALISM` | 1.2+1.3+1.4 merged | 350 |
| `_RESPONSE_LENGTH` | 1.6 | 250 |
| `_MEMORY_RULES` | 1.7 | 250 |
| `_TRAIT_BEHAVIORS[trait]` | 2.x per trait | 150-200 each |
| `_ATTACHMENT_NARRATIVE[style]` | 6.3 | 1 sentence each |

Emotional arc (spec 1.5) goes in `simulate_user_response()` — depends on turn number.

### A3. Rewrite `system_prompt()` (lines 66-132)

Replace three-tier conditional with single assembly:
1. Identity + background + presenting problem
2. Universal constants
3. Relevant `_TRAIT_BEHAVIORS` entries only
4. Attachment narrative line
5. Closing directive

### A4. Update `simulate_user_response()` (lines 910-939)

- Add `turn_num` and `max_turns` params
- Inject emotional arc phase (1-5: guarded, 6-15: opening up, 15+: deep)
- Trait-based arc modifiers (Defensive = slower, Oversharing = inverted, etc.)
- Update caller at line 1060

---

## Workstream B: Dynamic Persona Generation

### B1. Deprecate all static personas

All 7 existing personas → `DEPRECATED_PERSONAS` list. They serve as reference examples for the generation prompt and for test backward compatibility. `PERSONAS` becomes empty — the form is the sole path for new personas.

### B2. `SyntheticPersona` DB model

```python
class SyntheticPersona(db.Model, ModelMixin):
    __tablename__ = "synthetic_personas"

    name = Column(Text, unique=True, nullable=False)
    background = Column(Text, nullable=False)
    traits = Column(JSON, nullable=False)           # list of trait strings
    attachment_style = Column(Text, nullable=False)
    presenting_problem = Column(Text, nullable=False)
    data_points = Column(JSON, nullable=True)       # [{category, keywords}]
    sex = Column(Text, nullable=False)              # "male" / "female"
    age = Column(Integer, nullable=False)
```

`ModelMixin` provides `id`, `created_at`, `updated_at`. Alembic migration.

### B3. `generate_persona()` function

`generate_persona(traits, attachment_style, sex, age) -> Persona`

- Queries existing `SyntheticPersona.name` values to build exclusion list
- Calls `gemini_text_sync()` with structured prompt requesting JSON output:
  - **Sex-appropriate unique first name** (excluded names passed in prompt)
  - Full family background (same format as deprecated personas — family tree, nodal events, emotional process, relationship patterns)
  - Presenting problem matching traits/attachment/sex/age per spec sections 4.1, 6.2, 6.4
  - DataPoints: family member names mapped to `DataCategory` values
- Sex-differentiated communication defaults baked into the generation prompt (spec 6.2)
- Age/generational norms baked in (spec 6.4)
- Saves to `SyntheticPersona` table
- Returns `Persona` object with all fields populated

### B4. Web UI form

Replace persona dropdown in `synthetic_index.html`:

| Field | Type | Options |
|-------|------|---------|
| Traits | Multi-select checkboxes | PersonaTrait values |
| Attachment Style | Dropdown | 4 attachment styles |
| Sex | Dropdown | Male / Female |
| Age Range | Dropdown | 20s / 30s / 40s / 50s |
| Max Turns | Number input | Keep existing |
| User | Dropdown | Keep existing |
| Include Extraction | Checkbox | Keep existing |

Flow: Submit → `POST /generate-persona` → LLM generates persona → save to DB → kick off conversation via Celery (passing `persona_id`).

Also: section listing previously generated personas from DB with option to re-run.

### B5. Route + task updates

**Routes** (`training/routes/synthetic.py`):
- `POST /generate-persona` — calls `generate_persona()`, returns `persona_id`
- Update `POST /generate` — accept `persona_id`, load `SyntheticPersona` from DB
- `GET /` — list generated personas from DB

**Task** (`training/tasks.py`):
- `generate_synthetic_discussion` accepts `persona_id`
- Loads `SyntheticPersona` → constructs `Persona` object
- Legacy `persona_name` path falls back to `DEPRECATED_PERSONAS` lookup

---

## Workstream C: Eval Framework

### C1. Eval data model

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
    scores = Column(JSON, nullable=False)           # {dimension: {score, evidence}}
    total_score = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)

    discussion = relationship("Discussion")
    rubric = relationship("EvalRubric")
```

Versioned rubrics so old results remain interpretable as rubrics evolve. Same schema works for automated evals now and human-rater evals later.

### C2. Therapist rubric (`therapist_v1`)

Evaluates the AI coach. Dimensions map to clinical competencies for eventual human trainee assessment.

| Dimension | Method | Source |
|-----------|--------|--------|
| `robotic_patterns` | Regex penalty | Existing `_detect_patterns()` |
| `repetitive_starters` | Count penalty | Existing `_count_starters()` |
| `verbatim_echo` | Rate × penalty | Existing `_calculate_echo_rate()` |
| `question_density` | Avg penalty | Existing `_count_questions()` |
| `topic_coverage` | % categories covered | Existing `CoverageEvaluator` |
| `multigenerational_exploration` | LLM-scored | Did coach explore grandparents, cross-gen patterns? |
| `emotional_attunement` | LLM-scored | Did coach validate emotions without formulaic responses? |
| `pacing` | LLM-scored | Did coach match client's emotional pace? |

### C3. Client rubric (`client_v1`)

Evaluates synthetic client realism. Dimensions are constructs that could become psychometric instruments.

| Dimension | Method | Source |
|-----------|--------|--------|
| `therapy_speak` | Regex | Clinical jargon in client turns |
| `organized_delivery` | Heuristic + LLM | Structured backstory dumps, lists |
| `first_session_behavior` | Presence check | Confusion about process, surprise at questions |
| `emotional_arc` | LLM-scored | Tone shift across conversation thirds |
| `trait_consistency` | LLM-scored | Behaviors match assigned traits throughout |
| `narrative_coherence` | LLM-scored | Narrative structure matches attachment style |

### C4. Evaluator classes

New file `btcopilot/btcopilot/tests/personal/evaluators.py`:

- `TherapistEvaluator` — absorbs existing `QualityEvaluator` + `CoverageEvaluator` methods as dimension scorers. Persists `EvalResult` to DB.
- `ClientEvaluator` — new. Persists `EvalResult` to DB.

Both look up (or create) their `EvalRubric` by name+version, score each dimension, compute weighted total, persist result.

### C5. Integration

- Celery task runs both evaluators after conversation completes
- Task result returns structured eval data instead of flat `quality_score`/`coverage_rate`
- Template shows per-dimension breakdown for both therapist and client evals

---

## Documentation Updates

- Add to `btcopilot/CLAUDE.md` doc index: `Synthetic client personas, evals | doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md`
- Add to top-level `CLAUDE.md` routing table: `Feature/behavior specs | btcopilot/doc/specs/`
- Fix broken `PROMPT_ENGINEERING_CONTEXT.md` → `PROMPT_ENGINEERING_LOG.md` refs in both files
- Create `btcopilot/doc/specs/EVAL_FRAMEWORK_SPEC.md` documenting the psychometric roadmap

---

## Psychometric Roadmap (documented, not implemented)

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
3. **Scope** — this is large. If needed, defer LLM-scored eval dimensions to phase 2 and ship with automated (regex/heuristic) dimensions only.

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `btcopilot/btcopilot/tests/personal/synthetic.py` | Enums, prompt constants, `system_prompt()`, `simulate_user_response()`, all 7 → `DEPRECATED_PERSONAS`, `generate_persona()` |
| `btcopilot/btcopilot/personal/models/syntheticpersona.py` | **New** |
| `btcopilot/btcopilot/personal/models/evalresult.py` | **New** |
| `btcopilot/btcopilot/personal/models/__init__.py` | Export new models |
| `btcopilot/btcopilot/tests/personal/evaluators.py` | **New** — refactored evaluator classes |
| `btcopilot/btcopilot/training/routes/synthetic.py` | New routes |
| `btcopilot/btcopilot/training/tasks.py` | Accept persona_id, run evals |
| `btcopilot/btcopilot/training/templates/synthetic_index.html` | Generation form |
| `btcopilot/btcopilot/tests/personal/test_synthetic.py` | Updated imports, new tests |
| `btcopilot/CLAUDE.md` | Doc index update |
| `CLAUDE.md` (top-level) | Routing table update |
| Alembic migration | 3 new tables |
| `btcopilot/doc/specs/EVAL_FRAMEWORK_SPEC.md` | **New** — psychometric roadmap |

## Verification

1. Unit tests pass: `uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -k "not e2e" -v`
2. Migration: `uv run alembic upgrade head`
3. Web UI: fill form → persona generates with unique sex-appropriate name → conversation runs → eval results display per-dimension
4. Manual transcript review for naturalness
5. DB check: `synthetic_personas` and `eval_results` tables populated
