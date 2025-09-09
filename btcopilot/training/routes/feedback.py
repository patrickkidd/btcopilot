"""
Feedback routes for training data collection and review.

Provides API endpoints for auditors to submit feedback on AI extractions,
view feedback dashboards, and export training data.
"""

import logging
import json
from flask import Blueprint, request, jsonify, session, abort, render_template
from sqlalchemy import func

from ..models import Statement, SpeakerType, Feedback, Discussion
from ..utils import get_auditor_id, get_breadcrumbs
from ..sse import sse_manager

_log = logging.getLogger(__name__)

# Create the feedback blueprint
feedback_bp = Blueprint(
    "feedback",
    __name__,
    url_prefix="/feedback",
    template_folder="../templates",
    static_folder="../static",
)

# Note: Authentication/authorization should be provided by parent application


def compile_feedback_datapoints():
    """Compile all feedback into individual datapoints for analysis"""
    feedbacks = (
        Feedback.query.join(Statement)
        .join(Discussion)
        .order_by(Feedback.created_at.desc())
        .all()
    )

    # Transform feedbacks into individual datapoints
    datapoints = []

    for feedback in feedbacks:
        # Get discussion history up to and including the feedback statement
        discussion_statements = (
            Statement.query.filter(
                Statement.discussion_id == feedback.statement.discussion_id
            )
            .filter(Statement.id <= feedback.statement_id)
            .order_by(Statement.id.asc())
            .all()
        )

        # Prepare discussion history for fine-tuning context
        discussion_history = []
        for stmt in discussion_statements:
            discussion_history.append(
                {
                    "statement_id": stmt.id,
                    "text": stmt.text,
                    "speaker_type": stmt.speaker.type if stmt.speaker else None,
                    "pdp_deltas": stmt.pdp_deltas,
                    "custom_prompts": stmt.custom_prompts,
                }
            )

        base_info = {
            "feedback_id": feedback.id,
            "statement_id": feedback.statement_id,
            "discussion_id": feedback.statement.discussion_id,
            "user_id": feedback.statement.discussion.user_id or 1,  # Stand-in user ID
            "username": "training_user",  # Stand-in username
            "auditor_id": feedback.auditor_id,
            "thumbs_down": feedback.thumbs_down,
            "comment": feedback.comment,
            "created_at": (
                feedback.created_at.isoformat() if feedback.created_at else None
            ),
            "feedback_type": feedback.feedback_type,
            "statement_text": feedback.statement.text,
            "speaker_type": (
                feedback.statement.speaker.type if feedback.statement.speaker else None
            ),
            "discussion_history": discussion_history,
            "discussion_summary": feedback.statement.discussion.summary,
            "discussion_last_topic": feedback.statement.discussion.last_topic,
            "statement_pdp_deltas": feedback.statement.pdp_deltas,
            "statement_custom_prompts": feedback.statement.custom_prompts,
        }

        if feedback.feedback_type == "extraction" and feedback.statement.pdp_deltas:
            deltas = feedback.statement.pdp_deltas

            # Process people
            if deltas.get("people"):
                for person in deltas["people"]:
                    datapoint = base_info.copy()
                    datapoint["data_type"] = "person"
                    datapoint["person_name"] = person.get("name", "Unknown")
                    datapoint["has_offspring"] = bool(person.get("offspring"))
                    datapoint["has_spouses"] = bool(person.get("spouses"))
                    datapoint["has_parents"] = bool(person.get("parents"))
                    datapoint["person_confidence"] = person.get("confidence", 0.0)
                    datapoints.append(datapoint)

            # Process events (symptom, anxiety, functioning, relationships)
            if deltas.get("events"):
                for event in deltas["events"]:
                    for var_type in ["symptom", "anxiety", "functioning"]:
                        if event.get(var_type):
                            datapoint = base_info.copy()
                            datapoint["data_type"] = var_type
                            datapoint["shift"] = event[var_type].get("shift", "none")
                            datapoint["event_description"] = event.get("description", "")
                            datapoint["event_datetime"] = event.get("dateTime", "")
                            datapoints.append(datapoint)

                    # Add relationship datapoint
                    if event.get("relationship"):
                        datapoint = base_info.copy()
                        rel = event["relationship"]
                        datapoint["data_type"] = "relationship"
                        datapoint["relationship_type"] = rel.get("kind", "unknown")
                        datapoint["event_description"] = event.get("description", "")
                        datapoint["event_datetime"] = event.get("dateTime", "")
                        
                        # Add relationship details
                        if rel.get("kind") == "triangle":
                            datapoint["triangle_inside_a"] = rel.get("inside_a", [])
                            datapoint["triangle_inside_b"] = rel.get("inside_b", [])
                            datapoint["triangle_outside"] = rel.get("outside", [])
                        else:
                            datapoint["mechanism_movers"] = rel.get("movers", [])
                            datapoint["mechanism_recipients"] = rel.get("recipients", [])
                        datapoints.append(datapoint)

            # Process deletions
            if deltas.get("delete"):
                datapoint = base_info.copy()
                datapoint["data_type"] = "deletion"
                datapoint["deletion_count"] = len(deltas["delete"])
                datapoint["deleted_ids"] = deltas["delete"]
                datapoints.append(datapoint)

        # For conversation feedback, add a single row
        elif feedback.feedback_type == "conversation":
            datapoint = base_info.copy()
            datapoint["data_type"] = "conversation"
            datapoints.append(datapoint)

    return datapoints


@feedback_bp.route("")
@feedback_bp.route("/")
def index():
    """Admin view of all feedback - stand-in implementation"""
    # Stand-in user
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    # Get compiled datapoints
    datapoints = compile_feedback_datapoints()

    # Convert back to objects for template compatibility
    for dp in datapoints:
        if "created_at" in dp and dp["created_at"]:
            from datetime import datetime
            dp["created_at"] = datetime.fromisoformat(dp["created_at"])

        # Create user object for template
        dp["user"] = type(
            "User", (), {"id": dp["user_id"], "username": dp["username"]}
        )()

        # Create feedback object for template
        dp["feedback"] = type("Feedback", (), {"id": dp["feedback_id"]})()

    breadcrumbs = get_breadcrumbs("feedback")

    return render_template(
        "feedback_index.html",
        datapoints=datapoints,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
    )


@feedback_bp.route("", methods=["POST"])
@feedback_bp.route("/", methods=["POST"])
def create():
    """Create or update feedback on a statement"""
    data = request.json
    auditor_id = get_auditor_id(request, session)

    # Validate required fields
    if not all(k in data for k in ["message_id", "feedback_type"]):
        return jsonify({"error": "Missing required fields"}), 400

    # Check if feedback already exists - update it instead of creating new
    existing = Feedback.query.filter_by(
        statement_id=data["message_id"],
        auditor_id=auditor_id,
        feedback_type=data["feedback_type"],
    ).first()

    if existing:
        # Update existing feedback
        existing.thumbs_down = data.get("thumbs_down", False)
        existing.comment = data.get("comment")
        existing.edited_extraction = data.get("edited_extraction")
        existing.updated_at = func.now()

        # Note: Parent app should provide database session
        # db.session.commit()
        return jsonify({"success": True, "updated": True, "feedback_id": existing.id})

    # Validate statement exists
    statement = Statement.query.get(data["message_id"])
    if not statement:
        return jsonify({"error": "Statement not found"}), 404

    # Validate feedback type for extraction
    if (
        statement.speaker
        and statement.speaker.type != SpeakerType.Subject
        and data["feedback_type"] == "extraction"
    ):
        return (
            jsonify(
                {"error": "Can only provide extraction feedback on Subject messages"}
            ),
            400,
        )

    feedback = Feedback(
        statement_id=data["message_id"],
        auditor_id=auditor_id,
        feedback_type=data["feedback_type"],
        thumbs_down=data.get("thumbs_down", False),
        comment=data.get("comment"),
        edited_extraction=data.get("edited_extraction"),
    )

    # Note: Parent app should provide database session
    # db.session.add(feedback)
    # db.session.commit()

    # Notify subscribers
    sse_manager.publish(
        json.dumps(
            {
                "type": "new_feedback",
                "message_id": data["message_id"],
                "auditor_id": auditor_id,
                "feedback_type": data["feedback_type"],
            }
        )
    )

    _log.info(f"Feedback submitted: {feedback}")
    return jsonify({"success": True, "created": True, "feedback_id": feedback.id})


@feedback_bp.route("/download")
def download():
    """Download feedback datapoints as JSON file for training"""
    from datetime import datetime
    from flask import make_response

    # Get all datapoints
    datapoints = compile_feedback_datapoints()

    # Apply filters if provided in query parameters
    filters = request.args.to_dict()

    if filters:
        # Apply various filters (simplified for stand-in)
        filtered_datapoints = []
        for dp in datapoints:
            include = True
            
            # Basic filters
            if filters.get("data_type") and dp.get("data_type") != filters["data_type"]:
                include = False
            if filters.get("thumbs_down") and str(dp.get("thumbs_down", False)).lower() != filters["thumbs_down"]:
                include = False
                
            if include:
                filtered_datapoints.append(dp)
        datapoints = filtered_datapoints

    # Create comprehensive export data
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "total_datapoints": len(datapoints),
            "filters_applied": filters,
            "exported_by": "training_system",  # Stand-in
            "data_schema_version": "1.0",
            "intended_use": "fine-tuning and model analysis",
            "data_description": "Audit feedback with full thread context for AI model fine-tuning",
        },
        "datapoints": datapoints,
    }

    # Create JSON response with proper headers for download
    response = make_response(json.dumps(export_data, indent=2, default=str))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = (
        f'attachment; filename=feedback_datapoints_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

    return response


@feedback_bp.route("/<int:feedback_id>", methods=["DELETE"])
def delete(feedback_id):
    """Delete feedback"""
    auditor_id = get_auditor_id(request, session)

    # Find the feedback and verify ownership
    feedback = Feedback.query.filter_by(id=feedback_id, auditor_id=auditor_id).first()

    if not feedback:
        return (
            jsonify({"error": "Feedback not found or not owned by current auditor"}),
            404,
        )

    statement_id = feedback.statement_id
    feedback_type = feedback.feedback_type

    # Note: Parent app should provide database session
    # db.session.delete(feedback)
    # db.session.commit()

    # Notify subscribers
    sse_manager.publish(
        json.dumps(
            {
                "type": "feedback_deleted",
                "message_id": statement_id,
                "auditor_id": auditor_id,
                "feedback_type": feedback_type,
            }
        )
    )

    _log.info(f"Feedback deleted: {feedback_id} by {auditor_id}")
    return jsonify({"success": True})