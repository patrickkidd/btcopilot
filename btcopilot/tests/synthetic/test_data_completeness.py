"""
Tests for data collection completeness evaluation.

These tests verify that conversations collect the required family data
as defined in the data_requirements module.
"""

import pytest

from btcopilot.personal.data_requirements import (
    ALL_REQUIREMENTS,
    MINIMUM_COMPLETE_REQUIREMENTS,
    RequirementCategory,
    generate_checklist_markdown,
    generate_completion_criteria_markdown,
)
from btcopilot.tests.synthetic.data_completeness import (
    DataCompletenessEvaluator,
    DataCompletenessScore,
    CompletionStatus,
    evaluate_data_completeness,
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


class TestDataRequirements:
    """Tests for the data requirements module."""

    def test_all_requirements_have_ids(self):
        """All requirements should have unique IDs."""
        ids = [r.id for r in ALL_REQUIREMENTS]
        assert len(ids) == len(set(ids)), "Duplicate requirement IDs found"

    def test_all_requirements_have_descriptions(self):
        """All requirements should have descriptions."""
        for req in ALL_REQUIREMENTS:
            assert req.description, f"Requirement {req.id} missing description"

    def test_all_requirements_have_categories(self):
        """All requirements should have valid categories."""
        for req in ALL_REQUIREMENTS:
            assert isinstance(
                req.category, RequirementCategory
            ), f"Requirement {req.id} has invalid category"

    def test_minimum_requirements_reference_valid_ids(self):
        """Minimum requirements should reference valid requirement IDs."""
        valid_ids = {r.id for r in ALL_REQUIREMENTS}
        for group, req_ids in MINIMUM_COMPLETE_REQUIREMENTS.items():
            for req_id in req_ids:
                assert (
                    req_id in valid_ids
                ), f"Minimum requirement '{req_id}' in group '{group}' not found"

    def test_generate_checklist_markdown(self):
        """Should generate valid markdown checklist."""
        markdown = generate_checklist_markdown()

        # Should have header
        assert "**Required Data Checklist:**" in markdown

        # Should have all categories
        assert "Presenting Problem" in markdown
        assert "Family of Origin" in markdown
        assert "Extended Family" in markdown

        # Should have checkboxes
        assert "- [ ]" in markdown

    def test_generate_completion_criteria_markdown(self):
        """Should generate completion criteria text."""
        markdown = generate_completion_criteria_markdown()

        assert 'data collection "done"' in markdown
        assert "presenting problem" in markdown
        assert "parents" in markdown
        assert "grandparents" in markdown


class TestDataCompletenessEvaluator:
    """Tests for the data completeness evaluator."""

    def test_evaluates_complete_conversation(
        self, data_completeness_evaluator, test_persona
    ):
        """Should recognize a complete conversation."""
        # Build a conversation with all key data points
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="I've been having panic attacks for 6 months."),
                Turn(role="assistant", content="When did they start?"),
                Turn(
                    role="user",
                    content="About 6 months ago, right after my mom Helen died.",
                ),
                Turn(role="assistant", content="How old was your mom?"),
                Turn(role="user", content="She was 65. Dad is Richard, he's 68."),
                Turn(role="assistant", content="Are your parents together?"),
                Turn(
                    role="user",
                    content="They were married until mom died. Dad remarried quickly.",
                ),
                Turn(role="assistant", content="Do you have any siblings?"),
                Turn(role="user", content="Yes, my brother Tom is 31."),
                Turn(role="assistant", content="What about your grandparents?"),
                Turn(
                    role="user",
                    content="Grandma Rose on mom's side passed away. Grandpa Joe is 85. "
                    "On dad's side, both grandparents passed years ago.",
                ),
                Turn(role="assistant", content="Are you married?"),
                Turn(
                    role="user",
                    content="Yes, my husband Mark is 36. We got married in 2018. No kids.",
                ),
            ],
        )

        # Use heuristics (no LLM) for this test
        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        # Should have collected most key data
        assert score.presenting_problem_score > 0.5
        assert score.family_of_origin_score > 0.5
        assert score.overall_score > 0.5

    def test_evaluates_incomplete_conversation(
        self, data_completeness_evaluator, test_persona
    ):
        """Should recognize an incomplete conversation."""
        # Short conversation with minimal data
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="I'm stressed."),
                Turn(role="assistant", content="What's causing the stress?"),
                Turn(role="user", content="Work stuff."),
                Turn(role="assistant", content="How long has this been going on?"),
                Turn(role="user", content="A while."),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        # Should have low scores for most categories
        assert score.family_of_origin_score < 0.5
        assert score.extended_family_score < 0.5
        assert not score.minimum_complete

    def test_summary_generation(self, data_completeness_evaluator, test_persona):
        """Should generate readable summary."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="My mom Helen is 65."),
                Turn(role="assistant", content="And your dad?"),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)
        summary = score.summary()

        assert "Data Collection" in summary
        assert "Required:" in summary
        assert "Category Scores:" in summary


class TestHeuristicEvaluation:
    """Tests for heuristic-based evaluation without LLM."""

    def test_detects_mother_mention(self, data_completeness_evaluator, test_persona):
        """Should detect mother being mentioned."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="My mom Helen is doing well."),
                Turn(role="assistant", content="Good to hear."),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        # Should have detected mother
        mother_results = [
            r for r in score.results if r.requirement.id == "mother_name"
        ]
        assert len(mother_results) > 0
        assert mother_results[0].status == CompletionStatus.COLLECTED

    def test_detects_father_mention(self, data_completeness_evaluator, test_persona):
        """Should detect father being mentioned."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="My dad Richard is 68 years old."),
                Turn(role="assistant", content="OK."),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        father_results = [
            r for r in score.results if r.requirement.id == "father_name"
        ]
        assert len(father_results) > 0
        assert father_results[0].status == CompletionStatus.COLLECTED

    def test_detects_siblings_mention(self, data_completeness_evaluator, test_persona):
        """Should detect siblings being mentioned."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(
                    role="user", content="I have a brother Tom and a sister Amy."
                ),
                Turn(role="assistant", content="How old are they?"),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        sibling_results = [
            r for r in score.results if r.requirement.id == "siblings"
        ]
        assert len(sibling_results) > 0
        assert sibling_results[0].status == CompletionStatus.COLLECTED

    def test_detects_grandparents_mention(
        self, data_completeness_evaluator, test_persona
    ):
        """Should detect grandparents being mentioned."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(
                    role="user",
                    content="My grandmother Rose died last year. Grandfather Joe is still alive.",
                ),
                Turn(role="assistant", content="I'm sorry to hear about Rose."),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        grandparent_results = [
            r for r in score.results if r.requirement.id == "grandparents"
        ]
        assert len(grandparent_results) > 0
        assert grandparent_results[0].status == CompletionStatus.COLLECTED

    def test_detects_spouse_mention(self, data_completeness_evaluator, test_persona):
        """Should detect spouse being mentioned."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(
                    role="user",
                    content="My husband Mark thinks I should talk to someone.",
                ),
                Turn(role="assistant", content="What does Mark think is going on?"),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=False)

        spouse_results = [r for r in score.results if r.requirement.id == "spouse"]
        assert len(spouse_results) > 0
        assert spouse_results[0].status == CompletionStatus.COLLECTED


@pytest.mark.synthetic_llm
class TestLLMBasedEvaluation:
    """Tests for LLM-based data completeness evaluation."""

    def test_llm_evaluates_complete_conversation(
        self, data_completeness_evaluator, test_persona
    ):
        """Should use LLM to evaluate comprehensive conversation."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(
                    role="user",
                    content="I've been having panic attacks since my mother Helen died 8 months ago.",
                ),
                Turn(role="assistant", content="I'm sorry. When did the attacks start?"),
                Turn(
                    role="user",
                    content="About 2 months after she passed. Dad Richard, he's 68, remarried quickly.",
                ),
                Turn(role="assistant", content="How has that been?"),
                Turn(
                    role="user",
                    content="Hard. My brother Tom (31) handles it better than me. My husband Mark (36) is worried.",
                ),
                Turn(role="assistant", content="What about your grandparents?"),
                Turn(
                    role="user",
                    content="Grandma Rose on mom's side died. Grandpa Joe is 85. "
                    "Dad's parents both passed when I was young.",
                ),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=True)

        # LLM should recognize the complete data
        assert score.presenting_problem_score > 0.6
        assert score.family_of_origin_score > 0.6
        assert score.extended_family_score > 0.4

    def test_llm_identifies_missing_data(
        self, data_completeness_evaluator, test_persona
    ):
        """Should identify what data is missing."""
        conversation = SimulatedConversation(
            persona=test_persona,
            turns=[
                Turn(role="user", content="Work has been stressful lately."),
                Turn(role="assistant", content="What's been going on at work?"),
                Turn(role="user", content="Just a lot of pressure from the boss."),
            ],
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=True)

        # Should have missing required items
        assert len(score.missing_required) > 0
        # Family data should be largely missing
        assert score.family_of_origin_score < 0.3


@pytest.mark.synthetic_llm
class TestSyntheticConversationDataCollection:
    """
    Integration tests that run full synthetic conversations and evaluate
    whether enough family data was collected.
    """

    def test_evasive_persona_data_collection(
        self,
        conversation_simulator,
        data_completeness_evaluator,
        discussion_factory,
        evasive_persona,
    ):
        """Test that we can collect data from an evasive user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=evasive_persona,
            discussion=discussion,
            opening_message="I'm not really sure why I'm here. My husband thought it would help.",
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=True)

        print(f"\n=== Evasive Persona Data Collection ===")
        print(score.summary())
        print(f"\nConversation ({conversation.turn_count} turns):")
        print(conversation.conversation_text())

        # Should collect at least some core data despite evasiveness
        assert score.presenting_problem_score > 0.3, "Should understand presenting problem"

    def test_oversharer_persona_data_collection(
        self,
        conversation_simulator,
        data_completeness_evaluator,
        discussion_factory,
        oversharer_persona,
    ):
        """Test data collection from an oversharing user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=oversharer_persona,
            discussion=discussion,
            opening_message=(
                "Oh man, where do I start? My kid Jake is failing school, "
                "Linda thinks I'm too hard on him, and my dad just had a stroke..."
            ),
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=True)

        print(f"\n=== Oversharer Persona Data Collection ===")
        print(score.summary())

        # Oversharer should provide lots of data
        assert score.family_of_origin_score > 0.4, "Should collect family of origin data"

    def test_matter_of_fact_persona_data_collection(
        self,
        conversation_simulator,
        data_completeness_evaluator,
        discussion_factory,
        matter_of_fact_persona,
    ):
        """Test data collection from a matter-of-fact user."""
        discussion = discussion_factory()

        conversation = conversation_simulator.run(
            persona=matter_of_fact_persona,
            discussion=discussion,
            opening_message="My son Ryan, 24, moved back home. It's causing tension with my husband Tom.",
        )

        score = data_completeness_evaluator.evaluate(conversation, use_llm=True)

        print(f"\n=== Matter of Fact Persona Data Collection ===")
        print(score.summary())

        # Matter of fact users give clear data
        assert score.overall_score > 0.4, "Should collect substantial data"

    def test_batch_data_collection_across_personas(
        self,
        conversation_simulator,
        data_completeness_evaluator,
        discussion_factory,
        all_personas,
    ):
        """Test data collection across all personas."""
        results = conversation_simulator.run_batch(
            personas=all_personas,
            discussion_factory=discussion_factory,
            conversations_per_persona=1,
        )

        scores = []
        for conversation in results:
            score = data_completeness_evaluator.evaluate(conversation, use_llm=True)
            scores.append((conversation.persona.id, score))

            print(f"\n=== {conversation.persona.name} ({conversation.persona.id}) ===")
            print(score.summary())

        # Calculate aggregate stats
        avg_overall = sum(s.overall_score for _, s in scores) / len(scores)
        avg_problem = sum(s.presenting_problem_score for _, s in scores) / len(scores)
        avg_family = sum(s.family_of_origin_score for _, s in scores) / len(scores)

        print(f"\n=== AGGREGATE DATA COLLECTION RESULTS ===")
        print(f"Average overall: {avg_overall:.0%}")
        print(f"Average presenting problem: {avg_problem:.0%}")
        print(f"Average family of origin: {avg_family:.0%}")

        # At least the presenting problem should be understood
        assert avg_problem > 0.3, "Should understand presenting problems across personas"
