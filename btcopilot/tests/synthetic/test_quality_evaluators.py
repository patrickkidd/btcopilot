"""
Tests for the quality evaluation framework.

These tests verify that the evaluators correctly detect robotic patterns
without requiring actual LLM calls.
"""

import pytest

from btcopilot.tests.synthetic.evaluators import (
    RoboticPatternChecker,
    QualityEvaluator,
    PatternViolation,
)
from btcopilot.tests.synthetic.simulator import SimulatedConversation, Turn
from btcopilot.tests.synthetic.personas import Persona


@pytest.fixture
def test_persona():
    """A minimal test persona."""
    return Persona(
        id="test",
        name="Test User",
        description="Test persona",
        system_prompt="You are a test user.",
    )


class TestRoboticPatternChecker:
    """Tests for the RoboticPatternChecker class."""

    def test_detects_banned_phrases(self, pattern_checker):
        """Should detect banned therapist-speak phrases."""
        response = "It sounds like you're going through a difficult time."
        violations = pattern_checker.check_banned_phrases(response)

        assert len(violations) == 1
        assert violations[0].pattern_name == "banned_phrase"
        assert "it sounds like" in violations[0].content

    def test_detects_multiple_banned_phrases(self, pattern_checker):
        """Should detect multiple banned phrases in one response."""
        response = "That sounds hard. Tell me more about how that makes you feel."
        violations = pattern_checker.check_banned_phrases(response)

        assert len(violations) >= 2
        phrase_contents = [v.content for v in violations]
        assert "that sounds" in phrase_contents
        assert "tell me more" in phrase_contents

    def test_allows_clean_response(self, pattern_checker):
        """Should not flag responses without banned phrases."""
        response = "What's your mother's name and how old is she?"
        violations = pattern_checker.check_banned_phrases(response)

        assert len(violations) == 0

    def test_detects_repetition(self, pattern_checker):
        """Should detect repeated phrases across responses."""
        responses = [
            "What's your mother's name?",
            "And what's your father's name?",
            "What's your mother's age?",  # "what's your mother's" repeats
            "What's your mother's occupation?",
        ]
        violations, score = pattern_checker.check_repetition(responses)

        # Should detect the repeated "what's your mother's" phrase
        assert any(v.pattern_name == "repetition" for v in violations)
        assert score < 1.0

    def test_no_repetition_in_varied_responses(self, pattern_checker):
        """Should not flag varied responses as repetitive."""
        responses = [
            "What's your mother's name?",
            "How old is your father?",
            "Do you have any siblings?",
            "When did your parents meet?",
        ]
        violations, score = pattern_checker.check_repetition(responses)

        # No significant repetition
        repetition_violations = [v for v in violations if v.pattern_name == "repetition"]
        assert len(repetition_violations) == 0
        assert score > 0.8

    def test_detects_echoing(self, pattern_checker):
        """Should detect when bot parrots user's words."""
        user_message = "My mother has been sick for about six months now."
        assistant_response = "So your mother has been sick for about six months. How is she doing now?"

        violations = pattern_checker.check_echoing(user_message, assistant_response)

        assert len(violations) > 0
        assert violations[0].pattern_name == "echoing"

    def test_allows_non_echoing_response(self, pattern_checker):
        """Should not flag responses that don't echo."""
        user_message = "My mother died last year and I've been feeling really sad."
        assistant_response = "How old was she when she passed?"

        violations = pattern_checker.check_echoing(user_message, assistant_response)

        assert len(violations) == 0

    def test_detects_excessive_questions(self, pattern_checker):
        """Should flag responses with too many questions."""
        responses = [
            "What's your name? How old are you? Where do you live? What do you do?",
            "Another long response with many questions? Like this one? And this? And more?",
        ]
        violations, score = pattern_checker.check_question_balance(responses)

        assert any(v.pattern_name == "excessive_questions" for v in violations)
        assert score < 1.0

    def test_allows_reasonable_questions(self, pattern_checker):
        """Should not flag responses with 1-2 questions."""
        responses = [
            "What's your mother's name?",
            "How old is she? Is she still working?",
            "Do you have any siblings?",
        ]
        violations, score = pattern_checker.check_question_balance(responses)

        question_violations = [
            v for v in violations if v.pattern_name == "excessive_questions"
        ]
        assert len(question_violations) == 0
        assert score >= 0.8

    def test_detects_repetitive_openings(self, pattern_checker):
        """Should flag responses that always start the same way."""
        responses = [
            "I understand. What's your mother's name?",
            "I understand. How old is your father?",
            "I understand. Do you have siblings?",
            "I understand. When did this happen?",
        ]
        violations, score = pattern_checker.check_variety(responses)

        assert any(v.pattern_name == "repetitive_openings" for v in violations)
        assert score < 1.0

    def test_allows_varied_openings(self, pattern_checker):
        """Should not flag varied response openings."""
        responses = [
            "What's your mother's name?",
            "How old is your father?",
            "OK, do you have any siblings?",
            "Got it. When did this happen?",
        ]
        violations, score = pattern_checker.check_variety(responses)

        opening_violations = [
            v for v in violations if v.pattern_name == "repetitive_openings"
        ]
        assert len(opening_violations) == 0


class TestQualityEvaluator:
    """Tests for the QualityEvaluator class."""

    def test_evaluates_good_conversation(self, quality_evaluator, test_persona):
        """Should give high scores to natural conversations."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="Hi, I'm here because of family issues."),
                Turn(role="assistant", content="What's been going on?"),
                Turn(role="user", content="My parents are fighting a lot."),
                Turn(
                    role="assistant", content="How long has this been happening?"
                ),
                Turn(role="user", content="About six months."),
                Turn(
                    role="assistant",
                    content="What triggered it? Any major events around that time?",
                ),
            ],
        )

        score = quality_evaluator.evaluate(conversation)

        assert score.overall_score >= 0.7
        assert score.passed()
        assert score.banned_phrase_score >= 0.8
        assert score.echo_score >= 0.8

    def test_penalizes_robotic_conversation(self, quality_evaluator, test_persona):
        """Should give low scores to robotic conversations."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="I'm stressed about my family."),
                Turn(
                    role="assistant",
                    content="It sounds like you're stressed about your family. That must be hard. Tell me more.",
                ),
                Turn(role="user", content="My mother is sick."),
                Turn(
                    role="assistant",
                    content="It sounds like your mother being sick is difficult. How does that make you feel?",
                ),
                Turn(role="user", content="I feel sad."),
                Turn(
                    role="assistant",
                    content="It sounds like you feel sad. That makes sense. Tell me more about that.",
                ),
            ],
        )

        score = quality_evaluator.evaluate(conversation)

        assert score.overall_score < 0.7
        assert not score.passed()
        assert len(score.violations) > 0
        # Should have banned phrase violations
        banned_violations = [
            v for v in score.violations if v.pattern_name == "banned_phrase"
        ]
        assert len(banned_violations) > 0

    def test_summary_generation(self, quality_evaluator, test_persona):
        """Should generate readable summary."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="Hello"),
                Turn(role="assistant", content="Hi there. What brings you in?"),
            ],
        )

        score = quality_evaluator.evaluate(conversation)
        summary = score.summary()

        assert "Quality Score" in summary
        assert "Repetition" in summary
        assert "Echo" in summary
        assert "Variety" in summary


class TestQualityRegressions:
    """
    Regression tests for specific robotic behaviors that have been observed
    and should be caught by the evaluators.
    """

    def test_regression_it_sounds_like(self, pattern_checker):
        """Regression: 'It sounds like...' should always be flagged."""
        variants = [
            "It sounds like you're going through a lot.",
            "it sounds like this is hard for you.",
            "IT SOUNDS LIKE you need support.",
        ]
        for response in variants:
            violations = pattern_checker.check_banned_phrases(response)
            assert len(violations) > 0, f"Should flag: {response}"

    def test_regression_that_must_be(self, pattern_checker):
        """Regression: 'That must be...' should be flagged."""
        variants = [
            "That must be difficult.",
            "that must be frustrating.",
            "That must be really hard for you.",
        ]
        for response in variants:
            violations = pattern_checker.check_banned_phrases(response)
            assert len(violations) > 0, f"Should flag: {response}"

    def test_regression_tell_me_more(self, pattern_checker):
        """Regression: 'Tell me more' should be flagged."""
        variants = [
            "Tell me more about that.",
            "Can you tell me more?",
            "Tell me more.",
        ]
        for response in variants:
            violations = pattern_checker.check_banned_phrases(response)
            assert len(violations) > 0, f"Should flag: {response}"

    def test_regression_verbatim_echo(self, pattern_checker):
        """Regression: Verbatim echoing of significant phrases should be flagged."""
        user = "I've been having panic attacks since my mother died."
        # Bot echoes the exact phrase
        response = "You've been having panic attacks since your mother died. When did she pass?"

        violations = pattern_checker.check_echoing(user, response)
        assert len(violations) > 0

    def test_regression_question_spam(self, pattern_checker):
        """Regression: More than 3 questions in one response should be flagged."""
        response = (
            "What's your mom's name? How old is she? Is she still working? "
            "Does she live nearby? Do you see her often?"
        )

        violations, score = pattern_checker.check_question_balance([response])
        assert len(violations) > 0
        assert score < 0.8
