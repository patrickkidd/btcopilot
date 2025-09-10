"""
Admin interface for training data management and review.

Provides web interface for administrators to manage users, approve training data,
export test cases, and oversee the training data collection process. Uses 
stand-in implementations that should be extended by the parent application.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

from ..auth import require_admin, get_current_user
from ..models import Discussion, Statement, Feedback, get_session
from ..utils import get_breadcrumbs

_log = logging.getLogger(__name__)

# Create the admin blueprint
admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates",
    static_folder="../static",
)

# Note: Authentication/authorization should be provided by parent application

# Simple in-memory cache for feedback statistics
_feedback_stats_cache = {}
_feedback_stats_cache_time = None


def get_feedback_statistics():
    """Get feedback statistics with 5-minute caching - stand-in implementation"""
    import time

    global _feedback_stats_cache, _feedback_stats_cache_time

    current_time = time.time()

    # Check if cache is valid (5 minutes = 300 seconds)
    if (
        _feedback_stats_cache_time
        and current_time - _feedback_stats_cache_time < 300
        and _feedback_stats_cache
    ):
        return _feedback_stats_cache

    # Stand-in statistics calculation
    total_feedbacks = Feedback.query.count()
    conversation_feedbacks = Feedback.query.filter_by(feedback_type="conversation").count()
    extraction_feedbacks = Feedback.query.filter_by(feedback_type="extraction").count()
    thumbs_down_count = Feedback.query.filter_by(thumbs_down=True).count()
    
    # Count unique auditors (simplified)
    unique_auditors = len(set(f.auditor_id for f in Feedback.query.all()))

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


def build_user_summary(user_data, include_discussion_count=True):
    """Build summary data for a user - stand-in implementation"""
    # Stand-in user summary since we don't have User model
    return {
        "id": user_data.get("id", 1),
        "username": user_data.get("username", "unknown"),
        "full_name": user_data.get("full_name", "Unknown User"),
        "roles": user_data.get("roles", ["auditor"]),
        "status": user_data.get("status", "active"),
        "active": user_data.get("active", True),
        "discussion_count": 0 if not include_discussion_count else user_data.get("discussion_count", 0),
        "license_count": user_data.get("license_count", 0),
        "diagram_count": user_data.get("diagram_count", 0),
        "created_at": user_data.get("created_at"),
    }


@admin_bp.route("/")
def index():
    """Admin dashboard - stand-in implementation"""
    # Stand-in user
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    # Get discussions with simplified loading
    discussions = Discussion.query.limit(50).all()

    # Stand-in user data
    users_data = [
        {
            "id": 1,
            "username": "admin",
            "full_name": "Admin User",
            "roles": ["admin"],
            "status": "active",
            "active": True,
            "discussion_count": len(discussions),
            "license_count": 1,
            "diagram_count": 1,
        }
    ]

    # Get feedback statistics
    feedback_stats = get_feedback_statistics()

    breadcrumbs = get_breadcrumbs("admin")

    return render_template(
        "admin_dashboard.html",
        discussions=discussions,
        users=users_data,
        users_summary=users_data,
        total_user_count=1,
        showing_user_count=1,
        feedback_stats=feedback_stats,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
    )


@admin_bp.route("/users", methods=["GET"])
def users_list():
    """Get all users for admin interface - stand-in implementation"""
    # Stand-in user data
    users_data = [
        {
            "id": 1,
            "username": "admin",
            "full_name": "Admin User",
            "roles": ["admin"],
            "status": "active",
            "active": True,
            "discussion_count": Discussion.query.count(),
            "license_count": 1,
            "diagram_count": 1,
        }
    ]

    return jsonify(
        {
            "users": users_data,
            "total_count": len(users_data),
        }
    )


@admin_bp.route("/users/search", methods=["GET"])
def users_search():
    """Search users for admin interface - stand-in implementation"""
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "auditor").strip()

    # Stand-in search logic
    users_data = [
        {
            "id": 1,
            "username": "admin",
            "full_name": "Admin User",
            "roles": ["admin"],
            "status": "active",
            "active": True,
            "discussion_count": Discussion.query.count(),
            "license_count": 1,
            "diagram_count": 1,
        }
    ]

    # Simple filtering
    if search and search.lower() not in "admin":
        users_data = []

    return jsonify(
        {
            "users": users_data,
            "total_count": len(users_data),
        }
    )


@admin_bp.route("/approve", methods=["POST"])
def approve():
    """Approve a statement extraction or feedback - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

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

        # Toggle approval status - stand-in implementation
        if statement.approved:
            statement.approved = False
            statement.approved_by = None
            statement.approved_at = None
            statement.exported_at = None
            message = "Statement extraction approval removed"
        else:
            statement.approved = True
            statement.approved_by = current_user["username"]
            statement.approved_at = now
            message = "Statement extraction approved"

        # Note: Parent app should provide database session
        # db.session.commit()

        _log.info(
            f"Admin {current_user['username']} {message.lower()} for statement {statement_id}"
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

        # Toggle approval status - stand-in implementation
        if feedback.approved:
            feedback.approved = False
            feedback.approved_by = None
            feedback.approved_at = None
            feedback.exported_at = None
            message = "Feedback approval removed"
        else:
            feedback.approved = True
            feedback.approved_by = current_user["username"]
            feedback.approved_at = now
            feedback.rejection_reason = None
            message = "Feedback approved"

        # Note: Parent app should provide database session
        # db.session.commit()

        _log.info(
            f"Admin {current_user['username']} {message.lower()} for feedback {feedback_id}"
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


@admin_bp.route("/export-test-cases", methods=["POST"])
def export_test_cases():
    """Export approved test cases - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    # Stand-in export logic
    exported_count = 0

    # Count approved statements and feedback
    approved_statements = Statement.query.filter_by(approved=True).count()
    approved_feedback = Feedback.query.filter_by(approved=True).count()
    exported_count = approved_statements + approved_feedback

    _log.info(f"Admin {current_user['username']} exported {exported_count} test cases")

    return jsonify(
        {
            "success": True,
            "message": f"Stand-in export: {exported_count} test cases would be exported",
            "count": exported_count,
            "note": "Stand-in implementation - parent app should provide actual export functionality"
        }
    )


@admin_bp.route("/reject-feedback", methods=["POST"])
def reject_feedback():
    """Reject feedback with a reason - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

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

    # Set rejection reason and ensure it's not approved
    feedback.rejection_reason = rejection_reason
    feedback.approved = False
    feedback.approved_by = None
    feedback.approved_at = None
    feedback.exported_at = None

    # Note: Parent app should provide database session
    # db.session.commit()

    _log.info(
        f"Admin {current_user['username']} rejected feedback {feedback_id}: {rejection_reason}"
    )

    return jsonify(
        {
            "success": True,
            "message": "Feedback rejected with reason",
            "rejection_reason": rejection_reason,
        }
    )


@admin_bp.route("/approve-statement", methods=["POST"])
def approve_statement():
    """Approve the AI-generated extraction - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    statement_id = data.get("statement_id")
    if not statement_id:
        return jsonify({"error": "statement_id required"}), 400

    statement = Statement.query.get_or_404(statement_id)

    if not statement.pdp_deltas:
        return (
            jsonify({"error": "Can only approve statements with extraction data"}),
            400,
        )

    now = datetime.utcnow()

    # Mark statement as approved
    statement.approved = True
    statement.approved_by = current_user["username"]
    statement.approved_at = now

    # Note: Parent app should provide database session
    # db.session.commit()

    _log.info(
        f"Admin {current_user['username']} approved AI extraction for statement {statement_id}"
    )

    return jsonify(
        {
            "success": True,
            "approved_statement_id": statement_id,
            "approved_by": current_user["username"],
        }
    )


@admin_bp.route("/quick-approve", methods=["POST"])
def quick_approve():
    """Quick approve feedback - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    feedback_id = data.get("feedback_id")
    if not feedback_id:
        return jsonify({"error": "feedback_id required"}), 400

    feedback = Feedback.query.get_or_404(feedback_id)

    if not (feedback.feedback_type == "extraction" and feedback.edited_extraction):
        return (
            jsonify({"error": "Can only approve extraction feedback with edited data"}),
            400,
        )

    now = datetime.utcnow()

    # Approve this feedback
    feedback.approved = True
    feedback.approved_by = current_user["username"]
    feedback.approved_at = now
    feedback.rejection_reason = None

    # Note: Parent app should provide database session
    # db.session.commit()

    _log.info(f"Admin {current_user['username']} quick-approved feedback {feedback_id}")

    return jsonify(
        {
            "success": True,
            "approved_feedback_id": feedback_id,
            "approved_by": current_user["username"],
            "statement_id": feedback.statement_id,
        }
    )


@admin_bp.route("/unapprove-feedback", methods=["POST"])
def unapprove_feedback():
    """Unapprove feedback - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    data = request.get_json()
    feedback_id = data.get("feedback_id")

    if not feedback_id:
        return jsonify({"error": "feedback_id is required"}), 400

    feedback = Feedback.query.get_or_404(feedback_id)

    # Unapprove the feedback
    feedback.approved = False
    feedback.approved_by = None
    feedback.approved_at = None
    feedback.exported_at = None

    # Note: Parent app should provide database session
    # db.session.commit()

    _log.info(f"Admin {current_user['username']} unapproved feedback {feedback_id}")

    return jsonify(
        {
            "success": True,
            "unapproved_feedback_id": feedback_id,
            "statement_id": feedback.statement_id,
        }
    )


@admin_bp.route("/unapprove-statement", methods=["POST"])
def unapprove_statement():
    """Unapprove statement - stand-in implementation"""
    current_user = {"id": 1, "username": "admin", "role": "admin"}

    data = request.get_json()
    statement_id = data.get("statement_id")

    if not statement_id:
        return jsonify({"error": "statement_id is required"}), 400

    statement = Statement.query.get_or_404(statement_id)

    # Unapprove the statement
    statement.approved = False
    statement.approved_by = None
    statement.approved_at = None
    statement.exported_at = None

    # Note: Parent app should provide database session
    # db.session.commit()

    _log.info(f"Admin {current_user['username']} unapproved statement {statement_id}")

    return jsonify({"success": True, "unapproved_statement_id": statement_id})