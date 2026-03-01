"""
Synthetic User Testing Framework

This module provides tools for automated testing of conversational quality
using LLM-generated synthetic users with specific behavioral traits.

Key components:
- personas: User persona definitions and system prompts
- simulator: Conversation simulation loop
- evaluators: Quality evaluation metrics for detecting robotic patterns
- data_completeness: Data collection completeness evaluation
- conftest: pytest fixtures for synthetic testing
"""

from .personas import Persona, get_persona, get_all_personas
from .simulator import ConversationSimulator, SimulatedConversation
from .evaluators import (
    QualityEvaluator,
    RoboticPatternChecker,
    evaluate_conversation,
)
from .data_completeness import (
    DataCompletenessEvaluator,
    DataCompletenessScore,
    evaluate_data_completeness,
)

__all__ = [
    "Persona",
    "get_persona",
    "get_all_personas",
    "ConversationSimulator",
    "SimulatedConversation",
    "QualityEvaluator",
    "RoboticPatternChecker",
    "evaluate_conversation",
    "DataCompletenessEvaluator",
    "DataCompletenessScore",
    "evaluate_data_completeness",
]
