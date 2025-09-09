"""
Prompts lab interface for training data collection and refinement.

Provides web interface for auditors to test and refine AI prompts, view extraction
results, and iteratively improve system accuracy. Uses placeholder prompts that
should be overridden by the parent application.
"""

import logging
import json
from flask import Blueprint, request, jsonify, render_template, g

from ..models import Discussion, Statement, Feedback
from ..utils import get_breadcrumbs

_log = logging.getLogger(__name__)

# Create the prompts blueprint
prompts_bp = Blueprint(
    "prompts",
    __name__,
    url_prefix="/prompts",
    template_folder="../templates",
    static_folder="../static",
)

# Note: Authentication/authorization should be provided by parent application

# Stand-in prompts - parent application should override these
STAND_IN_PROMPTS = {
    "ROLE_COACH_NOT_THERAPIST": """
**Role & Goal**

- You are a consultant providing information and guidance.
- Focus on gathering information rather than providing emotional support.
- Use objective/measurable language when possible.
- Limit your responses to one question at a time.
- Focus on placing events in time and context.
""",
    "BOWEN_THEORY_COACHING_IN_A_NUTSHELL": """
Stand-in coaching framework:

1) Clarify and define the problem or issue
2) Gather information about the timeline and course 
3) Identify notable points or periods of change
4) Gather context around significant changes
5) Understand the people and relationships involved
""",
    "DATA_MODEL_DEFINITIONS": """
*Person*: Individuals involved in the narrative. Focus on family members
and close relationships across multiple generations.

*Event*: Indicates a change or shift in variables and always relates
to one or more people.

*Variables* are constructs defined by characteristics:
- Symptom: Physical/mental health changes or goal challenges
- Anxiety: Responses to real or imagined threats  
- Functioning: Ability to balance emotion and intellect
- Relationship: Actions performed in relation to others

Stand-in data model for generic relationship and event tracking.
""",
    "PDP_ROLE_AND_INSTRUCTIONS": """
**Role & Task**:

You are a data extraction assistant that provides NEW DELTAS (changes/additions) 
for a pending data pool (PDP) in a database.

Extract ONLY new information or changes from user statements:
- NEW people mentioned for the first time
- NEW events/incidents described  
- UPDATES to existing people
- DELETIONS when user corrects previous information

Stand-in extraction rules:
1. Sparse output - return few items, often empty arrays
2. Extract only new information not already in database
3. Single events per statement typically
4. Update only changed fields for existing items

This is a placeholder system. Parent application should provide
specific extraction rules and data models.
""",
    "PDP_EXAMPLES": """
Stand-in examples for data extraction:

Example: Simple person and event extraction
Input: "My brother came home upset yesterday."

Output: {
    "people": [
        {"id": -1, "name": "Brother", "confidence": 0.8}
    ],
    "events": [
        {
            "id": -2,
            "description": "Came home upset",
            "dateTime": "2025-01-01",
            "people": [-1],
            "confidence": 0.7
        }
    ],
    "delete": []
}

Parent application should provide comprehensive examples
for specific domain and data model.
"""
}


@prompts_bp.route("/")
def index():
    """Prompts lab dashboard - stand-in implementation"""
    # Stand-in user
    current_user = {"id": 1, "username": "auditor", "role": "auditor"}

    # Get discussions for testing
    discussions = Discussion.query.limit(50).all()

    # Get pre-selected discussion from query parameter
    preselected_discussion_id = request.args.get("discussion", type=int)

    # Use stand-in prompts
    default_prompts = STAND_IN_PROMPTS.copy()

    breadcrumbs = get_breadcrumbs("prompts")

    return render_template(
        "prompts_index.html",
        discussions=discussions,
        default_prompts=default_prompts,
        breadcrumbs=breadcrumbs,
        preselected_discussion_id=preselected_discussion_id,
        current_user=current_user,
    )


@prompts_bp.route("/test", methods=["POST"])
def test():
    """Test message processing with custom prompts - stand-in implementation"""
    data = request.json
    discussion_id = data.get("discussion_id")
    custom_prompts = data.get("prompts", {})
    message = data.get("message", "")

    if not discussion_id or not message:
        return jsonify({"error": "Discussion ID and message required"}), 400

    discussion = Discussion.query.get_or_404(discussion_id)

    # Store the custom prompts temporarily for this test
    g.custom_prompts = custom_prompts

    # Stand-in response processing
    try:
        # Parent application should implement actual AI processing
        # This is a placeholder response
        response_message = f"Stand-in response to: {message}"
        mock_pdp = {
            "people": [],
            "events": [],
            "delete": []
        }

        return jsonify(
            {
                "success": True,
                "message": response_message,
                "pdp": mock_pdp,
                "prompts_used": list(custom_prompts.keys()),
                "note": "Stand-in implementation - parent app should override"
            }
        )
    finally:
        # Clear the custom prompts
        if hasattr(g, "custom_prompts"):
            delattr(g, "custom_prompts")


@prompts_bp.route("/defaults")
def defaults():
    """Get default prompts"""
    return jsonify(STAND_IN_PROMPTS)


@prompts_bp.route("/<int:message_id>", methods=["GET", "POST"])
def message_prompts(message_id):
    """Get or set custom prompts for a specific message"""
    statement = Statement.query.get_or_404(message_id)

    if request.method == "GET":
        # Return existing custom prompts
        return jsonify({"custom_prompts": statement.custom_prompts or {}})

    elif request.method == "POST":
        # Save custom prompts - stand-in implementation
        data = request.json
        custom_prompts = data.get("custom_prompts", {})

        # Update the statement with custom prompts
        statement.custom_prompts = custom_prompts if custom_prompts else None
        # Note: Parent app should provide database session
        # db.session.commit()

        _log.info(
            f"Updated custom prompts for message {message_id}: {list(custom_prompts.keys())}"
        )

        return jsonify({"success": True})


@prompts_bp.route("/load-artifact/<int:statement_id>")
def load_artifact(statement_id):
    """Load complete extraction artifact for a statement - stand-in implementation"""
    statement = Statement.query.get_or_404(statement_id)

    # Check for feedback first (corrected extraction)
    feedback = Feedback.query.filter_by(
        statement_id=statement_id, feedback_type="extraction"
    ).first()

    # Stand-in artifact creation
    artifact = {
        "statement_id": statement_id,
        "discussion_id": statement.discussion_id,
        "inputs": {
            "user_statement": statement.text,
            "database": {"people": [], "events": []},
            "conversation_history": [],
            "current_pdp": {"people": [], "events": []}
        },
        "ai_extracted": statement.pdp_deltas or {},
        "corrected": feedback.edited_extraction if feedback and feedback.edited_extraction else statement.pdp_deltas or {},
        "has_correction": bool(feedback and feedback.edited_extraction),
        "note": "Stand-in artifact - parent app should provide full context"
    }

    return jsonify(artifact)


@prompts_bp.route("/suggest-improvements", methods=["POST"])
def suggest_improvements():
    """Get AI suggestions for improving prompts - stand-in implementation"""
    data = request.json
    artifact = data["artifact"]
    current_prompts = data.get("prompts", {})

    # Stand-in coaching suggestions
    mock_suggestions = f"""
    Stand-in prompt improvement suggestions for statement: "{artifact.get('inputs', {}).get('user_statement', 'N/A')}"

    1. Pattern Analysis: This is a placeholder analysis
    2. Prompt Modification: Stand-in suggestion for prompt changes
    3. Specific Changes: Parent application should provide actual AI analysis
    4. Example Addition: Consider adding domain-specific examples

    The parent application should integrate with an LLM service to provide
    actual prompt improvement suggestions based on extraction failures.
    """

    return jsonify(
        {
            "suggestions": mock_suggestions,
            "artifact_id": artifact.get("statement_id"),
            "note": "Stand-in implementation - parent app should provide AI suggestions"
        }
    )


@prompts_bp.route("/test-extraction", methods=["POST"])
def test_extraction():
    """Test extraction with modified prompts - stand-in implementation"""
    data = request.json
    artifact = data["artifact"]
    custom_prompts = data.get("prompts", {})

    # Stand-in extraction testing
    mock_extracted = {
        "people": [],
        "events": [],
        "delete": []
    }
    expected = artifact["corrected"]

    # Simple comparison
    matches = mock_extracted == expected

    return jsonify(
        {
            "extracted": mock_extracted,
            "expected": expected,
            "original_ai": artifact["ai_extracted"],
            "matches": matches,
            "artifact_id": artifact.get("statement_id"),
            "note": "Stand-in implementation - parent app should provide actual extraction testing"
        }
    )


@prompts_bp.route("/coach-chat", methods=["POST"])
def coach_chat():
    """Interactive chat for prompt refinement - stand-in implementation"""
    data = request.json
    message = data["message"]
    artifact = data.get("artifact", {})
    last_result = data.get("last_test_result", {})

    # Stand-in coaching response
    mock_response = f"""
    Stand-in coaching response to: "{message}"

    Based on the extraction failure for: "{artifact.get('inputs', {}).get('user_statement', 'N/A')}"

    This is a placeholder coaching system. The parent application should:
    1. Integrate with an LLM service for actual coaching
    2. Provide domain-specific prompt engineering guidance
    3. Analyze extraction patterns and suggest improvements
    4. Offer concrete prompt text modifications

    Current prompts and test results would be analyzed by the actual system.
    """

    return jsonify({
        "response": mock_response,
        "note": "Stand-in implementation - parent app should provide AI coaching"
    })