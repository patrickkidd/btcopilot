"""Common utilities for therapist module"""

from enum import Enum

from flask import url_for
from sqlalchemy import func

from btcopilot import auth
import btcopilot
from btcopilot.extensions import db


class GtStatus(Enum):
    """Ground truth approval status for a discussion"""

    None_ = "none"
    Partial = "partial"
    Full = "full"


def get_discussion_gt_statuses(discussion_ids):
    """
    Return dict: discussion_id -> {'total': int, 'approved': int, 'status': GtStatus}
    """
    from btcopilot.training.models import Feedback
    from btcopilot.personal.models import Statement

    if not discussion_ids:
        return {}

    totals = (
        db.session.query(Statement.discussion_id, func.count(Feedback.id))
        .join(Feedback)
        .filter(
            Statement.discussion_id.in_(discussion_ids),
            Feedback.feedback_type == "extraction",
        )
        .group_by(Statement.discussion_id)
        .all()
    )

    approved = (
        db.session.query(Statement.discussion_id, func.count(Feedback.id))
        .join(Feedback)
        .filter(
            Statement.discussion_id.in_(discussion_ids),
            Feedback.feedback_type == "extraction",
            Feedback.approved == True,
        )
        .group_by(Statement.discussion_id)
        .all()
    )

    totals_map = dict(totals)
    approved_map = dict(approved)

    result = {}
    for did in discussion_ids:
        total = totals_map.get(did, 0)
        appr = approved_map.get(did, 0)
        if total == 0:
            status = GtStatus.None_
        elif appr == total:
            status = GtStatus.Full
        elif appr > 0:
            status = GtStatus.Partial
        else:
            status = GtStatus.None_
        result[did] = {"total": total, "approved": appr, "status": status}
    return result


def get_breadcrumbs(current_page=None):
    """Generate breadcrumbs for training pages"""
    breadcrumbs = []

    if current_page == "audit":
        breadcrumbs.append({"title": "Coding", "url": None})
    elif current_page == "account":
        breadcrumbs.append({"title": "Account", "url": None})
    elif current_page == "admin":
        breadcrumbs.append({"title": "Admin", "url": None})
    elif current_page == "thread":
        breadcrumbs.append({"title": "Coding", "url": url_for("training.audit.index")})
    elif current_page == "prompts":
        breadcrumbs.append({"title": "Prompt Lab", "url": None})
    elif current_page == "synthetic":
        breadcrumbs.append({"title": "Synthetic", "url": None})

    return breadcrumbs


def check_admin_access():
    """Check if current user has admin access"""
    user = auth.current_user()
    return user and user.has_role(btcopilot.ROLE_ADMIN)


def get_auditor_id(request, session):
    """Get auditor ID from request headers or use current user's username"""
    # First check for explicit header (for testing)
    if request.headers.get("X-Auditor-Id"):
        return request.headers.get("X-Auditor-Id")

    # Use current user's username as auditor ID (not numeric ID)
    # The Feedback model stores auditor_id as username/email string
    user = auth.current_user()
    if user and user.username:
        return user.username

    # This shouldn't happen in practice since routes require login
    return "anonymous"
