"""
Synthetic conversation tests.

These tests run simulated conversations between the chatbot and synthetic users,
then evaluate the quality of the chatbot's responses.

Run with: pytest --synthetic tests/synthetic/
Run with real LLM: pytest --synthetic --synthetic-llm tests/synthetic/
"""

import pytest
import logging

from btcopilot.tests.synthetic.personas import get_persona, get_all_personas
from btcopilot.tests.synthetic.simulator import ConversationSimulator
from btcopilot.tests.synthetic.evaluators import QualityEvaluator, evaluate_conversation

_log = logging.getLogger(__name__)


@pytest.mark.synthetic_llm
class TestSyntheticConversations:
    """
    Full synthetic conversation tests with real LLM calls.

    These tests simulate complete conversations with different user personas
    and evaluate the chatbot's response quality.
    """

    def test_evasive_persona(
        self, conversation_simulator, quality_evaluator, discussion_factory, evasive_persona
    ):
        """Test conversation with an evasive user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=evasive_persona,
            discussion=discussion,
            opening_message="I'm not really sure why I'm here. My husband thought it would help.",
        )

        score = quality_evaluator.evaluate(conversation)
        _log.info(f"Evasive persona score:\n{score.summary()}")
        _log.info(f"Conversation:\n{conversation.conversation_text()}")

        # Conversation should complete
        assert conversation.completed
        assert conversation.turn_count >= 4

        # Quality should be acceptable
        assert score.overall_score >= 0.5, f"Quality too low:\n{score.summary()}"

    def test_oversharer_persona(
        self,
        conversation_simulator,
        quality_evaluator,
        discussion_factory,
        oversharer_persona,
    ):
        """Test conversation with an oversharing user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=oversharer_persona,
            discussion=discussion,
            opening_message=(
                "Oh man, where do I start? My kid Jake is failing school and smoking pot, "
                "Linda thinks I'm too hard on him but she doesn't understand because her dad "
                "was never around, and my father just had a stroke..."
            ),
        )

        score = quality_evaluator.evaluate(conversation)
        _log.info(f"Oversharer persona score:\n{score.summary()}")
        _log.info(f"Conversation:\n{conversation.conversation_text()}")

        assert conversation.completed
        assert conversation.turn_count >= 4
        assert score.overall_score >= 0.5, f"Quality too low:\n{score.summary()}"

    def test_date_confused_persona(
        self,
        conversation_simulator,
        quality_evaluator,
        discussion_factory,
        date_confused_persona,
    ):
        """Test conversation with a date-confused user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=date_confused_persona,
            discussion=discussion,
            opening_message="I've been struggling since my husband passed. It was... two years ago? Maybe three.",
        )

        score = quality_evaluator.evaluate(conversation)
        _log.info(f"Date confused persona score:\n{score.summary()}")
        _log.info(f"Conversation:\n{conversation.conversation_text()}")

        assert conversation.completed
        assert score.overall_score >= 0.5, f"Quality too low:\n{score.summary()}"

    def test_emotionally_flooded_persona(
        self,
        conversation_simulator,
        quality_evaluator,
        discussion_factory,
        emotionally_flooded_persona,
    ):
        """Test conversation with an emotionally flooded user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=emotionally_flooded_persona,
            discussion=discussion,
            opening_message="I just... I can't stop thinking about Emma. Two months and I still can't sleep.",
        )

        score = quality_evaluator.evaluate(conversation)
        _log.info(f"Emotionally flooded persona score:\n{score.summary()}")
        _log.info(f"Conversation:\n{conversation.conversation_text()}")

        assert conversation.completed
        assert score.overall_score >= 0.5, f"Quality too low:\n{score.summary()}"

    def test_matter_of_fact_persona(
        self,
        conversation_simulator,
        quality_evaluator,
        discussion_factory,
        matter_of_fact_persona,
    ):
        """Test conversation with a matter-of-fact user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=matter_of_fact_persona,
            discussion=discussion,
            opening_message="My son Ryan, 24, moved back home. It's causing tension with my husband Tom.",
        )

        score = quality_evaluator.evaluate(conversation)
        _log.info(f"Matter of fact persona score:\n{score.summary()}")
        _log.info(f"Conversation:\n{conversation.conversation_text()}")

        assert conversation.completed
        assert score.overall_score >= 0.5, f"Quality too low:\n{score.summary()}"


@pytest.mark.synthetic_llm
class TestSyntheticBatch:
    """Test running batch conversations across all personas."""

    def test_batch_all_personas(self, discussion_factory):
        """Run one conversation with each persona and report aggregate quality."""
        simulator = ConversationSimulator(max_turns=10)
        evaluator = QualityEvaluator(use_llm_judge=False)

        personas = get_all_personas()
        results = simulator.run_batch(
            personas=personas,
            discussion_factory=discussion_factory,
            conversations_per_persona=1,
        )

        scores = []
        for conversation in results:
            score = evaluator.evaluate(conversation)
            scores.append(score)
            _log.info(f"\n=== {conversation.persona.name} ({conversation.persona.id}) ===")
            _log.info(score.summary())

        # Aggregate stats
        avg_score = sum(s.overall_score for s in scores) / len(scores)
        passed = sum(1 for s in scores if s.passed())

        _log.info(f"\n=== AGGREGATE RESULTS ===")
        _log.info(f"Average score: {avg_score:.2f}")
        _log.info(f"Passed: {passed}/{len(scores)}")

        # At least half should pass
        assert passed >= len(scores) // 2, f"Too many failures: {passed}/{len(scores)} passed"


@pytest.mark.synthetic
class TestSyntheticMocked:
    """
    Synthetic tests with mocked LLM responses for faster CI runs.

    These verify the simulation loop works correctly without actual API calls.
    """

    def test_simulation_loop_completes(
        self,
        mock_chatbot_response,
        mock_synthetic_user,
        discussion_factory,
        evasive_persona,
    ):
        """Test that the simulation loop runs to completion with mocks."""
        # Set up mock responses
        mock_chatbot_response(
            [
                "What brings you in today?",
                "How long has this been going on?",
                "What's your mom's name?",
                "And your dad?",
            ]
        )
        mock_synthetic_user(
            [
                "I guess my husband thought it would help.",
                "A few months, maybe longer.",
                "Her name is Helen. She's... I don't know, around 65?",
                "Frank. He's a few years older.",
                "I think that covers most of my family.",
            ]
        )

        discussion = discussion_factory()
        simulator = ConversationSimulator(max_turns=5)

        conversation = simulator.run(
            persona=evasive_persona,
            discussion=discussion,
            opening_message="I'm not really sure why I'm here.",
        )

        assert conversation.completed
        assert conversation.turn_count >= 2

    def test_quality_evaluation_with_mocked_conversation(
        self,
        quality_evaluator,
        mock_chatbot_response,
        mock_synthetic_user,
        discussion_factory,
        evasive_persona,
    ):
        """Test quality evaluation works with mocked conversation."""
        # Good responses (no robotic patterns)
        mock_chatbot_response(
            [
                "What's been going on?",
                "When did this start?",
                "What's your mother's name and age?",
                "Any siblings?",
            ]
        )
        mock_synthetic_user(
            [
                "Family stuff, I guess.",
                "A while ago.",
                "Helen, she's about 65.",
                "One brother, Tom.",
                "That's everyone.",
            ]
        )

        discussion = discussion_factory()
        simulator = ConversationSimulator(max_turns=5)

        conversation = simulator.run(
            persona=evasive_persona,
            discussion=discussion,
            opening_message="My husband suggested I come.",
        )

        score = quality_evaluator.evaluate(conversation)

        # Should score well since responses are clean
        assert score.banned_phrase_score >= 0.8
        assert score.echo_score >= 0.8

    def test_detects_poor_quality_with_mocked_conversation(
        self,
        quality_evaluator,
        mock_chatbot_response,
        mock_synthetic_user,
        discussion_factory,
        evasive_persona,
    ):
        """Test that poor quality responses are detected."""
        # Bad responses (full of robotic patterns)
        mock_chatbot_response(
            [
                "It sounds like you're going through a difficult time. Tell me more.",
                "That must be hard. How does that make you feel?",
                "It sounds like your family situation is challenging. Tell me more about that.",
            ]
        )
        mock_synthetic_user(
            [
                "I guess so.",
                "Sad, I suppose.",
                "That's about it.",
            ]
        )

        discussion = discussion_factory()
        simulator = ConversationSimulator(max_turns=3)

        conversation = simulator.run(
            persona=evasive_persona,
            discussion=discussion,
            opening_message="Things have been rough.",
        )

        score = quality_evaluator.evaluate(conversation)

        # Should have violations
        assert len(score.violations) > 0
        assert score.banned_phrase_score < 1.0

        # Check specific violations are detected
        violation_names = [v.pattern_name for v in score.violations]
        assert "banned_phrase" in violation_names
