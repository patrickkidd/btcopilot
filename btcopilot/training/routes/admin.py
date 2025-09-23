import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from sqlalchemy.orm import subqueryload
from sqlalchemy import func, case

import vedana
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import User, License, Diagram
from btcopilot.personal.database import Database
from btcopilot.personal.models import Discussion, Statement
from btcopilot.training.models import Feedback
from btcopilot.training.utils import get_breadcrumbs

_log = logging.getLogger(__name__)

bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates",
)
bp = minimum_role(vedana.ROLE_ADMIN)(bp)


# Simple in-memory cache for feedback statistics
_feedback_stats_cache = {}
_feedback_stats_cache_time = None


def get_feedback_statistics():
    """Get feedback statistics with 5-minute caching"""
    import time

    # Declare global variables first
    global _feedback_stats_cache, _feedback_stats_cache_time

    current_time = time.time()

    # Check if cache is valid (5 minutes = 300 seconds)
    if (
        _feedback_stats_cache_time
        and current_time - _feedback_stats_cache_time < 300
        and _feedback_stats_cache
    ):
        return _feedback_stats_cache

    # Get fresh statistics
    feedback_stats_query = db.session.query(
        func.count().label("total"),
        func.sum(case((Feedback.feedback_type == "conversation", 1), else_=0)).label(
            "conversations"
        ),
        func.sum(case((Feedback.feedback_type == "extraction", 1), else_=0)).label(
            "extractions"
        ),
        func.sum(case((Feedback.thumbs_down == True, 1), else_=0)).label("thumbs_down"),
        func.count(func.distinct(Feedback.auditor_id)).label("unique_auditors"),
    ).first()

    total_feedbacks = feedback_stats_query.total or 0
    conversation_feedbacks = feedback_stats_query.conversations or 0
    extraction_feedbacks = feedback_stats_query.extractions or 0
    thumbs_down_count = feedback_stats_query.thumbs_down or 0
    unique_auditors = feedback_stats_query.unique_auditors or 0

    feedback_stats = {
        "total": total_feedbacks,
        "conversations": conversation_feedbacks,
        "extractions": extraction_feedbacks,
        "issues": thumbs_down_count,
        "issue_rate": (
            round(thumbs_down_count / total_feedbacks * 100, 1)
            if total_feedbacks > 0
            else 0
        ),
        "auditors": unique_auditors,
    }

    # Update cache
    _feedback_stats_cache = feedback_stats
    _feedback_stats_cache_time = current_time

    return feedback_stats


def invalidate_feedback_stats_cache():
    """Invalidate the feedback statistics cache"""
    global _feedback_stats_cache, _feedback_stats_cache_time
    _feedback_stats_cache = {}
    _feedback_stats_cache_time = None


def build_user_summary(user, include_discussion_count=True):
    """Build summary data for a user"""
    if include_discussion_count:
        # For users with loaded diagrams/discussions
        if hasattr(user, "diagrams") and user.diagrams:
            discussion_count = sum(
                len(diagram.discussions) for diagram in user.diagrams
            )
        else:
            # Efficiently count discussions for users without loaded diagrams
            discussion_count = (
                db.session.query(func.count(Discussion.id))
                .join(Diagram)
                .filter(Diagram.user_id == user.id)
                .scalar()
                or 0
            )
    else:
        discussion_count = 0

    license_count = len(user.licenses) if user.licenses else 0
    diagram_count = len(user.diagrams) if user.diagrams else 0

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name(),
        "roles": user.roles.split(",") if user.roles else [],
        "status": user.status,
        "active": user.active,
        "discussion_count": discussion_count,
        "license_count": license_count,
        "diagram_count": diagram_count,
        "created_at": (
            user.created_at.isoformat()
            if hasattr(user, "created_at") and user.created_at
            else None
        ),
    }


def get_users_for_admin(search=None, role_filter=None, for_index=False):
    """Get users for admin interface with optional filtering"""

    if for_index:
        # For index page: prioritize admin users + users with discussions + recent users (limited set)

        # Admin users (always include these first)
        admin_users = User.query.filter(User.roles.like("%admin%")).options(
            subqueryload(User.diagrams).subqueryload(Diagram.discussions),
            subqueryload(User.licenses).subqueryload(License.policy),
            subqueryload(User.licenses).subqueryload(License.activations),
        )

        # Users with discussions (prioritize these)
        users_with_discussions = (
            User.query.join(Diagram, Diagram.user_id == User.id)
            .join(Discussion)
            .options(
                subqueryload(User.diagrams).subqueryload(Diagram.discussions),
                subqueryload(User.licenses).subqueryload(License.policy),
                subqueryload(User.licenses).subqueryload(License.activations),
            )
            .distinct()
        )

        # Most recent users (for general admin management)
        recent_users = (
            User.query.options(
                subqueryload(User.licenses).subqueryload(License.policy),
                subqueryload(User.licenses).subqueryload(License.activations),
            )
            .order_by(User.id.desc())
            .limit(100)
        )

        # Combine and deduplicate
        all_user_ids = set()
        users = []

        # Add admin users first (highest priority)
        for user in admin_users:
            if user.id not in all_user_ids:
                users.append(user)
                all_user_ids.add(user.id)

        # Add users with discussions
        for user in users_with_discussions:
            if user.id not in all_user_ids:
                users.append(user)
                all_user_ids.add(user.id)

        # Add recent users if not already included
        for user in recent_users:
            if user.id not in all_user_ids:
                users.append(user)
                all_user_ids.add(user.id)

        # Limit to max 100 users for performance on index page
        users = users[:100]

        # Build summary data (users already have discussions loaded)
        users_data = [
            build_user_summary(user, include_discussion_count=True) for user in users
        ]

        return {
            "users": users,
            "users_data": users_data,
            "pagination": None,  # Index page doesn't use pagination
            "total_count": User.query.count(),
        }

    else:
        # For search API: full query with filters and pagination
        query = User.query

        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                db.or_(
                    User.username.ilike(search_term),
                    db.func.concat(User.first_name, " ", User.last_name).ilike(
                        search_term
                    ),
                )
            )

        # Apply role filter
        if role_filter and role_filter != "all":
            query = query.filter(User.roles.like(f"%{role_filter}%"))

        # Order by ID descending (most recent first)
        users = query.order_by(User.id.desc()).all()

        # Build summary data (skip expensive discussion counts for subscribers)
        include_discussions = role_filter != "subscriber"
        users_data = [
            build_user_summary(user, include_discussion_count=include_discussions)
            for user in users
        ]

        return {
            "users": users,
            "users_data": users_data,
            "total_count": len(users),
        }


@bp.route("/")
def index():
    current_user = auth.current_user()

    # Get all discussions with user info
    discussions = Discussion.query.options(subqueryload(Discussion.statements)).all()

    # Get users using shared function (default to auditor users for performance)
    user_data = get_users_for_admin(role_filter="auditor")

    # Get cached feedback statistics
    feedback_stats = get_feedback_statistics()

    breadcrumbs = get_breadcrumbs("admin")

    return render_template(
        "therapist_admin.html",
        discussions=discussions,
        users=user_data["users"],
        users_summary=user_data["users_data"],
        total_user_count=user_data["total_count"],
        showing_user_count=len(user_data["users"]),
        feedback_stats=feedback_stats,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
        vedana=vedana,
    )


@bp.route("/users", methods=["GET"])
def users_list():
    """Get all users for admin interface - no filtering, client-side only"""
    current_user = auth.current_user()

    # Get ALL users without any filters - client will handle filtering
    users = User.query.order_by(User.id.desc()).all()

    # Build summary data for all users
    users_data = [
        build_user_summary(user, include_discussion_count=True) for user in users
    ]

    return jsonify(
        {
            "users": users_data,
            "total_count": len(users),
        }
    )


@bp.route("/users/search", methods=["GET"])
def users_search():
    """Search users for admin interface (no pagination, default to auditor role)"""
    current_user = auth.current_user()

    # Get query parameters
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "auditor").strip()  # Default to auditor

    # Get users using shared function
    user_data = get_users_for_admin(
        search=search,
        role_filter=role_filter,
        for_index=False,
    )

    return jsonify(
        {
            "users": user_data["users_data"],
            "total_count": user_data["total_count"],
        }
    )


@bp.route("/users/<int:user_id>/details", methods=["GET"])
def user_details(user_id):
    """Get detailed user information including discussions and licenses"""
    current_user = auth.current_user()

    # Access control: admins can see any user, auditors can only see themselves
    if not current_user.has_role(vedana.ROLE_ADMIN):
        if not current_user.has_role(vedana.ROLE_AUDITOR) or current_user.id != user_id:
            return jsonify({"error": "Access denied"}), 403

    user = User.query.options(
        subqueryload(User.diagrams).subqueryload(Diagram.discussions),
        subqueryload(User.licenses).subqueryload(License.policy),
        subqueryload(User.licenses).subqueryload(License.activations),
    ).get_or_404(user_id)

    # Build detailed user data using build_user_summary for consistency
    user_data = build_user_summary(user, include_discussion_count=True)

    # Add full discussions data
    user_data["discussions"] = [
        discussion.as_dict(include=["summary", "last_topic", "statements"])
        for diagram in user.diagrams
        for discussion in diagram.discussions
    ]

    # Add detailed license data
    user_data["licenses"] = [
        license.as_dict(include=["policy", "activations"]) for license in user.licenses
    ]

    return jsonify(user_data)


@bp.route("/users/<int:user_id>/detail-html", methods=["GET"])
def user_detail_html(user_id):
    """Get detailed user information as HTML for modal"""
    current_user = auth.current_user()

    # Access control: admins can see any user, auditors can only see themselves
    if not current_user.has_role(vedana.ROLE_ADMIN):
        if not current_user.has_role(vedana.ROLE_AUDITOR) or current_user.id != user_id:
            return "<div class='notification is-danger'>Access denied</div>", 403

    user = User.query.options(
        subqueryload(User.diagrams)
        .subqueryload(Diagram.discussions)
        .subqueryload(Discussion.statements),
        subqueryload(User.licenses).subqueryload(License.policy),
        subqueryload(User.licenses).subqueryload(License.activations),
    ).get_or_404(user_id)

    # Build user summary data
    user_summary = build_user_summary(user, include_discussion_count=True)

    # Get all discussions from user's diagrams
    user_discussions = []
    for diagram in user.diagrams:
        for discussion in diagram.discussions:
            user_discussions.append(discussion)

    # Sort discussions by most recent first
    user_discussions.sort(key=lambda d: d.created_at, reverse=True)

    return render_template(
        "partials/user_detail_content.html",
        user=user,
        user_summary=user_summary,
        user_discussions=user_discussions,
        current_user=current_user,
        vedana=vedana,
        is_modal=True,
    )


@bp.route("/users/<int:user_id>/clear-database", methods=["DELETE"])
def user_clear_db(user_id):
    """Clear a user's database JSON column"""
    admin_user = auth.current_user()
    target_user = User.query.get_or_404(user_id)

    # Clear the user's free diagram database
    if target_user.free_diagram:

        target_user.free_diagram.set_database(Database.create_with_defaults())

    old_database = {}
    db.session.commit()

    _log.info(
        f"Admin {admin_user.username} cleared database for user "
        f"{target_user.username} (ID: {user_id})"
    )

    return jsonify(
        {
            "success": True,
            "message": f"Cleared database for user {target_user.username}. "
            f"Previous data contained {len(old_database)} top-level keys.",
        }
    )


@bp.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
def user_update(user_id):
    admin_user = auth.current_user()
    target_user = User.query.get_or_404(user_id)

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Track changes for logging
    changes = {}

    # Update roles if provided
    if "roles" in data:
        new_roles = data["roles"]

        # Validate roles
        valid_roles = ["subscriber", "admin", "auditor"]
        for role in new_roles:
            if role not in valid_roles:
                return (
                    jsonify(
                        {
                            "error": f"Invalid role: {role}. Valid roles are: {', '.join(valid_roles)}"
                        }
                    ),
                    400,
                )

        # Map frontend role names to vedana constants
        role_mapping = {
            "subscriber": vedana.ROLE_SUBSCRIBER,
            "admin": vedana.ROLE_ADMIN,
            "auditor": vedana.ROLE_AUDITOR,
        }

        # Convert to vedana role constants
        vedana_roles = [role_mapping[role] for role in new_roles]

        # Store old roles for logging
        old_roles = target_user.roles.split(",") if target_user.roles else []
        new_roles_str = (
            ",".join(vedana_roles) if vedana_roles else vedana.ROLE_SUBSCRIBER
        )

        if target_user.roles != new_roles_str:
            changes["roles"] = {"old": old_roles, "new": new_roles}
            target_user.roles = new_roles_str

    # Update other allowed fields
    allowed_fields = ["first_name", "last_name", "status", "active"]

    for field in allowed_fields:
        if field in data:
            old_value = getattr(target_user, field)
            new_value = data[field]

            # Validate status field
            if field == "status" and new_value not in ["pending", "confirmed"]:
                return (
                    jsonify(
                        {
                            "error": f"Invalid status: {new_value}. Must be 'pending' or 'confirmed'"
                        }
                    ),
                    400,
                )

            # Validate active field
            if field == "active" and not isinstance(new_value, bool):
                return jsonify({"error": "Active field must be a boolean"}), 400

            if old_value != new_value:
                changes[field] = {"old": old_value, "new": new_value}
                setattr(target_user, field, new_value)

    # Only commit if there were changes
    if changes:
        db.session.commit()

        _log.info(
            f"Admin {admin_user.username} updated user {target_user.username} (ID: {user_id}). "
            f"Changes: {changes}"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Updated user {target_user.username}",
                "changes": changes,
            }
        )
    else:
        return jsonify({"success": True, "message": "No changes made", "changes": {}})


@bp.route("/approve", methods=["POST"])
def approve():
    """Approve a statement extraction or feedback as ground truth for testing"""
    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    approve_type = data.get("type")  # "statement" or "feedback"
    if approve_type not in ["statement", "feedback"]:
        return (
            jsonify({"error": "Invalid type. Must be 'statement' or 'feedback'"}),
            400,
        )

    now = datetime.utcnow()

    if approve_type == "statement":
        statement_id = data.get("statement_id")
        if not statement_id:
            return jsonify({"error": "statement_id required"}), 400

        statement = Statement.query.get_or_404(statement_id)

        # Only approve Subject statements with extracted data
        if not (
            statement.speaker
            and statement.speaker.type.name == "Subject"
            and statement.pdp_deltas
        ):
            return (
                jsonify(
                    {"error": "Can only approve Subject statements with extracted data"}
                ),
                400,
            )

        # Toggle approval status
        if statement.approved:
            statement.approved = False
            statement.approved_by = None
            statement.approved_at = None
            statement.exported_at = (
                None  # Clear export timestamp so it can be re-exported
            )
            message = "Statement extraction approval removed"
        else:
            statement.approved = True
            statement.approved_by = current_user.username
            statement.approved_at = now
            message = "Statement extraction approved"

        db.session.commit()

        _log.info(
            f"Admin {current_user.username} {message.lower()} for statement {statement_id}"
        )

        return jsonify(
            {
                "success": True,
                "message": message,
                "approved": statement.approved,
                "approved_by": statement.approved_by,
                "approved_at": (
                    statement.approved_at.isoformat() if statement.approved_at else None
                ),
            }
        )

    elif approve_type == "feedback":
        feedback_id = data.get("feedback_id")
        if not feedback_id:
            return jsonify({"error": "feedback_id required"}), 400

        feedback = Feedback.query.get_or_404(feedback_id)

        # Only approve extraction feedback with edited data
        if not (feedback.feedback_type == "extraction" and feedback.edited_extraction):
            return (
                jsonify(
                    {"error": "Can only approve extraction feedback with edited data"}
                ),
                400,
            )

        # Toggle approval status
        if feedback.approved:
            feedback.approved = False
            feedback.approved_by = None
            feedback.approved_at = None
            feedback.exported_at = (
                None  # Clear export timestamp so it can be re-exported
            )
            message = "Feedback approval removed"
        else:
            # Before approving this feedback, unapprove any other feedback for the same statement
            # Only one feedback should be approved per statement
            other_approved_feedback = (
                Feedback.query.filter(Feedback.statement_id == feedback.statement_id)
                .filter(Feedback.feedback_type == "extraction")
                .filter(Feedback.approved == True)
                .filter(Feedback.id != feedback.id)
                .all()
            )

            for other_feedback in other_approved_feedback:
                other_feedback.approved = False
                other_feedback.approved_by = None
                other_feedback.approved_at = None
                other_feedback.exported_at = None
                _log.info(
                    f"Admin {current_user.username} auto-unapproved feedback {other_feedback.id} "
                    f"to approve feedback {feedback_id} for statement {feedback.statement_id}"
                )

            # Before approving feedback, unapprove the statement if it's approved
            # Only one approval should be active per statement (either AI or feedback)
            statement = Statement.query.get(feedback.statement_id)
            if statement and statement.approved:
                _log.warning(
                    f"MUTUAL EXCLUSIVITY: Admin {current_user.username} is approving feedback {feedback_id}, "
                    f"auto-unapproving AI statement {statement.id} (was approved by {statement.approved_by} at {statement.approved_at})"
                )
                statement.approved = False
                statement.approved_by = None
                statement.approved_at = None
                statement.exported_at = None

            # Now approve this feedback
            feedback.approved = True
            feedback.approved_by = current_user.username
            feedback.approved_at = now
            feedback.rejection_reason = None  # Clear any previous rejection
            message = "Feedback approved"

            if other_approved_feedback:
                message += f" (unapproved {len(other_approved_feedback)} other feedback for this statement)"

        db.session.commit()

        _log.info(
            f"Admin {current_user.username} {message.lower()} for feedback {feedback_id}"
        )

        return jsonify(
            {
                "success": True,
                "message": message,
                "approved": feedback.approved,
                "approved_by": feedback.approved_by,
                "approved_at": (
                    feedback.approved_at.isoformat() if feedback.approved_at else None
                ),
            }
        )


@bp.route("/export-test-cases", methods=["POST"])
def export_test_cases():
    """Export approved test cases that haven't been exported yet"""
    current_user = auth.current_user()

    # Import here to avoid circular imports
    from btcopilot.training.export_tests import export_approved_test_cases

    try:
        exported_count = export_approved_test_cases()

        _log.info(f"Admin {current_user.username} exported {exported_count} test cases")

        return jsonify(
            {
                "success": True,
                "message": f"Exported {exported_count} test cases to ./model_tests/data/",
                "count": exported_count,
            }
        )

    except Exception as e:
        _log.error(f"Error exporting test cases: {e}", exc_info=True)
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


@bp.route("/reject-feedback", methods=["POST"])
def reject_feedback():
    """Reject feedback with a reason"""
    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    feedback_id = data.get("feedback_id")
    rejection_reason = data.get("rejection_reason")

    if not feedback_id:
        return jsonify({"error": "feedback_id required"}), 400

    if not rejection_reason:
        return jsonify({"error": "rejection_reason required"}), 400

    feedback = Feedback.query.get_or_404(feedback_id)

    # Only reject extraction feedback
    if feedback.feedback_type != "extraction":
        return jsonify({"error": "Can only reject extraction feedback"}), 400

    # Set rejection reason and ensure it's not approved
    feedback.rejection_reason = rejection_reason
    feedback.approved = False
    feedback.approved_by = None
    feedback.approved_at = None
    feedback.exported_at = None

    db.session.commit()

    _log.info(
        f"Admin {current_user.username} rejected feedback {feedback_id}: {rejection_reason}"
    )

    return jsonify(
        {
            "success": True,
            "message": "Feedback rejected with reason",
            "rejection_reason": rejection_reason,
        }
    )


@bp.route("/approve-statement", methods=["POST"])
def approve_statement():
    """Approve the AI-generated extraction as correct (positive training example)"""
    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    statement_id = data.get("statement_id")
    if not statement_id:
        return jsonify({"error": "statement_id required"}), 400

    statement = Statement.query.get_or_404(statement_id)

    # Only approve statements with extraction data
    if not statement.pdp_deltas:
        return (
            jsonify({"error": "Can only approve statements with extraction data"}),
            400,
        )

    now = datetime.utcnow()

    # Before approving statement, unapprove any approved feedback for the same statement
    # Only one approval should be active per statement (either AI or feedback)
    approved_feedback = (
        Feedback.query.filter(Feedback.statement_id == statement_id)
        .filter(Feedback.feedback_type == "extraction")
        .filter(Feedback.approved == True)
        .all()
    )

    for feedback in approved_feedback:
        _log.warning(
            f"MUTUAL EXCLUSIVITY: Admin {current_user.username} is approving AI statement {statement_id}, "
            f"auto-unapproving feedback {feedback.id} (was approved by {feedback.approved_by} at {feedback.approved_at})"
        )
        feedback.approved = False
        feedback.approved_by = None
        feedback.approved_at = None
        feedback.exported_at = None

    # Mark statement as approved
    statement.approved = True
    statement.approved_by = current_user.username
    statement.approved_at = now

    db.session.commit()

    _log.info(
        f"Admin {current_user.username} approved AI extraction for statement {statement_id}"
    )

    return jsonify(
        {
            "success": True,
            "approved_statement_id": statement_id,
            "approved_by": current_user.username,
        }
    )


@bp.route("/quick-approve", methods=["POST"])
def quick_approve():
    """Quick approve feedback for inline review - same logic as main approve but returns minimal response"""
    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    feedback_id = data.get("feedback_id")
    if not feedback_id:
        return jsonify({"error": "feedback_id required"}), 400

    feedback = Feedback.query.get_or_404(feedback_id)

    # Only approve extraction feedback with edited data
    if not (feedback.feedback_type == "extraction" and feedback.edited_extraction):
        return (
            jsonify({"error": "Can only approve extraction feedback with edited data"}),
            400,
        )

    now = datetime.utcnow()

    # Before approving this feedback, unapprove any other feedback for the same statement
    other_approved_feedback = (
        Feedback.query.filter(Feedback.statement_id == feedback.statement_id)
        .filter(Feedback.feedback_type == "extraction")
        .filter(Feedback.approved == True)
        .filter(Feedback.id != feedback.id)
        .all()
    )

    for other_feedback in other_approved_feedback:
        other_feedback.approved = False
        other_feedback.approved_by = None
        other_feedback.approved_at = None
        other_feedback.exported_at = None

    # Before approving feedback, unapprove the statement if it's approved
    # Only one approval should be active per statement (either AI or feedback)
    statement = Statement.query.get(feedback.statement_id)
    if statement and statement.approved:
        _log.warning(
            f"MUTUAL EXCLUSIVITY (quick-approve): Admin {current_user.username} is approving feedback {feedback_id}, "
            f"auto-unapproving AI statement {statement.id} (was approved by {statement.approved_by} at {statement.approved_at})"
        )
        statement.approved = False
        statement.approved_by = None
        statement.approved_at = None
        statement.exported_at = None

    # Approve this feedback
    feedback.approved = True
    feedback.approved_by = current_user.username
    feedback.approved_at = now
    feedback.rejection_reason = None

    db.session.commit()

    _log.info(f"Admin {current_user.username} quick-approved feedback {feedback_id}")

    return jsonify(
        {
            "success": True,
            "approved_feedback_id": feedback_id,
            "approved_by": current_user.username,
            "statement_id": feedback.statement_id,
        }
    )


@bp.route("/unapprove-feedback", methods=["POST"])
@minimum_role(vedana.ROLE_ADMIN)
def unapprove_feedback():
    data = request.get_json()
    feedback_id = data.get("feedback_id")

    if not feedback_id:
        return jsonify({"error": "feedback_id is required"}), 400

    feedback = Feedback.query.get(feedback_id)
    if not feedback:
        return jsonify({"error": "Feedback not found"}), 404

    # Unapprove the feedback
    feedback.approved = False
    feedback.approved_by = None
    feedback.approved_at = None
    feedback.exported_at = None

    db.session.commit()

    current_user = auth.current_user()
    _log.info(f"Admin {current_user.username} unapproved feedback {feedback_id}")

    return jsonify(
        {
            "success": True,
            "unapproved_feedback_id": feedback_id,
            "statement_id": feedback.statement_id,
        }
    )


@bp.route("/unapprove-statement", methods=["POST"])
@minimum_role(vedana.ROLE_ADMIN)
def unapprove_statement():
    data = request.get_json()
    statement_id = data.get("statement_id")

    if not statement_id:
        return jsonify({"error": "statement_id is required"}), 400

    statement = Statement.query.get(statement_id)
    if not statement:
        return jsonify({"error": "Statement not found"}), 404

    # Unapprove the statement
    statement.approved = False
    statement.approved_by = None
    statement.approved_at = None
    statement.exported_at = None

    db.session.commit()

    current_user = auth.current_user()
    _log.info(f"Admin {current_user.username} unapproved statement {statement_id}")

    return jsonify({"success": True, "unapproved_statement_id": statement_id})
