"""
Pytest integration for synthetic conversation quality testing.

Run with: uv run pytest btcopilot/tests/personal/test_synthetic.py -v -m e2e
"""

import logging

import pytest

from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Statement, Speaker
from btcopilot.tests.personal.synthetic import (
    PERSONAS,
    Persona,
    PersonaTrait,
    DataCategory,
    DataPoint,
    ConversationSimulator,
    QualityEvaluator,
    CoverageEvaluator,
    run_synthetic_tests,
    Turn,
    ConversationResult,
)


_log = logging.getLogger(__name__)


def test_detects_therapist_cliches():
    evaluator = QualityEvaluator()
    turns = [
        Turn(speaker="user", text="I'm having trouble with my mom"),
        Turn(
            speaker="ai",
            text="It sounds like you're struggling with that relationship.",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=PERSONAS[0]))
    categories = [p.category for p in result.patterns]
    assert "therapist_cliche" in categories


def test_detects_repetitive_starters():
    evaluator = QualityEvaluator()
    turns = [
        Turn(speaker="user", text="My dad left when I was 10"),
        Turn(speaker="ai", text="That's interesting. Tell me more."),
        Turn(speaker="user", text="It was hard"),
        Turn(speaker="ai", text="That's interesting. How did your mom handle it?"),
        Turn(speaker="user", text="She struggled"),
        Turn(speaker="ai", text="That's interesting. What about your siblings?"),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=PERSONAS[0]))
    assert "that's interesting" in result.repetitiveStarters
    assert result.repetitiveStarters["that's interesting"] >= 3


def test_counts_questions():
    evaluator = QualityEvaluator()
    turns = [
        Turn(speaker="user", text="I have two brothers"),
        Turn(
            speaker="ai",
            text="What are their names? How old are they? Where do they live?",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=PERSONAS[0]))
    assert result.questionsPerTurn[0] == 3


def test_detects_echoing():
    evaluator = QualityEvaluator()
    turns = [
        Turn(speaker="user", text="My mother always criticized my choices"),
        Turn(
            speaker="ai",
            text="So your mother always criticized your choices. How did that affect you?",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=PERSONAS[0]))
    assert result.verbatimEchoRate > 0.0


def test_good_conversation_scores_higher():
    evaluator = QualityEvaluator()
    bad_turns = [
        Turn(speaker="user", text="I'm anxious about my mom's diagnosis"),
        Turn(
            speaker="ai",
            text="It sounds like that must be difficult. How does that make you feel?",
        ),
        Turn(speaker="user", text="Scared"),
        Turn(speaker="ai", text="It sounds like you're feeling scared. Tell me more."),
    ]
    good_turns = [
        Turn(speaker="user", text="I'm anxious about my mom's diagnosis"),
        Turn(
            speaker="ai",
            text="When did she get diagnosed? What was going on in the family at that time?",
        ),
        Turn(speaker="user", text="Six months ago. My dad had just retired."),
        Turn(speaker="ai", text="How did your dad react to her diagnosis?"),
    ]
    bad_result = evaluator.evaluate(
        ConversationResult(turns=bad_turns, persona=PERSONAS[0])
    )
    good_result = evaluator.evaluate(
        ConversationResult(turns=good_turns, persona=PERSONAS[0])
    )
    assert good_result.score > bad_result.score


def test_coverage_detects_missing_categories():
    persona = Persona(
        name="Test",
        background="Test",
        dataPoints=[
            DataPoint(DataCategory.Mother, ["mother", "mom"]),
            DataPoint(DataCategory.Father, ["father", "dad"]),
            DataPoint(DataCategory.Siblings, ["brother", "sister"]),
        ],
    )
    turns = [
        Turn(speaker="user", text="I'm stressed"),
        Turn(speaker="ai", text="Tell me about your mother."),
    ]
    evaluator = CoverageEvaluator()
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.coverageRate < 1.0
    assert DataCategory.Father in result.missedCategories
    assert DataCategory.Siblings in result.missedCategories
    assert DataCategory.Mother not in result.missedCategories


def test_coverage_tracks_matched_keywords():
    persona = Persona(
        name="Test",
        background="Test",
        dataPoints=[
            DataPoint(DataCategory.Mother, ["carol", "mother", "mom"]),
        ],
    )
    turns = [
        Turn(speaker="user", text="My mom is sick"),
        Turn(speaker="ai", text="How is Carol doing? When did your mother get sick?"),
    ]
    evaluator = CoverageEvaluator()
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.coverageRate == 1.0
    assert "carol" in result.categoryCoverage[0].matchedKeywords
    assert "mother" in result.categoryCoverage[0].matchedKeywords


def test_coverage_full_persona():
    evaluator = CoverageEvaluator()
    turns = [
        Turn(speaker="user", text="I can't sleep since mom's dementia diagnosis"),
        Turn(
            speaker="ai",
            text="Tell me about your sleep and anxiety. When was Carol diagnosed?",
        ),
        Turn(speaker="user", text="Six months ago. Dad lives in Florida."),
        Turn(
            speaker="ai",
            text="How is your father Richard handling it? Are your parents divorced?",
        ),
        Turn(speaker="user", text="Yes, divorced in 1997."),
        Turn(
            speaker="ai",
            text="How is your brother Michael? Were there deaths in the family?",
        ),
        Turn(speaker="user", text="Ruth died in 2018, Harold in 2010."),
        Turn(speaker="ai", text="What about Margaret and George on your dad's side?"),
        Turn(speaker="user", text="Margaret is 92, George died in 1995."),
        Turn(
            speaker="ai",
            text="Do you have aunts or uncles? How are David and the kids?",
        ),
        Turn(speaker="user", text="Yes, Aunt Linda. David and Emma and Jake are good."),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=PERSONAS[0]))
    assert result.coverageRate >= 0.9
    assert result.passed


def test_coverage_empty_datapoints():
    persona = Persona(name="Test", background="Test", dataPoints=[])
    turns = [Turn(speaker="ai", text="Hello")]
    evaluator = CoverageEvaluator()
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.coverageRate == 1.0
    assert result.passed


@pytest.mark.e2e
def test_coverage_in_live_conversation(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    persona = PERSONAS[0]
    simulator = ConversationSimulator(
        max_turns=2, persist=True, username=test_user.username
    )
    coverage_eval = CoverageEvaluator()

    result = simulator.run(persona, ask)
    result.coverage = coverage_eval.evaluate(result)

    _log.info(f"\n{'='*60}")
    _log.info(f"Synthetic Conversation with {persona.name}")
    _log.info(f"{'='*60}")
    for i, turn in enumerate(result.turns):
        speaker = "USER" if turn.speaker == "user" else "AI"
        _log.info(f"\n[{i+1}] {speaker}:\n{turn.text}")
    _log.info(f"\n{'='*60}")
    _log.info(f"Coverage: {result.coverage.coverageRate:.0%}")
    _log.info(
        f"Missed categories: {[c.value for c in result.coverage.missedCategories]}"
    )
    for cat in result.coverage.categoryCoverage:
        status = "✓" if cat.covered else "✗"
        _log.info(f"  {status} {cat.category.value}: {cat.matchedKeywords}")
    _log.info(f"Discussion ID: {result.discussionId}")
    _log.info(f"View at: http://127.0.0.1:8888/discussions/{result.discussionId}")
    _log.info(f"{'='*60}")

    assert result.coverage.passed, f"Coverage {result.coverage.coverageRate:.0%} < 70%"


@pytest.mark.e2e
def test_single_persona_conversation(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    persona = PERSONAS[0]
    simulator = ConversationSimulator(max_turns=10)
    evaluator = QualityEvaluator()

    def ask_wrapper(discussion, user_statement):
        return ask(discussion, user_statement)

    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    result = simulator.run(persona, ask_wrapper)
    result.quality = evaluator.evaluate(result)

    _log.info(f"Conversation with {persona.name}:")
    for turn in result.turns:
        _log.info(f"  {turn.speaker}: {turn.text[:80]}...")
    _log.info(f"Quality score: {result.quality.score:.2f}")
    _log.info(f"Patterns found: {len(result.quality.patterns)}")
    for pattern in result.quality.patterns:
        _log.info(f"  - {pattern.category}: {pattern.text[:60]}...")

    assert len(result.turns) >= 4
    assert result.quality is not None


@pytest.mark.e2e
@pytest.mark.slow
def test_full_synthetic_suite(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    results = run_synthetic_tests(
        ask_fn=ask,
        personas=PERSONAS[:3],
        conversations_per_persona=1,
    )

    passed_count = sum(1 for r in results if r.quality and r.quality.passed)
    total_count = len(results)

    _log.info(f"Synthetic test results: {passed_count}/{total_count} passed")
    for result in results:
        if result.quality:
            _log.info(
                f"  {result.persona.name}: score={result.quality.score:.2f}, "
                f"patterns={len(result.quality.patterns)}"
            )

    assert (
        passed_count >= total_count * 0.5
    ), f"Only {passed_count}/{total_count} passed"


@pytest.mark.e2e
def test_regression_robotic_patterns(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    persona = Persona(
        name="TestUser",
        background="30-year-old, married, one child.",
        traits=[PersonaTrait.Terse],
        presenting_problem="Stress at work affecting sleep.",
    )

    simulator = ConversationSimulator(max_turns=8)
    evaluator = QualityEvaluator()

    result = simulator.run(persona, ask)
    result.quality = evaluator.evaluate(result)

    cliches = [p for p in result.quality.patterns if p.category == "therapist_cliche"]
    assert len(cliches) == 0, f"Found therapist clichés: {[p.text for p in cliches]}"

    for starter, count in result.quality.repetitiveStarters.items():
        assert count <= 3, f"Starter '{starter}' repeated {count} times"


@pytest.mark.chat_flow(response="Tell me about your family.")
def test_persist_synthetic_conversation(test_user):
    from btcopilot.pro.models import Diagram

    persona = Persona(
        name="TestPersist",
        background="Test background.",
        traits=[PersonaTrait.Terse],
        presenting_problem="Test problem.",
    )

    simulator = ConversationSimulator(
        max_turns=2, persist=True, username=test_user.username
    )
    result = simulator.run(persona, ask)

    assert result.discussionId is not None

    discussion = db.session.get(Discussion, result.discussionId)
    assert discussion is not None
    assert discussion.synthetic is True
    assert discussion.synthetic_persona is not None
    assert discussion.synthetic_persona["name"] == "TestPersist"
    assert "terse" in discussion.synthetic_persona["traits"]
    assert discussion.diagram_id is not None

    diagram = db.session.get(Diagram, discussion.diagram_id)
    assert diagram is not None
    assert diagram.name == "Synthetic: TestPersist"

    assert len(discussion.statements) >= 2
    assert len(discussion.speakers) == 2

    user_speaker = next(
        (s for s in discussion.speakers if s.name == "TestPersist"), None
    )
    ai_speaker = next((s for s in discussion.speakers if s.name == "AI Coach"), None)
    assert user_speaker is not None
    assert ai_speaker is not None

    user_stmts = [s for s in discussion.statements if s.speaker_id == user_speaker.id]
    ai_stmts = [s for s in discussion.statements if s.speaker_id == ai_speaker.id]
    assert len(user_stmts) >= 1
    assert len(ai_stmts) >= 1

    diagram_id = discussion.diagram_id
    db.session.delete(discussion)
    db.session.flush()
    db.session.delete(db.session.get(Diagram, diagram_id))
    db.session.commit()


@pytest.mark.chat_flow(response="Tell me about your family.")
def test_non_persist_cleans_up(test_user):
    initial_count = Discussion.query.filter_by(synthetic=True).count()

    persona = Persona(
        name="TestCleanup",
        background="Test background.",
        traits=[PersonaTrait.Terse],
        presenting_problem="Test problem.",
    )

    simulator = ConversationSimulator(max_turns=2, persist=False)
    result = simulator.run(persona, ask)

    assert result.discussionId is None

    final_count = Discussion.query.filter_by(synthetic=True).count()
    assert final_count == initial_count
