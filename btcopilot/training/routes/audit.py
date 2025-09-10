"""
Audit routes for training data collection and review.

Provides web interface for auditors to review AI extractions, provide feedback,
and manage training data quality. Uses placeholder authentication that should
be overridden by the parent application.
"""

import logging
from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from datetime import datetime

from ..auth import require_auditor_or_admin, get_current_user, get_auditor_id
from ..models import Discussion, Statement
from ...extensions import db
from ..utils import get_breadcrumbs

_log = logging.getLogger(__name__)

# Create the audit blueprint
audit_bp = Blueprint(
    "audit",
    __name__,
    url_prefix="/audit",
    template_folder="../templates",
    static_folder="../static",
)

# Note: Authentication/authorization should be provided by parent application


@audit_bp.route("/")
@require_auditor_or_admin
def index():
    """
    Audit dashboard showing available discussions for review.
    
    This is a stand-in implementation. Parent application should override
    with proper user management and data access controls.
    """
    # Stand-in user simulation - parent app should provide real user
    current_user = {"id": 1, "username": "auditor", "role": "auditor"}
    
    # Get discussions for auditing (simplified query)
    discussions = Discussion.query.limit(50).all()
    
    # Sort discussions by most recent first
    discussions.sort(key=lambda d: d.created_at, reverse=True)

    breadcrumbs = get_breadcrumbs("audit")
    
    # Stand-in user summary
    user_summary = {
        "total_discussions": len(discussions),
        "statements_with_extractions": 0,
        "approved_statements": 0,
        "feedback_given": 0,
    }

    return render_template(
        "audit_index.html",
        discussions=discussions,
        user_summary=user_summary,
        current_user=current_user,
        breadcrumbs=breadcrumbs,
    )


@audit_bp.route("/discussion/<int:discussion_id>")
def review_discussion(discussion_id):
    """
    Review a specific discussion and its statements.
    
    Provides interface for auditing AI extractions and providing feedback.
    """
    discussion = Discussion.query.get_or_404(discussion_id)
    
    # Stand-in user
    current_user = {"id": 1, "username": "auditor", "role": "auditor"}
    
    breadcrumbs = get_breadcrumbs("thread")
    
    return render_template(
        "discussion_audit.html",
        discussion=discussion,
        current_user=current_user,
        breadcrumbs=breadcrumbs,
    )