"""
Test case export system for approved data extraction ground truth.

Provides functionality to export approved statements and feedback as training
test cases for model development. Uses stand-in implementations that should
be extended by parent application.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .models import Statement, Feedback, SpeakerType

import logging

_log = logging.getLogger(__name__)


def export_approved_test_cases() -> int:
    """
    Export all approved, unexported test cases - stand-in implementation
    
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
                # Still mark the statement as exported
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
            # Also mark the related statement as exported
            if feedback.statement:
                feedback.statement.exported_at = datetime.utcnow()
            exported_count += 1

            _log.info(f"Exported feedback {feedback.id} to {filepath}")

        except Exception as e:
            _log.error(f"Error exporting feedback {feedback.id}: {e}", exc_info=True)

    # Note: Parent app should provide database session commit
    # db.session.commit()

    return exported_count


def create_statement_test_case(statement: Statement) -> Dict[str, Any]:
    """
    Create a test case JSON structure from an approved statement - stand-in implementation
    
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

    # Stand-in database - parent app should provide actual database integration
    database = {"people": [], "events": []}

    # Stand-in cumulative PDP - parent app should calculate actual cumulative data
    cumulative_pdp = {"people": [], "events": []}

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
        "note": "Stand-in implementation - parent app should provide full context"
    }


def create_feedback_test_case(feedback: Feedback) -> Dict[str, Any]:
    """
    Create a test case JSON structure from approved feedback - stand-in implementation
    
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

    # Stand-in database - parent app should provide actual database integration
    database = {"people": [], "events": []}

    # Stand-in cumulative PDP - parent app should calculate actual cumulative data
    cumulative_pdp = {"people": [], "events": []}

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
        "note": "Stand-in implementation - parent app should provide full context"
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