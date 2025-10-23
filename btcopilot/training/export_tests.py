"""
Test case export system for approved data extraction ground truth
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from btcopilot.extensions import db
from btcopilot.personal.models import Statement, SpeakerType
from btcopilot.schema import Diagram
from btcopilot.personal.pdp import cumulative
from btcopilot.training.models import Feedback

import logging

_log = logging.getLogger(__name__)


def export_approved_test_cases() -> int:
    """
    Export all approved, unexported test cases to ./model_tests/data/uncategorized/

    Returns:
        int: Number of test cases exported
    """
    exported_count = 0

    # Ensure the directory exists
    export_dir = Path("./model_tests/data/uncategorized")
    export_dir.mkdir(parents=True, exist_ok=True)

    # Export approved statements (but only if they don't have approved feedback)
    statements = Statement.query.filter(
        Statement.approved == True,
        Statement.exported_at == None,
        Statement.pdp_deltas != None,
    ).all()

    for statement in statements:
        try:
            # Check if this statement has approved feedback - if so, skip the statement export
            # since the feedback version will be exported instead
            approved_feedback = Feedback.query.filter(
                Feedback.statement_id == statement.id,
                Feedback.approved == True,
                Feedback.feedback_type == "extraction",
                Feedback.edited_extraction != None,
            ).first()

            if approved_feedback:
                _log.info(
                    f"Skipping statement {statement.id} export - approved feedback exists"
                )
                # Still mark the statement as exported since the corrected version will be exported
                statement.exported_at = datetime.utcnow()
                continue

            test_case = create_statement_test_case(statement)
            filename = f"stmt_{statement.id}.json"
            filepath = export_dir / filename

            with open(filepath, "w") as f:
                json.dump(test_case, f, indent=2, ensure_ascii=False)

            # Mark as exported
            statement.exported_at = datetime.utcnow()
            exported_count += 1

            _log.info(f"Exported statement {statement.id} to {filepath}")

        except Exception as e:
            _log.error(f"Error exporting statement {statement.id}: {e}", exc_info=True)

    # Export approved feedback
    feedback_items = Feedback.query.filter(
        Feedback.approved == True,
        Feedback.exported_at == None,
        Feedback.edited_extraction != None,
        Feedback.feedback_type == "extraction",
    ).all()

    for feedback in feedback_items:
        try:
            test_case = create_feedback_test_case(feedback)
            filename = f"stmt_{feedback.statement_id}_corrected.json"
            filepath = export_dir / filename

            with open(filepath, "w") as f:
                json.dump(test_case, f, indent=2, ensure_ascii=False)

            # Mark as exported
            feedback.exported_at = datetime.utcnow()
            # Also mark the related statement as exported since we're using the corrected version
            if feedback.statement:
                feedback.statement.exported_at = datetime.utcnow()
            exported_count += 1

            _log.info(f"Exported feedback {feedback.id} to {filepath}")

        except Exception as e:
            _log.error(f"Error exporting feedback {feedback.id}: {e}", exc_info=True)

    # Commit all the exported_at timestamps
    db.session.commit()

    return exported_count


def create_statement_test_case(statement: Statement) -> Dict[str, Any]:
    """
    Create a test case JSON structure from an approved statement

    Args:
        statement: Statement with approved extraction

    Returns:
        Dict: Test case structure
    """
    discussion = statement.discussion

    # Build conversation history up to and including this statement
    conversation_history = []
    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id)
    )

    for stmt in sorted_statements:
        if stmt.id <= statement.id and stmt.speaker:
            speaker_type = (
                "Subject" if stmt.speaker.type == SpeakerType.Subject else "Expert"
            )
            conversation_history.append(
                {"speaker": speaker_type, "text": stmt.text or ""}
            )

    # Get diagram database
    database = {}
    if discussion.diagram:
        database = discussion.diagram.get_database().model_dump()
    else:
        database = Diagram().model_dump()

    # Calculate cumulative PDP up to this statement (not including it)
    cumulative_pdp = cumulative(discussion, statement).model_dump()

    return {
        "test_id": f"stmt_{statement.id}",
        "source": "statement",
        "created_at": datetime.utcnow().isoformat(),
        "statement_id": statement.id,
        "discussion_id": discussion.id,
        "inputs": {
            "conversation_history": conversation_history,
            "database": database,
            "current_pdp": cumulative_pdp,
            "user_statement": statement.text or "",
            "custom_prompts": statement.custom_prompts,
        },
        "expected_output": statement.pdp_deltas,
    }


def create_feedback_test_case(feedback: Feedback) -> Dict[str, Any]:
    """
    Create a test case JSON structure from approved feedback

    Args:
        feedback: Feedback with approved edited extraction

    Returns:
        Dict: Test case structure
    """
    statement = feedback.statement
    discussion = statement.discussion

    # Build conversation history up to and including this statement
    conversation_history = []
    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id)
    )

    for stmt in sorted_statements:
        if stmt.id <= statement.id and stmt.speaker:
            speaker_type = (
                "Subject" if stmt.speaker.type == SpeakerType.Subject else "Expert"
            )
            conversation_history.append(
                {"speaker": speaker_type, "text": stmt.text or ""}
            )

    # Get diagram database
    database = {}
    if discussion.diagram:
        database = discussion.diagram.get_database().model_dump()
    else:
        database = Diagram().model_dump()

    # Calculate cumulative PDP up to this statement (not including it)
    cumulative_pdp = cumulative(discussion, statement).model_dump()

    return {
        "test_id": f"feedback_{feedback.id}",
        "source": "feedback",
        "created_at": datetime.utcnow().isoformat(),
        "statement_id": statement.id,
        "feedback_id": feedback.id,
        "discussion_id": discussion.id,
        "auditor_id": feedback.auditor_id,
        "inputs": {
            "conversation_history": conversation_history,
            "database": database,
            "current_pdp": cumulative_pdp,
            "user_statement": statement.text or "",
            "custom_prompts": statement.custom_prompts,
        },
        "expected_output": feedback.edited_extraction,
        "original_output": statement.pdp_deltas,
        "feedback_comment": feedback.comment,
    }


def get_exportable_counts() -> Dict[str, int]:
    """
    Get counts of items that can be exported

    Returns:
        Dict with counts of exportable statements and feedback
    """
    statement_count = Statement.query.filter(
        Statement.approved == True,
        Statement.exported_at == None,
        Statement.pdp_deltas != None,
    ).count()

    feedback_count = Feedback.query.filter(
        Feedback.approved == True,
        Feedback.exported_at == None,
        Feedback.edited_extraction != None,
        Feedback.feedback_type == "extraction",
    ).count()

    return {
        "statements": statement_count,
        "feedback": feedback_count,
        "total": statement_count + feedback_count,
    }
