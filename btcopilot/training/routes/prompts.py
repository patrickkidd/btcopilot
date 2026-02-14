import logging
import json
from flask import Blueprint, request, jsonify, render_template, g
from sqlalchemy.orm import subqueryload

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.llmutil import gemini_text_sync
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal import prompts, ask, Response
from btcopilot.schema import DiagramData, asdict
from btcopilot.pdp import update
from btcopilot.training.models import Feedback
from btcopilot.training.utils import get_breadcrumbs
from btcopilot.training.export_tests import (
    create_statement_test_case,
    create_feedback_test_case,
)

_log = logging.getLogger(__name__)

# Create the prompts blueprint
bp = Blueprint(
    "prompts",
    __name__,
    url_prefix="/prompts",
    template_folder="../templates",
    static_folder="../static",
)
bp = minimum_role(btcopilot.ROLE_AUDITOR)(bp)


@bp.route("/")
def index():
    user = auth.current_user()

    # Get all discussions with user info
    discussions = Discussion.query.options(subqueryload(Discussion.user)).all()

    # Get pre-selected discussion from query parameter
    preselected_discussion_id = request.args.get("discussion", type=int)

    # Get default prompts
    default_prompts = {
        "DATA_EXTRACTION_PROMPT": prompts.DATA_EXTRACTION_PROMPT,
        "DATA_EXTRACTION_EXAMPLES": prompts.DATA_EXTRACTION_EXAMPLES,
        "DATA_EXTRACTION_CONTEXT": prompts.DATA_EXTRACTION_CONTEXT,
        "CONVERSATION_FLOW_PROMPT": prompts.CONVERSATION_FLOW_PROMPT,
    }

    breadcrumbs = get_breadcrumbs("prompts")

    return render_template(
        "prompts_index.html",
        discussions=discussions,
        default_prompts=default_prompts,
        breadcrumbs=breadcrumbs,
        preselected_discussion_id=preselected_discussion_id,
        current_user=user,
        btcopilot=btcopilot,
    )


@bp.route("/test", methods=["POST"])
def test():
    data = request.json
    discussion_id = data.get("discussion_id")
    custom_prompts = data.get("prompts", {})
    message = data.get("message", "")

    if not discussion_id or not message:
        return jsonify({"error": "Discussion ID and message required"}), 400

    discussion = Discussion.query.get_or_404(discussion_id)

    # Store the custom prompts temporarily for this test
    g.custom_prompts = custom_prompts

    # Process the message with custom prompts
    try:
        response: Response = ask(discussion, message)

        # Return the response without saving to database
        return jsonify(
            {
                "success": True,
                "message": response.statement,
                "pdp": asdict(response.pdp),
                "prompts_used": list(custom_prompts.keys()),
            }
        )
    finally:
        # Clear the custom prompts
        if hasattr(g, "custom_prompts"):
            delattr(g, "custom_prompts")


@bp.route("/defaults")
def defaults():
    return jsonify(
        {
            "DATA_EXTRACTION_PROMPT": prompts.DATA_EXTRACTION_PROMPT,
            "DATA_EXTRACTION_EXAMPLES": prompts.DATA_EXTRACTION_EXAMPLES,
            "DATA_EXTRACTION_CONTEXT": prompts.DATA_EXTRACTION_CONTEXT,
            "CONVERSATION_FLOW_PROMPT": prompts.CONVERSATION_FLOW_PROMPT,
        }
    )


@bp.route("/<int:message_id>", methods=["GET", "POST"])
def message_prompts(message_id):
    """Get or set custom prompts for a specific message"""

    statement = Statement.query.get_or_404(message_id)

    if request.method == "GET":
        # Return existing custom prompts
        return jsonify({"custom_prompts": statement.custom_prompts or {}})

    elif request.method == "POST":
        # Save custom prompts
        data = request.json
        custom_prompts = data.get("custom_prompts", {})

        # Update the statement with custom prompts
        statement.custom_prompts = custom_prompts if custom_prompts else None
        db.session.commit()

        _log.info(
            f"Updated custom prompts for message {message_id}: {list(custom_prompts.keys())}"
        )

        return jsonify({"success": True})


@bp.route("/load-artifact/<int:statement_id>")
def load_artifact(statement_id):
    """Load complete extraction artifact for a statement"""
    statement = Statement.query.get_or_404(statement_id)

    # Check for feedback first (corrected extraction)
    feedback = Feedback.query.filter_by(
        statement_id=statement_id, feedback_type="extraction"
    ).first()

    # Use existing test case creation logic!
    if feedback and feedback.edited_extraction:
        artifact = create_feedback_test_case(feedback)
        artifact["has_correction"] = True
        artifact["ai_extracted"] = statement.pdp_deltas
        artifact["corrected"] = feedback.edited_extraction
    else:
        artifact = create_statement_test_case(statement)
        artifact["has_correction"] = False
        artifact["ai_extracted"] = statement.pdp_deltas
        artifact["corrected"] = statement.pdp_deltas  # Same as AI if no correction

    return jsonify(artifact)


@bp.route("/suggest-improvements", methods=["POST"])
def suggest_improvements():
    """Get AI suggestions for improving prompts based on artifact"""
    data = request.json
    artifact = data["artifact"]
    current_prompts = data.get("prompts", {})

    # Build coaching prompt
    coach_prompt = f"""
    A PDP extraction system failed on this case. Help improve the system prompts.
    
    USER STATEMENT:
    {artifact['inputs']['user_statement']}
    
    AI INCORRECTLY EXTRACTED:
    {json.dumps(artifact['ai_extracted'], indent=2)}
    
    CORRECT EXTRACTION SHOULD BE:
    {json.dumps(artifact['corrected'], indent=2)}
    
    CONTEXT:
    - Database had {len(artifact['inputs']['database']['people'])} people and {len(artifact['inputs']['database']['events'])} events
    - Conversation history had {len(artifact['inputs']['conversation_history'])} messages
    - PDP before this statement had {len(artifact['inputs']['current_pdp']['people'])} people and {len(artifact['inputs']['current_pdp']['events'])} events
    
    CURRENT DATA_EXTRACTION_PROMPT:
    {current_prompts.get('DATA_EXTRACTION_PROMPT', prompts.DATA_EXTRACTION_PROMPT)[:1000]}...
    
    Analyze why the AI missed this extraction and suggest specific improvements to the prompts:
    
    1. What pattern or rule did the AI miss?
    2. Which specific section of the prompt needs modification?
    3. What exact text should be added, changed, or removed?
    4. Would additional examples help? If so, suggest one.
    
    Focus on actionable changes that would help the AI catch this specific pattern.
    """

    try:
        response = gemini_text_sync(coach_prompt)

        return jsonify(
            {"suggestions": response, "artifact_id": artifact.get("statement_id")}
        )
    except Exception as e:
        _log.error(f"Error getting AI suggestions: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route("/test-extraction", methods=["POST"])
def test_extraction():
    """Test extraction with modified prompts on specific artifact"""
    data = request.json
    artifact = data["artifact"]
    custom_prompts = data.get("prompts", {})

    try:
        # Temporarily override prompts for testing
        original_prompts = {
            "DATA_EXTRACTION_PROMPT": prompts.DATA_EXTRACTION_PROMPT,
            "DATA_EXTRACTION_EXAMPLES": prompts.DATA_EXTRACTION_EXAMPLES,
            "DATA_EXTRACTION_CONTEXT": prompts.DATA_EXTRACTION_CONTEXT,
        }

        try:
            # Apply custom prompts
            if "DATA_EXTRACTION_PROMPT" in custom_prompts:
                prompts.DATA_EXTRACTION_PROMPT = custom_prompts[
                    "DATA_EXTRACTION_PROMPT"
                ]
            if "DATA_EXTRACTION_EXAMPLES" in custom_prompts:
                prompts.DATA_EXTRACTION_EXAMPLES = custom_prompts[
                    "DATA_EXTRACTION_EXAMPLES"
                ]
            if "DATA_EXTRACTION_CONTEXT" in custom_prompts:
                prompts.DATA_EXTRACTION_CONTEXT = custom_prompts[
                    "DATA_EXTRACTION_CONTEXT"
                ]

            # Create discussion and database objects for testing
            discussion = Discussion.query.get(artifact["discussion_id"])
            database = DiagramData(**artifact["inputs"]["diagram_data"])

            # Run extraction with modified prompts (using asyncio.run for sync context)
            import asyncio

            _, result_deltas = asyncio.run(
                update(
                    thread=discussion,
                    database=database,
                    user_message=artifact["inputs"]["user_statement"],
                )
            )

            # Compare results
            extracted = asdict(result_deltas)
            expected = artifact["corrected"]

            # Simple comparison - could be enhanced
            matches = extracted == expected

            return jsonify(
                {
                    "extracted": extracted,
                    "expected": expected,
                    "original_ai": artifact["ai_extracted"],
                    "matches": matches,
                    "artifact_id": artifact.get("statement_id"),
                }
            )

        finally:
            # Always restore original prompts
            prompts.DATA_EXTRACTION_PROMPT = original_prompts["DATA_EXTRACTION_PROMPT"]
            prompts.DATA_EXTRACTION_EXAMPLES = original_prompts[
                "DATA_EXTRACTION_EXAMPLES"
            ]
            prompts.DATA_EXTRACTION_CONTEXT = original_prompts[
                "DATA_EXTRACTION_CONTEXT"
            ]

    except Exception as e:
        _log.error(f"Error testing extraction: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route("/coach-chat", methods=["POST"])
def coach_chat():
    """Interactive chat for prompt refinement"""
    data = request.json
    message = data["message"]
    artifact = data.get("artifact", {})
    last_result = data.get("last_test_result", {})

    # Build context-aware chat prompt focused on PDP extraction improvement
    current_prompts = data.get("current_prompts", {})

    chat_prompt = f"""
    You are an expert AI prompt engineer helping improve PDP (Pending Data Pool) extraction system prompts used in btcopilot/training/prompts.py. These prompts are loaded by pdp.py for extracting psychological/therapeutic data from user conversations.

    **YOUR ROLE**: Help refine the system prompts that instruct the AI to extract:
    - People (with relationships, confidence levels)  
    - Events (with symptom, anxiety, functioning shifts, and relationship patterns)
    - Deletes (IDs of items to remove)

    **CURRENT EXTRACTION FAILURE**:
    User Statement: "{artifact.get('inputs', {}).get('user_statement', 'N/A')}"
    
    AI Extracted (WRONG): {json.dumps(artifact.get('ai_extracted', {}), indent=2)}
    Should Extract (CORRECT): {json.dumps(artifact.get('corrected', {}), indent=2)}
    
    Latest Test: {json.dumps(last_result.get('extracted', {}), indent=2) if last_result else 'No recent tests'}

    **CURRENT PROMPTS IN USE**:
    DATA_EXTRACTION_PROMPT: "{current_prompts.get('DATA_EXTRACTION_PROMPT', prompts.DATA_EXTRACTION_PROMPT)[:500]}..."

    **USER QUESTION**: {message}

    Focus on improving the extraction accuracy by suggesting specific modifications to:
    1. The role/instruction prompts that define what to extract
    2. The example prompts that show extraction patterns
    3. Edge cases, relationship detection, confidence scoring
    
    Provide concrete prompt text changes, not general advice.
    """

    try:
        response = gemini_text_sync(chat_prompt)
        return jsonify({"response": response})
    except Exception as e:
        _log.error(f"Error in coach chat: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
