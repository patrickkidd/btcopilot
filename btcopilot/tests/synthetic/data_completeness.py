"""
Data Completeness Evaluator

Evaluates whether a conversation has collected enough family data
to be considered complete according to the data collection requirements.

Uses LLM to analyze conversation content against structured requirements.
"""

import os
import logging
from dataclasses import dataclass, field
from enum import Enum

from btcopilot.schema import PDP
from btcopilot.personal.data_requirements import (
    DataRequirement,
    RequirementCategory,
    MINIMUM_COMPLETE_REQUIREMENTS,
    ALL_REQUIREMENTS,
    get_requirements_by_category,
)

from .simulator import SimulatedConversation

_log = logging.getLogger(__name__)


class CompletionStatus(Enum):
    """Status of a requirement."""

    NOT_COLLECTED = "not_collected"
    PARTIALLY_COLLECTED = "partially_collected"
    COLLECTED = "collected"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class RequirementResult:
    """Result of evaluating a single requirement."""

    requirement: DataRequirement
    status: CompletionStatus
    evidence: str | None = None  # Quote from conversation showing collection
    confidence: float = 0.0  # 0.0-1.0


@dataclass
class DataCompletenessScore:
    """Results of evaluating data collection completeness."""

    results: list[RequirementResult] = field(default_factory=list)

    # Summary scores by category
    presenting_problem_score: float = 0.0
    family_of_origin_score: float = 0.0
    extended_family_score: float = 0.0
    own_family_score: float = 0.0
    nodal_events_score: float = 0.0

    # Overall metrics
    required_collected: int = 0
    required_total: int = 0
    optional_collected: int = 0
    optional_total: int = 0

    # Is minimum requirement met?
    minimum_complete: bool = False

    # Details about what's missing
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Overall completion score (0.0-1.0)."""
        if self.required_total == 0:
            return 1.0
        return self.required_collected / self.required_total

    def passed(self, threshold: float = 0.7) -> bool:
        """Check if data collection passes threshold."""
        return self.overall_score >= threshold

    def summary(self) -> str:
        """Get human-readable summary."""
        status = "COMPLETE" if self.minimum_complete else "INCOMPLETE"
        lines = [
            f"Data Collection: {self.overall_score:.0%} ({status})",
            f"  Required: {self.required_collected}/{self.required_total}",
            f"  Optional: {self.optional_collected}/{self.optional_total}",
            "",
            "Category Scores:",
            f"  Presenting Problem: {self.presenting_problem_score:.0%}",
            f"  Family of Origin: {self.family_of_origin_score:.0%}",
            f"  Extended Family: {self.extended_family_score:.0%}",
            f"  Own Family: {self.own_family_score:.0%}",
            f"  Nodal Events: {self.nodal_events_score:.0%}",
        ]

        if self.missing_required:
            lines.append("")
            lines.append("Missing Required:")
            for item in self.missing_required[:5]:
                lines.append(f"  - {item}")

        return "\n".join(lines)


class DataCompletenessEvaluator:
    """
    Evaluates whether a conversation collected enough family data.

    Uses LLM analysis to determine what data was collected based on
    conversation content, then compares against requirements.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """
        Initialize the evaluator.

        Args:
            llm_model: Model to use for analysis
        """
        self.llm_model = llm_model

    def evaluate(
        self,
        conversation: SimulatedConversation,
        use_llm: bool = True,
    ) -> DataCompletenessScore:
        """
        Evaluate data collection completeness.

        Args:
            conversation: The conversation to evaluate
            use_llm: Whether to use LLM for analysis (False uses heuristics)

        Returns:
            DataCompletenessScore with detailed results
        """
        if use_llm:
            return self._evaluate_with_llm(conversation)
        else:
            return self._evaluate_with_heuristics(conversation)

    def _evaluate_with_llm(
        self, conversation: SimulatedConversation
    ) -> DataCompletenessScore:
        """Use LLM to analyze what data was collected."""
        import openai
        import json

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # Build the prompt with requirements
        requirements_list = []
        for req in ALL_REQUIREMENTS:
            requirements_list.append(
                {
                    "id": req.id,
                    "description": req.description,
                    "category": req.category.value,
                    "required": req.required,
                }
            )

        prompt = f"""Analyze this conversation to determine what family data was collected.

For each requirement, determine:
- "collected": The information was clearly provided
- "partially_collected": Some related info was given but incomplete
- "not_collected": This information was not gathered
- "not_applicable": Doesn't apply (e.g., "spouse" for unmarried person)

Conversation:
{conversation.conversation_text()}

Requirements to check:
{json.dumps(requirements_list, indent=2)}

Respond with JSON only:
{{
  "results": [
    {{
      "id": "requirement_id",
      "status": "collected|partially_collected|not_collected|not_applicable",
      "evidence": "quote from conversation if collected",
      "confidence": 0.0-1.0
    }}
  ],
  "is_partnered": true/false,
  "has_children": true/false
}}"""

        try:
            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            analysis = json.loads(response.choices[0].message.content)
            return self._build_score_from_analysis(analysis, conversation)

        except Exception as e:
            _log.warning(f"LLM analysis failed: {e}, falling back to heuristics")
            return self._evaluate_with_heuristics(conversation)

    def _evaluate_with_heuristics(
        self, conversation: SimulatedConversation
    ) -> DataCompletenessScore:
        """Use simple heuristics to estimate data collection."""
        score = DataCompletenessScore()
        conversation_text = conversation.conversation_text().lower()

        # Simple keyword-based heuristics
        heuristic_checks = {
            "problem_description": [
                "problem",
                "issue",
                "struggling",
                "difficult",
                "trouble",
                "anxiety",
                "panic",
                "depression",
                "stressed",
                "conflict",
                "fighting",
                "worried",
                "symptoms",
            ],
            "problem_onset": [
                "started",
                "began",
                "since",
                "months ago",
                "years ago",
                "for 6 months",
                "for a year",
                "recently",
                "last year",
            ],
            "problem_people_involved": [
                "involved",
                "between",
                "with my",
                "and my",
                "affects",
                "me and",
            ],
            "mother_name": ["mom", "mother", "mama", "helen", "mary", "nancy"],
            "mother_age_status": ["years old", "age", "died", "passed", "deceased", "65", "60"],
            "father_name": ["dad", "father", "papa", "richard", "tom", "mike"],
            "father_age_status": ["years old", "age", "died", "passed", "deceased", "68", "70"],
            "parents_status": [
                "married",
                "divorced",
                "separated",
                "together",
                "remarried",
                "still together",
            ],
            "siblings": ["brother", "sister", "sibling", "only child", "brothers", "sisters"],
            "grandparents": ["grandmother", "grandfather", "grandma", "grandpa", "grandparents"],
            "spouse": ["husband", "wife", "spouse", "partner", "married to", "we got married"],
            "children": ["son", "daughter", "child", "kids", "no kids", "no children"],
        }

        req_lookup = {r.id: r for r in ALL_REQUIREMENTS}

        for req_id, keywords in heuristic_checks.items():
            if req_id in req_lookup:
                req = req_lookup[req_id]
                found = any(kw in conversation_text for kw in keywords)
                status = CompletionStatus.COLLECTED if found else CompletionStatus.NOT_COLLECTED
                score.results.append(
                    RequirementResult(
                        requirement=req,
                        status=status,
                        confidence=0.5 if found else 0.0,
                    )
                )

        # Calculate scores
        self._calculate_category_scores(score)
        self._check_minimum_complete(score)

        return score

    def _build_score_from_analysis(
        self, analysis: dict, conversation: SimulatedConversation
    ) -> DataCompletenessScore:
        """Build score from LLM analysis results."""
        score = DataCompletenessScore()
        req_lookup = {r.id: r for r in ALL_REQUIREMENTS}

        status_map = {
            "collected": CompletionStatus.COLLECTED,
            "partially_collected": CompletionStatus.PARTIALLY_COLLECTED,
            "not_collected": CompletionStatus.NOT_COLLECTED,
            "not_applicable": CompletionStatus.NOT_APPLICABLE,
        }

        for result in analysis.get("results", []):
            req_id = result.get("id")
            if req_id in req_lookup:
                req = req_lookup[req_id]
                status_str = result.get("status", "not_collected")
                status = status_map.get(status_str, CompletionStatus.NOT_COLLECTED)

                score.results.append(
                    RequirementResult(
                        requirement=req,
                        status=status,
                        evidence=result.get("evidence"),
                        confidence=result.get("confidence", 0.0),
                    )
                )

        self._calculate_category_scores(score)
        self._check_minimum_complete(score)

        return score

    def _calculate_category_scores(self, score: DataCompletenessScore) -> None:
        """Calculate per-category and overall scores."""
        category_counts = {}
        for cat in RequirementCategory:
            category_counts[cat] = {"collected": 0, "total": 0}

        for result in score.results:
            cat = result.requirement.category
            is_collected = result.status in (
                CompletionStatus.COLLECTED,
                CompletionStatus.PARTIALLY_COLLECTED,
            )
            is_applicable = result.status != CompletionStatus.NOT_APPLICABLE

            if is_applicable:
                if result.requirement.required:
                    score.required_total += 1
                    if is_collected:
                        score.required_collected += 1
                    else:
                        score.missing_required.append(result.requirement.description)
                else:
                    score.optional_total += 1
                    if is_collected:
                        score.optional_collected += 1
                    else:
                        score.missing_optional.append(result.requirement.description)

                category_counts[cat]["total"] += 1
                if is_collected:
                    category_counts[cat]["collected"] += 1

        # Calculate category scores
        def cat_score(cat: RequirementCategory) -> float:
            counts = category_counts[cat]
            if counts["total"] == 0:
                return 1.0
            return counts["collected"] / counts["total"]

        score.presenting_problem_score = cat_score(RequirementCategory.PRESENTING_PROBLEM)
        score.family_of_origin_score = cat_score(RequirementCategory.FAMILY_OF_ORIGIN)
        score.extended_family_score = cat_score(RequirementCategory.EXTENDED_FAMILY)
        score.own_family_score = cat_score(RequirementCategory.OWN_FAMILY)
        score.nodal_events_score = cat_score(RequirementCategory.NODAL_EVENTS)

    def _check_minimum_complete(self, score: DataCompletenessScore) -> None:
        """Check if minimum requirements are met."""
        collected_ids = {
            r.requirement.id
            for r in score.results
            if r.status
            in (CompletionStatus.COLLECTED, CompletionStatus.PARTIALLY_COLLECTED)
        }

        # Check each minimum requirement group
        checks_passed = 0
        total_checks = len(MINIMUM_COMPLETE_REQUIREMENTS)

        for group_name, req_ids in MINIMUM_COMPLETE_REQUIREMENTS.items():
            group_collected = sum(1 for rid in req_ids if rid in collected_ids)
            # Consider group passed if at least 60% collected
            if group_collected >= len(req_ids) * 0.6:
                checks_passed += 1

        score.minimum_complete = checks_passed >= total_checks * 0.7


def evaluate_data_completeness(
    conversation: SimulatedConversation,
    use_llm: bool = True,
) -> DataCompletenessScore:
    """
    Convenience function to evaluate data collection completeness.

    Args:
        conversation: The conversation to evaluate
        use_llm: Whether to use LLM for analysis

    Returns:
        DataCompletenessScore with detailed results
    """
    evaluator = DataCompletenessEvaluator()
    return evaluator.evaluate(conversation, use_llm=use_llm)
