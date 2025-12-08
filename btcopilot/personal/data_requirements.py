"""
Data Collection Requirements

Defines what data must be collected for a complete family diagram.
This module is the single source of truth for data collection requirements,
used by both the chat prompts and the testing framework.
"""

from dataclasses import dataclass, field
from enum import Enum


class RequirementCategory(Enum):
    """Categories of data to collect."""

    PRESENTING_PROBLEM = "presenting_problem"
    FAMILY_OF_ORIGIN = "family_of_origin"
    EXTENDED_FAMILY = "extended_family"
    OWN_FAMILY = "own_family"
    NODAL_EVENTS = "nodal_events"


@dataclass
class DataRequirement:
    """A single data requirement."""

    id: str
    description: str
    category: RequirementCategory
    required: bool = True  # Some are optional (e.g., own family if not partnered)
    examples: list[str] = field(default_factory=list)


# =============================================================================
# PRESENTING PROBLEM REQUIREMENTS
# =============================================================================

PRESENTING_PROBLEM_REQUIREMENTS = [
    DataRequirement(
        id="problem_description",
        description="What the problem is",
        category=RequirementCategory.PRESENTING_PROBLEM,
        examples=["panic attacks", "conflict with spouse", "child's behavior issues"],
    ),
    DataRequirement(
        id="problem_onset",
        description="When it started",
        category=RequirementCategory.PRESENTING_PROBLEM,
        examples=["6 months ago", "since mom died", "after the move"],
    ),
    DataRequirement(
        id="problem_people_involved",
        description="Who is involved",
        category=RequirementCategory.PRESENTING_PROBLEM,
        examples=["me and my husband", "my son and his teacher", "the whole family"],
    ),
    DataRequirement(
        id="problem_feelings",
        description="How each person feels about it",
        category=RequirementCategory.PRESENTING_PROBLEM,
        required=False,  # Move on if no engagement
        examples=["I'm frustrated, he's defensive", "she seems scared"],
    ),
    DataRequirement(
        id="problem_challenges",
        description="Biggest challenges/uncertainties about the situation",
        category=RequirementCategory.PRESENTING_PROBLEM,
        examples=["don't know what to do", "can't get him to talk", "feeling stuck"],
    ),
]

# =============================================================================
# FAMILY OF ORIGIN REQUIREMENTS
# =============================================================================

FAMILY_OF_ORIGIN_REQUIREMENTS = [
    DataRequirement(
        id="mother_name",
        description="Mother: name",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=["Helen", "Mary", "mom (if name unknown)"],
    ),
    DataRequirement(
        id="mother_age_status",
        description="Mother: age (or death year/cause)",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=["65", "died in 2020 from cancer", "passed away 3 years ago"],
    ),
    DataRequirement(
        id="father_name",
        description="Father: name",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=["Richard", "Tom", "dad (if name unknown)"],
    ),
    DataRequirement(
        id="father_age_status",
        description="Father: age (or death year/cause)",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=["68", "died in 2015", "unknown - left when I was young"],
    ),
    DataRequirement(
        id="parents_status",
        description="Parents together or divorced? When?",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=["still married", "divorced in 2010", "separated", "father remarried"],
    ),
    DataRequirement(
        id="siblings",
        description="All siblings: names and ages",
        category=RequirementCategory.FAMILY_OF_ORIGIN,
        examples=[
            "brother Tom (31), sister Amy (28)",
            "only child",
            "two older brothers",
        ],
    ),
]

# =============================================================================
# EXTENDED FAMILY REQUIREMENTS
# =============================================================================

EXTENDED_FAMILY_REQUIREMENTS = [
    DataRequirement(
        id="grandparents",
        description="4 grandparents: names and alive/deceased",
        category=RequirementCategory.EXTENDED_FAMILY,
        examples=[
            "maternal grandma Rose (deceased), grandpa Joe (85)",
            "paternal grandparents both passed",
        ],
    ),
    DataRequirement(
        id="aunts_uncles_count",
        description="Number of aunts/uncles on each side",
        category=RequirementCategory.EXTENDED_FAMILY,
        examples=[
            "mom has 2 sisters, dad was an only child",
            "3 aunts/uncles on each side",
        ],
    ),
]

# =============================================================================
# OWN FAMILY REQUIREMENTS (if partnered)
# =============================================================================

OWN_FAMILY_REQUIREMENTS = [
    DataRequirement(
        id="spouse",
        description="Spouse: name, age, when married",
        category=RequirementCategory.OWN_FAMILY,
        required=False,  # Only if partnered
        examples=["Mark, 36, married 2018", "partner of 5 years"],
    ),
    DataRequirement(
        id="children",
        description="Children: names and ages",
        category=RequirementCategory.OWN_FAMILY,
        required=False,  # Only if has children
        examples=["Jake (17), Emma (14)", "no children", "expecting first"],
    ),
]

# =============================================================================
# NODAL EVENTS REQUIREMENTS
# =============================================================================

NODAL_EVENTS_REQUIREMENTS = [
    DataRequirement(
        id="problem_timeline",
        description="When problem started (specific timeframe)",
        category=RequirementCategory.NODAL_EVENTS,
        examples=["June 2024", "about 6 months ago", "after mom's funeral"],
    ),
    DataRequirement(
        id="recent_deaths",
        description="Recent deaths (who, when, how did family react?)",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,  # May not have any
        examples=["mother died 8 months ago, father remarried quickly"],
    ),
    DataRequirement(
        id="illnesses",
        description="Illnesses or health scares",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,
        examples=["father had stroke last year", "brother's cancer diagnosis"],
    ),
    DataRequirement(
        id="relationship_changes",
        description="Marriages, divorces, separations",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,
        examples=["sister divorced last year", "parents separated when I was 10"],
    ),
    DataRequirement(
        id="moves",
        description="Moves (geographic or household changes)",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,
        examples=["moved back in with parents", "relocated for work"],
    ),
    DataRequirement(
        id="job_changes",
        description="Job changes, retirements, financial setbacks",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,
        examples=["laid off 6 months ago", "dad retired last year"],
    ),
    DataRequirement(
        id="cutoffs",
        description="Cutoffs (who's not speaking to whom?)",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,
        examples=["haven't spoken to father since wedding", "sister not talking to mom"],
    ),
    DataRequirement(
        id="symptom_connection",
        description="Connection between events and symptoms",
        category=RequirementCategory.NODAL_EVENTS,
        required=False,  # User may not see connection
        examples=["anxiety started after mom died", "symptoms worse since the move"],
    ),
]

# =============================================================================
# ALL REQUIREMENTS
# =============================================================================

ALL_REQUIREMENTS = (
    PRESENTING_PROBLEM_REQUIREMENTS
    + FAMILY_OF_ORIGIN_REQUIREMENTS
    + EXTENDED_FAMILY_REQUIREMENTS
    + OWN_FAMILY_REQUIREMENTS
    + NODAL_EVENTS_REQUIREMENTS
)

REQUIRED_REQUIREMENTS = [r for r in ALL_REQUIREMENTS if r.required]


def get_requirements_by_category(
    category: RequirementCategory,
) -> list[DataRequirement]:
    """Get all requirements for a specific category."""
    return [r for r in ALL_REQUIREMENTS if r.category == category]


# =============================================================================
# MINIMUM REQUIREMENTS FOR "DONE"
# =============================================================================

# These are the minimum requirements to consider data collection complete.
# Based on the prompt: "You have enough to return focus to the presenting problem when..."

MINIMUM_COMPLETE_REQUIREMENTS = {
    # 1. Thorough understanding of the presenting problem
    "presenting_problem": ["problem_description", "problem_onset", "problem_people_involved"],
    # 2. Both parents with names, ages, status
    "parents": ["mother_name", "mother_age_status", "father_name", "father_age_status"],
    # 3. Sibling roster (names, ages)
    "siblings": ["siblings"],
    # 4. At least basic info on all 4 grandparents
    "grandparents": ["grandparents"],
    # 5. If partnered: spouse and children basics (checked conditionally)
    # 6. Sense of major recent stressors (at least one nodal event category explored)
}


def generate_checklist_markdown() -> str:
    """
    Generate the checklist markdown for use in prompts.

    This ensures the prompt checklist stays in sync with the requirements.
    """
    lines = ["**Required Data Checklist:**", ""]

    category_names = {
        RequirementCategory.PRESENTING_PROBLEM: "Presenting Problem",
        RequirementCategory.FAMILY_OF_ORIGIN: "Family of Origin",
        RequirementCategory.EXTENDED_FAMILY: "Extended Family",
        RequirementCategory.OWN_FAMILY: "User's Own Family (if applicable)",
        RequirementCategory.NODAL_EVENTS: "Timeline of Nodal Events",
    }

    for category in RequirementCategory:
        reqs = get_requirements_by_category(category)
        if reqs:
            lines.append(f"{category_names[category]}:")
            for req in reqs:
                optional = " (optional)" if not req.required else ""
                lines.append(f"- [ ] {req.description}{optional}")
            lines.append("")

    return "\n".join(lines)


def generate_completion_criteria_markdown() -> str:
    """
    Generate the "when is data collection done" markdown for prompts.
    """
    return """**When is data collection "done"?**

You have enough to return focus to the presenting problem when you have:
1. Thorough understanding of the presenting problem
2. Both parents with names, ages, status
3. Sibling roster (names, ages)
4. At least basic info on all 4 grandparents
5. If partnered: spouse and children basics
6. Sense of major recent stressors"""
