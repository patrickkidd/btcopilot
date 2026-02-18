"""
Pytest integration for synthetic conversation quality testing.

Run with: uv run pytest btcopilot/btcopilot/tests/personal/test_synthetic.py -v -m e2e
"""

import json
import logging

import pytest

from btcopilot.extensions import db
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Statement, Speaker
from btcopilot.tests.personal.synthetic import (
    DEPRECATED_PERSONAS,
    Persona,
    PersonaTrait,
    AttachmentStyle,
    DataCategory,
    DataPoint,
    ConversationSimulator,
    QualityEvaluator,
    CoverageEvaluator,
    run_synthetic_tests,
    Turn,
    ConversationResult,
    generate_persona,
)


_log = logging.getLogger(__name__)


# --- Prompt Architecture Tests ---


def test_system_prompt_includes_anti_patterns():
    persona = Persona(
        name="Test",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
    )
    prompt = persona.system_prompt()
    assert "Anti-Patterns" in prompt
    assert "therapy-speak" in prompt


def test_system_prompt_includes_attachment_narrative():
    persona = Persona(
        name="Test",
        background="Test background.",
        attachmentStyle=AttachmentStyle.DismissiveAvoidant,
    )
    prompt = persona.system_prompt()
    assert "Narrative Style" in prompt
    assert "lacks emotional content" in prompt


def test_system_prompt_includes_trait_behaviors():
    persona = Persona(
        name="Test",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
        traits=[PersonaTrait.Evasive, PersonaTrait.Defensive],
    )
    prompt = persona.system_prompt()
    assert "Behavioral Traits" in prompt
    assert "shields" in prompt.lower() or "redirect" in prompt.lower()
    assert "push back" in prompt.lower() or "shut down" in prompt.lower()


def test_system_prompt_deduplicates_high_functioning():
    persona = Persona(
        name="Test",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
    )
    prompt = persona.system_prompt()
    # Should only appear once even with both traits
    assert prompt.count("genuine curiosity") == 1


def test_system_prompt_no_old_conditional_sections():
    persona = Persona(
        name="Test",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
        traits=[PersonaTrait.Terse],
    )
    prompt = persona.system_prompt()
    # Old sections should not appear
    assert "Consistency & Improvisation" not in prompt
    assert "Response Variety (CRITICAL)" not in prompt


# --- Quality Evaluator Tests ---


def test_detects_therapist_cliches():
    evaluator = QualityEvaluator()
    persona = Persona(
        name="Test",
        background="Test.",
        attachmentStyle=AttachmentStyle.Secure,
    )
    turns = [
        Turn(speaker="user", text="I'm having trouble with my mom"),
        Turn(
            speaker="ai",
            text="It sounds like you're struggling with that relationship.",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    categories = [p.category for p in result.patterns]
    assert "therapist_cliche" in categories


def test_detects_repetitive_starters():
    evaluator = QualityEvaluator()
    persona = Persona(
        name="Test",
        background="Test.",
        attachmentStyle=AttachmentStyle.Secure,
    )
    turns = [
        Turn(speaker="user", text="My dad left when I was 10"),
        Turn(speaker="ai", text="That's interesting. Tell me more."),
        Turn(speaker="user", text="It was hard"),
        Turn(speaker="ai", text="That's interesting. How did your mom handle it?"),
        Turn(speaker="user", text="She struggled"),
        Turn(speaker="ai", text="That's interesting. What about your siblings?"),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert "that's interesting" in result.repetitiveStarters
    assert result.repetitiveStarters["that's interesting"] >= 3


def test_counts_questions():
    evaluator = QualityEvaluator()
    persona = Persona(
        name="Test",
        background="Test.",
        attachmentStyle=AttachmentStyle.Secure,
    )
    turns = [
        Turn(speaker="user", text="I have two brothers"),
        Turn(
            speaker="ai",
            text="What are their names? How old are they? Where do they live?",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.questionsPerTurn[0] == 3


def test_detects_echoing():
    evaluator = QualityEvaluator()
    persona = Persona(
        name="Test",
        background="Test.",
        attachmentStyle=AttachmentStyle.Secure,
    )
    turns = [
        Turn(speaker="user", text="My mother always criticized my choices"),
        Turn(
            speaker="ai",
            text="So your mother always criticized your choices. How did that affect you?",
        ),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.verbatimEchoRate > 0.0


def test_good_conversation_scores_higher():
    evaluator = QualityEvaluator()
    persona = Persona(
        name="Test",
        background="Test.",
        attachmentStyle=AttachmentStyle.Secure,
    )
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
        ConversationResult(turns=bad_turns, persona=persona)
    )
    good_result = evaluator.evaluate(
        ConversationResult(turns=good_turns, persona=persona)
    )
    assert good_result.score > bad_result.score


# --- Coverage Evaluator Tests ---


def test_coverage_detects_missing_categories():
    persona = Persona(
        name="Test",
        background="Test",
        attachmentStyle=AttachmentStyle.Secure,
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
        attachmentStyle=AttachmentStyle.Secure,
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
    persona = Persona(
        name="CoverageTest",
        background="Test background.",
        attachmentStyle=AttachmentStyle.DismissiveAvoidant,
        traits=[PersonaTrait.Evasive],
        dataPoints=[
            DataPoint(DataCategory.PresentingProblem, ["sleep", "anxiety"]),
            DataPoint(DataCategory.Mother, ["carol", "mother"]),
            DataPoint(DataCategory.Father, ["richard", "father"]),
            DataPoint(DataCategory.ParentsStatus, ["divorced"]),
            DataPoint(DataCategory.Siblings, ["michael", "brother"]),
            DataPoint(DataCategory.MaternalGrandparents, ["ruth", "harold"]),
            DataPoint(DataCategory.PaternalGrandparents, ["margaret", "george"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "linda"]),
            DataPoint(DataCategory.Spouse, ["david", "husband"]),
            DataPoint(DataCategory.Children, ["emma", "jake"]),
            DataPoint(DataCategory.NodalEvents, ["1997", "2018", "died"]),
        ],
    )
    # Coverage evaluator checks AI text only, so keywords must appear in AI turns
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
            text="How is your brother Michael? When did Ruth and Harold pass away?",
        ),
        Turn(speaker="user", text="Ruth died in 2018, Harold in 2010."),
        Turn(
            speaker="ai",
            text="So Ruth died in 2018. What about Margaret and George on your dad's side?",
        ),
        Turn(speaker="user", text="Margaret is 92, George died in 1995."),
        Turn(
            speaker="ai",
            text="Any aunts or uncles like Linda? How are David, Emma and Jake?",
        ),
        Turn(speaker="user", text="Aunt Linda is 65. David and the kids are good."),
    ]
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.coverageRate >= 0.9
    assert result.passed


def test_coverage_empty_datapoints():
    persona = Persona(
        name="Test",
        background="Test",
        attachmentStyle=AttachmentStyle.Secure,
        dataPoints=[],
    )
    turns = [Turn(speaker="ai", text="Hello")]
    evaluator = CoverageEvaluator()
    result = evaluator.evaluate(ConversationResult(turns=turns, persona=persona))
    assert result.coverageRate == 1.0
    assert result.passed


# --- Generate Persona Tests ---


@pytest.mark.e2e
def test_generate_persona(test_user, monkeypatch):
    from btcopilot.personal.models import SyntheticPersona

    mock_response = json.dumps(
        {
            "name": "TestGenerated",
            "background": "35-year-old woman, works as a nurse.\n\n**Parents:**\n- Mother: Karen (62)\n- Father: Bill (64)",
            "presenting_problem": "I haven't been sleeping well lately.",
            "data_points": [
                {"category": "presenting_problem", "keywords": ["sleep"]},
                {"category": "mother", "keywords": ["karen"]},
                {"category": "father", "keywords": ["bill"]},
            ],
        }
    )
    monkeypatch.setattr(
        "btcopilot.tests.personal.synthetic.gemini_text_sync",
        lambda *a, **kw: mock_response,
    )

    result = generate_persona(
        traits=[PersonaTrait.Evasive],
        attachment_style=AttachmentStyle.DismissiveAvoidant,
        sex="female",
        age=35,
    )
    assert isinstance(result, SyntheticPersona)
    assert result.name == "TestGenerated"
    assert result.sex == "female"
    assert result.age == 35

    persona = result.to_persona()
    assert persona.attachmentStyle == AttachmentStyle.DismissiveAvoidant
    assert PersonaTrait.Evasive in persona.traits
    assert len(persona.dataPoints) == 3

    # Cleanup
    db.session.delete(result)
    db.session.commit()


# --- E2E Tests ---


@pytest.mark.e2e
def test_coverage_in_live_conversation(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    persona = Persona(
        name="LiveCoverageTest",
        background=DEPRECATED_PERSONAS[0].background,
        attachmentStyle=AttachmentStyle.DismissiveAvoidant,
        traits=[PersonaTrait.Evasive, PersonaTrait.Defensive],
        presenting_problem="I haven't been sleeping well. My doctor said it might be stress but I don't know.",
        dataPoints=DEPRECATED_PERSONAS[0].dataPoints,
    )
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
        status = "+" if cat.covered else "-"
        _log.info(f"  {status} {cat.category.value}: {cat.matchedKeywords}")
    _log.info(f"Discussion ID: {result.discussionId}")
    _log.info(f"View at: http://127.0.0.1:8888/discussions/{result.discussionId}")
    _log.info(f"{'='*60}")

    assert result.coverage.passed, f"Coverage {result.coverage.coverageRate:.0%} < 70%"


@pytest.mark.e2e
def test_single_persona_conversation(test_user):
    logging.getLogger("btcopilot").setLevel(logging.INFO)

    persona = Persona(
        name="SingleTest",
        background="30-year-old, married, one child. Parents divorced when she was 12.",
        attachmentStyle=AttachmentStyle.AnxiousPreoccupied,
        traits=[PersonaTrait.Emotional],
        presenting_problem="I've been having a hard time lately. Not sure what's wrong.",
    )
    simulator = ConversationSimulator(max_turns=10)
    evaluator = QualityEvaluator()

    result = simulator.run(persona, ask)
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

    personas = [
        Persona(
            name=f"Suite{i}",
            background=DEPRECATED_PERSONAS[i].background,
            attachmentStyle=DEPRECATED_PERSONAS[i].attachmentStyle,
            traits=DEPRECATED_PERSONAS[i].traits,
            presenting_problem=DEPRECATED_PERSONAS[i].presenting_problem,
        )
        for i in range(len(DEPRECATED_PERSONAS))
    ]

    results = run_synthetic_tests(
        ask_fn=ask,
        personas=personas,
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
        name="RegressionTest",
        background="30-year-old, married, one child.",
        attachmentStyle=AttachmentStyle.DismissiveAvoidant,
        traits=[PersonaTrait.Terse],
        presenting_problem="Stress at work affecting sleep.",
    )

    simulator = ConversationSimulator(max_turns=8)
    evaluator = QualityEvaluator()

    result = simulator.run(persona, ask)
    result.quality = evaluator.evaluate(result)

    cliches = [p for p in result.quality.patterns if p.category == "therapist_cliche"]
    assert len(cliches) == 0, f"Found therapist cliches: {[p.text for p in cliches]}"

    for starter, count in result.quality.repetitiveStarters.items():
        assert count <= 3, f"Starter '{starter}' repeated {count} times"


@pytest.mark.e2e
@pytest.mark.chat_flow(response="Tell me about your family.")
def test_persist_synthetic_conversation(test_user):
    from btcopilot.pro.models import Diagram

    persona = Persona(
        name="TestPersist",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
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
    assert discussion.synthetic_persona["attachmentStyle"] == "secure"
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


@pytest.mark.e2e
@pytest.mark.chat_flow(response="Tell me about your family.")
def test_non_persist_cleans_up(test_user):
    initial_count = Discussion.query.filter_by(synthetic=True).count()

    persona = Persona(
        name="TestCleanup",
        background="Test background.",
        attachmentStyle=AttachmentStyle.Secure,
        traits=[PersonaTrait.Terse],
        presenting_problem="Test problem.",
    )

    simulator = ConversationSimulator(max_turns=2, persist=False)
    result = simulator.run(persona, ask)

    assert result.discussionId is None

    final_count = Discussion.query.filter_by(synthetic=True).count()
    assert final_count == initial_count
