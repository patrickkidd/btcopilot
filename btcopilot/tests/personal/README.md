# Synthetic Conversation Testing

Automated testing framework for evaluating conversational quality in the Personal app chat flow.

## Overview

This module simulates conversations between the AI coach and synthetic user personas, then evaluates the AI's responses for robotic patterns and conversational quality issues.

## Components

### synthetic.py

Core testing infrastructure:

- **Persona**: Dataclass defining synthetic users with background, presenting problem, behavioral traits, and data points
- **PersonaTrait**: Enum of conversation behaviors (evasive, oversharing, confused_dates, defensive, tangential, terse, emotional)
- **DataCategory**: Enum of required data categories from Bowen Theory coaching checklist
- **DataPoint**: Links a category to keywords indicating the AI asked about it
- **ConversationSimulator**: Runs conversation loops between the chatbot and synthetic users
- **QualityEvaluator**: Detects robotic patterns and scores conversation quality
- **CoverageEvaluator**: Checks if AI asked about required family data categories
- **run_synthetic_tests()**: Orchestrates full test suite across multiple personas

### test_synthetic.py

Pytest integration with unit tests and e2e tests.

## Usage

### Quick unit tests (no LLM calls)

```bash
uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -k "not e2e" -v
```

### Single e2e conversation

```bash
uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py::test_single_persona_conversation -v -m e2e
```

### Full synthetic suite (slow)

```bash
uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -v -m e2e
```

### Skip slow tests

```bash
uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -v -m "e2e and not slow"
```

## Evaluators

### QualityEvaluator

Checks for robotic patterns:

1. **Therapist cliches**: "It sounds like...", "That must be difficult...", "How does that make you feel?"
2. **Repetitive starters**: Same opening phrase used multiple times
3. **Questions per turn**: Excessive questioning in single responses
4. **Verbatim echoing**: Parroting back user's exact words

### CoverageEvaluator

Checks if AI explored required data categories from the Bowen Theory coaching checklist:

| Category | Description |
|----------|-------------|
| PresentingProblem | What brought them, symptoms |
| Mother | Mother's name, details |
| Father | Father's name, details |
| ParentsStatus | Married, divorced, remarried |
| Siblings | Brothers, sisters |
| MaternalGrandparents | Mom's parents |
| PaternalGrandparents | Dad's parents |
| AuntsUncles | Extended family |
| Spouse | Current/ex partner |
| Children | User's children |
| NodalEvents | Deaths, illnesses, moves, marriages |

Coverage is measured by keyword matching in AI responses. Passing threshold is 70%.

## Personas

Five pre-built personas with varied traits:

| Name | Traits | Presenting Problem |
|------|--------|-------------------|
| Sarah | Evasive, Defensive | Anxiety after mother's dementia diagnosis |
| Marcus | Oversharing, Tangential | Commitment issues after breakup |
| Linda | ConfusedDates, Emotional | Depression after son moved out |
| James | Terse, Defensive | Uncertainty about having kids |
| Elena | Tangential, ConfusedDates | Caregiver stress while grieving |

## Adding New Patterns

To detect a new robotic pattern, add it to `ROBOTIC_PATTERNS` in synthetic.py:

```python
ROBOTIC_PATTERNS = [
    # existing patterns...
    (r"\byour_pattern_here\b", "category_name"),
]
```

## Adding New Personas

```python
from btcopilot.tests.personal.synthetic import (
    Persona,
    PersonaTrait,
    DataCategory,
    DataPoint,
)

persona = Persona(
    name="CustomUser",
    background="Description of their family situation",
    traits=[PersonaTrait.Terse, PersonaTrait.Defensive],
    presenting_problem="What brought them to the conversation",
    dataPoints=[
        DataPoint(DataCategory.PresentingProblem, ["anxiety", "stress"]),
        DataPoint(DataCategory.Mother, ["mother", "mom", "jane"]),
        DataPoint(DataCategory.Father, ["father", "dad", "john"]),
        # Add all categories for comprehensive coverage testing
    ],
)
```

## Programmatic Usage

```python
from btcopilot.personal import ask
from btcopilot.tests.personal.synthetic import (
    PERSONAS,
    ConversationSimulator,
    QualityEvaluator,
    CoverageEvaluator,
    run_synthetic_tests,
)

# Run full suite
results = run_synthetic_tests(
    ask_fn=ask,
    personas=PERSONAS[:3],
    conversations_per_persona=2,
)

quality_eval = QualityEvaluator()
coverage_eval = CoverageEvaluator()

for result in results:
    result.quality = quality_eval.evaluate(result)
    result.coverage = coverage_eval.evaluate(result)

    print(f"{result.persona.name}:")
    print(f"  Quality: {result.quality.score:.2f} ({'PASS' if result.quality.passed else 'FAIL'})")
    print(f"  Coverage: {result.coverage.coverageRate:.0%} ({'PASS' if result.coverage.passed else 'FAIL'})")

    if result.coverage.missedCategories:
        print(f"  Missed: {[c.value for c in result.coverage.missedCategories]}")
```

## Score Interpretation

### QualityEvaluator

- **1.0**: Perfect (no issues detected)
- **0.7+**: Passed (acceptable quality)
- **< 0.7**: Failed (needs prompt tuning)

Score penalties:
- -0.1 per detected robotic pattern
- -0.05 per repeated starter beyond 2 occurrences
- -0.1 per question above 3 per turn (average)
- -0.3 * echo_rate for verbatim echoing

### CoverageEvaluator

- **1.0**: All data categories explored
- **0.7+**: Passed (adequate coverage)
- **< 0.7**: Failed (AI missed key family data areas)

## Two Purposes for Synthetic Conversations

**1. Ephemeral Prompt Testing** (`persist=False`)
- Run synthetic suite → evaluate quality/coverage → pass/fail
- Regenerated each time you test
- Used to validate prompt changes don't regress conversation quality

**2. Ground Truth Corpus** (`persist=True`)
- Frozen conversation transcripts for extraction evaluation
- Once persisted, prompt version is irrelevant - the conversation already happened
- Code extractions in training app, approve as ground truth
- Used to calculate F1 metrics for extraction accuracy

## Ground Truth Generation Workflow

### Option A: Web UI (Recommended)

1. Start the training app via the btcopilot-flask mcp server
2. Navigate to `http://127.0.0.1:5555/training/synthetic/`
3. Select a persona from the dropdown
4. Set max turns (default 20)
5. **Uncheck "Skip extraction"** - needed for ground truth coding
6. Click "Generate Discussion"
7. Wait for generation (may take 1-2 minutes)
8. Click "View Discussion" to go to the audit page

### Option B: Programmatic

```python
from btcopilot.personal.chat import ask
from btcopilot.tests.personal.synthetic import ConversationSimulator, PERSONAS

simulator = ConversationSimulator(
    max_turns=20,
    persist=True,
    username="patrick@alaskafamilysystems.com",  # Your username
    skip_extraction=False,  # Needed for ground truth
)

result = simulator.run(PERSONAS[0], ask)
print(f"View at: http://127.0.0.1:5555/training/discussions/{result.discussionId}")
```

## Viewing Synthetic Discussions

Synthetic discussions are marked with:
- **Robot badge** in the discussion header
- **`Discussion.synthetic = True`** in the database
- **`Discussion.synthetic_persona`** JSON with persona metadata

### In Admin Dashboard

1. Navigate to `http://127.0.0.1:5555/training/admin/`
2. Use the "Synthetic filter" dropdown to filter discussions
3. Click a discussion ID to view

### Visual Indicators

- Discussions table: robot icon badge next to discussion ID
- Discussion audit page: yellow "Synthetic" badge with persona name tooltip

## Coding as Ground Truth

1. Navigate to a synthetic discussion at `/training/discussions/{id}`
2. Review each statement with AI extractions
3. Edit incorrect extractions using the SARF Editor
4. Click "Approve" on corrected extractions
5. Extractions become ground truth for F1 calculations

## F1 Metrics with Synthetic Data

The admin dashboard shows **both** F1 metrics:
- **All Data**: Includes synthetic ground truth
- **Real Users Only**: Excludes synthetic discussions

Use "Real Users Only" for honest MVP assessment while still benefiting from synthetic ground truth for coverage.

## Query Ground Truth

```python
from btcopilot.training.models import Feedback
from btcopilot.personal.models import Discussion, Statement

# Find synthetic discussions with approved ground truth
approved = (
    Feedback.query
    .join(Statement, Feedback.statement_id == Statement.id)
    .join(Discussion, Statement.discussion_id == Discussion.id)
    .filter(
        Discussion.synthetic == True,
        Feedback.approved == True,
    )
    .all()
)
```

## ConversationSimulator Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_turns` | 20 | Maximum conversation turns |
| `persist` | False | Save to database |
| `username` | None | User to associate discussion with (required if persist=True) |
| `skip_extraction` | True | Skip PDP extraction (set False for ground truth) |
