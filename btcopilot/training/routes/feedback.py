import logging
import json
from flask import Blueprint, request, jsonify, session, abort, render_template

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from sqlalchemy import func
from btcopilot.pro.models import User
from btcopilot.personal.models import Statement, SpeakerType, Discussion
from btcopilot.training.models import Feedback
from btcopilot.training.utils import get_auditor_id, get_breadcrumbs

# from btcopilot.training.sse import sse_manager

_log = logging.getLogger(__name__)

# Create the feedback blueprint
bp = Blueprint(
    "feedback",
    __name__,
    url_prefix="/feedback",
)
bp = minimum_role(btcopilot.ROLE_AUDITOR)(bp)


def normalize_pdp_deltas_to_new_schema(data):
    """Convert old schema to new schema format for backward compatibility."""
    if not data:
        return data

    normalized = {"people": [], "events": [], "delete": data.get("delete", [])}

    # Normalize people
    for person in data.get("people", []):
        normalized_person = {
            "id": person.get("id"),
            "name": person.get("name"),
            "last_name": person.get("last_name"),  # May be None in old data
            "spouses": person.get("spouses", []),
            "confidence": person.get("confidence"),
        }

        # Convert old parents list to parent_a/parent_b
        old_parents = person.get("parents", [])
        normalized_person["parent_a"] = old_parents[0] if len(old_parents) > 0 else None
        normalized_person["parent_b"] = old_parents[1] if len(old_parents) > 1 else None

        # offspring is dropped - it's computed from parent relationships

        normalized["people"].append(normalized_person)

    # Normalize events
    for event in data.get("events", []):
        normalized_event = {
            "id": event.get("id"),
            "kind": event.get("kind"),
            "person": event.get("person"),
            "spouse": event.get("spouse"),
            "child": event.get("child"),
            "description": event.get("description"),
            "dateTime": event.get("dateTime"),
            "endDateTime": event.get("endDateTime"),
            "confidence": event.get("confidence"),
        }

        # Normalize variable shifts (dict → direct value)
        for var in ["symptom", "anxiety", "functioning"]:
            old_value = event.get(var)
            if isinstance(old_value, dict):
                normalized_event[var] = old_value.get("shift")
            else:
                normalized_event[var] = old_value

        # Normalize relationship (nested dict → flat structure)
        old_rel = event.get("relationship")
        if old_rel:
            if isinstance(old_rel, dict):
                # Old format: nested dict with kind
                normalized_event["relationship"] = old_rel.get("kind")

                # Convert movers/recipients to relationshipTargets
                movers = old_rel.get("movers", [])
                recipients = old_rel.get("recipients", [])
                normalized_event["relationshipTargets"] = movers + recipients

                # Convert triangle structure
                inside_a = old_rel.get("inside_a", [])
                inside_b = old_rel.get("inside_b", [])
                # Create tuples pairing inside_a with inside_b
                triangles = []
                for i in range(max(len(inside_a), len(inside_b))):
                    a = inside_a[i] if i < len(inside_a) else None
                    b = inside_b[i] if i < len(inside_b) else None
                    if a is not None and b is not None:
                        triangles.append([a, b])
                normalized_event["relationshipTriangles"] = triangles
            else:
                # Already new format
                normalized_event["relationship"] = old_rel
                normalized_event["relationshipTargets"] = event.get(
                    "relationshipTargets", []
                )
                normalized_event["relationshipTriangles"] = event.get(
                    "relationshipTriangles", []
                )

        normalized["events"].append(normalized_event)

    return normalized


def compile_feedback_datapoints():
    """Compile all feedback into individual datapoints for analysis"""
    feedbacks = (
        Feedback.query.join(Statement)
        .join(Discussion)
        .join(User)
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
            "user_id": feedback.statement.discussion.user.id,
            "username": feedback.statement.discussion.user.username,
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
            # Normalize to new schema
            deltas = normalize_pdp_deltas_to_new_schema(feedback.statement.pdp_deltas)

            # Process people
            if deltas.get("people"):
                all_people = deltas.get("people", [])
                for person in all_people:
                    datapoint = base_info.copy()
                    datapoint["data_type"] = "person"
                    datapoint["person_name"] = person.get("name", "Unknown")

                    # Compute offspring from ALL people with this person as parent
                    offspring_ids = [
                        p.get("id")
                        for p in all_people
                        if person.get("id") in [p.get("parent_a"), p.get("parent_b")]
                    ]
                    datapoint["has_offspring"] = len(offspring_ids) > 0

                    datapoint["has_spouses"] = bool(person.get("spouses"))

                    # Convert parent_a/parent_b to list for compatibility
                    parents = [
                        p
                        for p in [person.get("parent_a"), person.get("parent_b")]
                        if p is not None
                    ]
                    datapoint["has_parents"] = len(parents) > 0

                    datapoint["person_confidence"] = person.get("confidence", 0.0)
                    datapoints.append(datapoint)

            # Process events
            if deltas.get("events"):
                for event in deltas["events"]:
                    # Add symptom datapoint
                    if event.get("symptom"):
                        datapoint = base_info.copy()
                        datapoint["data_type"] = "symptom"
                        datapoint["shift"] = event["symptom"]  # Direct enum value
                        datapoint["event_description"] = event.get("description", "")
                        datapoint["event_datetime"] = event.get("dateTime", "")
                        datapoints.append(datapoint)

                    # Add anxiety datapoint
                    if event.get("anxiety"):
                        datapoint = base_info.copy()
                        datapoint["data_type"] = "anxiety"
                        datapoint["shift"] = event["anxiety"]  # Direct enum value
                        datapoint["event_description"] = event.get("description", "")
                        datapoint["event_datetime"] = event.get("dateTime", "")
                        datapoints.append(datapoint)

                    # Add functioning datapoint
                    if event.get("functioning"):
                        datapoint = base_info.copy()
                        datapoint["data_type"] = "functioning"
                        datapoint["shift"] = event["functioning"]  # Direct enum value
                        datapoint["event_description"] = event.get("description", "")
                        datapoint["event_datetime"] = event.get("dateTime", "")
                        datapoints.append(datapoint)

                    # Add relationship datapoint
                    if event.get("relationship"):
                        datapoint = base_info.copy()
                        datapoint["data_type"] = "relationship"
                        datapoint["relationship_type"] = event[
                            "relationship"
                        ]  # Direct enum value
                        datapoint["event_description"] = event.get("description", "")
                        datapoint["event_datetime"] = event.get("dateTime", "")

                        # Get targets and triangles from new fields
                        datapoint["relationship_targets"] = event.get(
                            "relationshipTargets", []
                        )
                        datapoint["relationship_triangles"] = event.get(
                            "relationshipTriangles", []
                        )

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


@bp.route("")
@bp.route("/")
@minimum_role(btcopilot.ROLE_ADMIN)
def index():
    """Admin view of all feedback"""
    user = auth.current_user()

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

    breadcrumbs = get_breadcrumbs("admin_feedback")

    return render_template(
        "feedback_index.html",
        datapoints=datapoints,
        breadcrumbs=breadcrumbs,
        current_user=user,
        btcopilot=btcopilot,
    )


@bp.route("", methods=["POST"])
@bp.route("/", methods=["POST"])
def create():
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

        db.session.commit()
        return jsonify({"success": True, "updated": True, "feedback_id": existing.id})

    # Validate statement exists and is AI-generated
    statement = Statement.query.get(data["message_id"])
    if not statement:
        return jsonify({"error": "Statement not found"}), 404

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

    db.session.add(feedback)
    db.session.commit()

    # # Notify subscribers
    # sse_manager.publish(
    #     json.dumps(
    #         {
    #             "type": "new_feedback",
    #             "message_id": data["message_id"],
    #             "auditor_id": auditor_id,
    #             "feedback_type": data["feedback_type"],
    #         }
    #     )
    # )

    _log.info(f"Feedback submitted: {feedback}")
    return jsonify({"success": True, "created": True, "feedback_id": feedback.id})


@bp.route("/download")
@minimum_role(btcopilot.ROLE_ADMIN)
def download():
    """Download feedback datapoints as JSON file"""

    # Get all datapoints
    datapoints = compile_feedback_datapoints()

    # Apply filters if provided in query parameters
    filters = request.args.to_dict()

    if filters:
        filtered_datapoints = []
        for dp in datapoints:
            include = True

            # Apply basic filters
            if (
                filters.get("user")
                and filters["user"].lower() not in dp["username"].lower()
            ):
                include = False
            if filters.get("auditor") and dp["auditor_id"] != filters["auditor"]:
                include = False
            if (
                filters.get("thumbs_down")
                and str(dp["thumbs_down"]).lower() != filters["thumbs_down"]
            ):
                include = False
            if filters.get("data_type") and dp["data_type"] != filters["data_type"]:
                include = False

            # Apply data type specific filters
            if filters.get("data_type") == "person":
                if filters.get("has_offspring") == "true" and not dp.get(
                    "has_offspring"
                ):
                    include = False
                if filters.get("has_spouses") == "true" and not dp.get("has_spouses"):
                    include = False
                if filters.get("has_parents") == "true" and not dp.get("has_parents"):
                    include = False
            elif filters.get("data_type") in ["symptom", "anxiety", "functioning"]:
                if filters.get("shift") and dp.get("shift") != filters["shift"]:
                    include = False
            elif filters.get("data_type") == "relationship":
                if (
                    filters.get("relationship_type")
                    and dp.get("relationship_type") != filters["relationship_type"]
                ):
                    include = False
            elif filters.get("data_type") == "deletion":
                if (
                    filters.get("has_deletions") == "true"
                    and dp["data_type"] != "deletion"
                ):
                    include = False

            if include:
                filtered_datapoints.append(dp)

        datapoints = filtered_datapoints

    # Create response with JSON data
    from flask import jsonify, make_response
    from datetime import datetime
    import json

    # Add comprehensive metadata for fine-tuning
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "total_datapoints": len(datapoints),
            "filters_applied": filters,
            "exported_by": (
                auth.current_user().username if auth.current_user() else "unknown"
            ),
            "data_schema_version": "1.0",
            "intended_use": "fine-tuning and model analysis",
            "data_description": "Audit feedback with full thread context for AI model fine-tuning",
            "feedback_types": list(
                set(dp.get("feedback_type", "unknown") for dp in datapoints)
            ),
            "data_types": list(
                set(dp.get("data_type", "unknown") for dp in datapoints)
            ),
            "auditors": list(set(dp.get("auditor_id", "unknown") for dp in datapoints)),
            "date_range": {
                "earliest": min(
                    (dp.get("created_at") for dp in datapoints if dp.get("created_at")),
                    default=None,
                ),
                "latest": max(
                    (dp.get("created_at") for dp in datapoints if dp.get("created_at")),
                    default=None,
                ),
            },
            "statistics": {
                "total_issues": sum(
                    1 for dp in datapoints if dp.get("thumbs_down", False)
                ),
                "total_approved": sum(
                    1 for dp in datapoints if not dp.get("thumbs_down", False)
                ),
                "threads_included": len(
                    set(dp.get("discussion_id") for dp in datapoints)
                ),
                "users_included": len(set(dp.get("user_id") for dp in datapoints)),
            },
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


@bp.route("/<int:feedback_id>", methods=["DELETE"])
def delete(feedback_id):
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

    db.session.delete(feedback)
    db.session.commit()

    # # Notify subscribers
    # sse_manager.publish(
    #     json.dumps(
    #         {
    #             "type": "feedback_deleted",
    #             "message_id": statement_id,
    #             "auditor_id": auditor_id,
    #             "feedback_type": feedback_type,
    #         }
    #     )
    # )

    _log.info(f"Feedback deleted: {feedback_id} by {auditor_id}")
    return jsonify({"success": True})
