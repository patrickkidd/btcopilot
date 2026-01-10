"""
Pytest fixtures for synthetic user testing.
"""

import pytest
from unittest.mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.schema import PDP, PDPDeltas

from .personas import get_persona, get_all_personas
from .simulator import ConversationSimulator
from .evaluators import QualityEvaluator, RoboticPatternChecker
from .data_completeness import DataCompletenessEvaluator


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "synthetic: run synthetic conversation tests (requires --synthetic flag)",
    )
    config.addinivalue_line(
        "markers",
        "synthetic_llm: run synthetic tests with real LLM calls (costs money)",
    )


def pytest_addoption(parser):
    parser.addoption(
        "--synthetic",
        action="store_true",
        default=False,
        help="Run synthetic conversation tests",
    )
    parser.addoption(
        "--synthetic-llm",
        action="store_true",
        default=False,
        help="Run synthetic tests with real LLM calls (requires --synthetic)",
    )


@pytest.fixture(autouse=True)
def skip_synthetic(request):
    """Skip synthetic tests unless --synthetic flag is provided."""
    if request.node.get_closest_marker("synthetic"):
        if not request.config.getoption("--synthetic"):
            pytest.skip("need --synthetic option to run")

    if request.node.get_closest_marker("synthetic_llm"):
        if not request.config.getoption("--synthetic-llm"):
            pytest.skip("need --synthetic-llm option to run")


@pytest.fixture
def conversation_simulator():
    """Create a conversation simulator with default settings."""
    return ConversationSimulator(max_turns=15)


@pytest.fixture
def quality_evaluator():
    """Create a quality evaluator with default settings."""
    return QualityEvaluator(use_llm_judge=False)


@pytest.fixture
def pattern_checker():
    """Create a robotic pattern checker."""
    return RoboticPatternChecker()


@pytest.fixture
def data_completeness_evaluator():
    """Create a data completeness evaluator."""
    return DataCompletenessEvaluator()


@pytest.fixture
def all_personas():
    """Get all registered personas."""
    return get_all_personas()


@pytest.fixture
def evasive_persona():
    """Get the evasive persona."""
    return get_persona("evasive")


@pytest.fixture
def oversharer_persona():
    """Get the oversharer persona."""
    return get_persona("oversharer")


@pytest.fixture
def date_confused_persona():
    """Get the date confused persona."""
    return get_persona("date_confused")


@pytest.fixture
def emotionally_flooded_persona():
    """Get the emotionally flooded persona."""
    return get_persona("emotionally_flooded")


@pytest.fixture
def matter_of_fact_persona():
    """Get the matter of fact persona."""
    return get_persona("matter_of_fact")


@pytest.fixture
def discussion_factory(test_user):
    """Factory function to create fresh Discussion objects."""

    def _create_discussion():
        discussion = Discussion(user=test_user)
        db.session.add(discussion)
        db.session.commit()
        return discussion

    return _create_discussion


@pytest.fixture
def mock_synthetic_user():
    """
    Mock the synthetic user's LLM responses for deterministic testing.

    Yields a function that can be used to set predefined responses.
    """
    responses = []
    response_index = [0]

    def set_responses(new_responses: list[str]):
        responses.clear()
        responses.extend(new_responses)
        response_index[0] = 0

    def mock_completion(*args, **kwargs):
        from unittest.mock import MagicMock

        idx = response_index[0]
        if idx < len(responses):
            text = responses[idx]
            response_index[0] += 1
        else:
            text = "I think that covers most of my family."

        # Create mock response object
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = text
        return mock_response

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.completions.create = mock_completion
        yield set_responses


@pytest.fixture
def mock_chatbot_response():
    """
    Mock the chatbot's response for testing evaluators in isolation.

    Yields a function that can be used to set predefined responses.
    """
    responses = []
    response_index = [0]

    def set_responses(new_responses: list[str]):
        responses.clear()
        responses.extend(new_responses)
        response_index[0] = 0

    async def mock_pdp_update(*args, **kwargs):
        return (PDP(), PDPDeltas())

    def mock_generate_response(*args, **kwargs):
        idx = response_index[0]
        if idx < len(responses):
            text = responses[idx]
            response_index[0] += 1
        else:
            text = "Is there anything else you'd like to share about your family?"
        return text

    with patch("btcopilot.pdp.update", AsyncMock(side_effect=mock_pdp_update)):
        with patch(
            "btcopilot.personal.chat._generate_response", side_effect=mock_generate_response
        ):
            yield set_responses
