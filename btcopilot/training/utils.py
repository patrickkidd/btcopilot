"""Common utilities for therapist module"""

from enum import Enum

from flask import url_for
from sqlalchemy import func

from btcopilot import auth
import btcopilot
from btcopilot.extensions import db


class GTStatus(Enum):
    None_ = "none"
    Partial = "partial"
    Full = "full"


def get_discussion_gt_statuses(discussion_ids):
    """
    Return dict: discussion_id -> {'total': int, 'approved': int, 'status': GTStatus}

    Only one auditor's feedbacks are approved per discussion (via bulk approve).
    Status is Full when all of that auditor's edited feedbacks are approved.
    """
    from btcopilot.training.models import Feedback
    from btcopilot.personal.models import Statement

    if not discussion_ids:
        return {}

    result = {}
    for did in discussion_ids:
        # Find the approved auditor for this discussion (if any)
        approved_auditor = (
            db.session.query(Feedback.auditor_id)
            .join(Statement)
            .filter(
                Statement.discussion_id == did,
                Feedback.feedback_type == "extraction",
                Feedback.approved == True,
            )
            .first()
        )

        if not approved_auditor:
            result[did] = {"total": 0, "approved": 0, "status": GTStatus.None_}
            continue

        auditor_id = approved_auditor[0]

        # Count that auditor's feedbacks with edited_extraction
        total = (
            Feedback.query.join(Statement)
            .filter(
                Statement.discussion_id == did,
                Feedback.feedback_type == "extraction",
                Feedback.auditor_id == auditor_id,
                Feedback.edited_extraction.isnot(None),
            )
            .count()
        )

        # Count that auditor's approved feedbacks
        approved = (
            Feedback.query.join(Statement)
            .filter(
                Statement.discussion_id == did,
                Feedback.feedback_type == "extraction",
                Feedback.auditor_id == auditor_id,
                Feedback.edited_extraction.isnot(None),
                Feedback.approved == True,
            )
            .count()
        )

        if total == 0:
            status = GTStatus.None_
        elif approved == total:
            status = GTStatus.Full
        else:
            status = GTStatus.Partial

        result[did] = {"total": total, "approved": approved, "status": status}

    return result


def get_breadcrumbs(current_page=None):
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
    user = auth.current_user()
    return user and user.has_role(btcopilot.ROLE_ADMIN)


def get_auditor_id(request, session):
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


def get_discussion_view_menu(discussion_id, active_view):
    """Build breadcrumb dropdown menu for discussion-level views. Returns (menu, active_title)."""
    titles = {"coding": "Coding", "f1": "F1 Analysis", "irr": "IRR Analysis", "matrix": "Pairwise Matrix"}
    menu = [
        {"title": "Coding", "url": url_for("training.discussions.audit", discussion_id=discussion_id), "icon": "edit", "active": active_view == "coding"},
        {"title": "F1 Analysis", "url": url_for("training.analysis.discussion_analysis", discussion_id=discussion_id), "icon": "chart-bar", "active": active_view == "f1"},
        {"divider": True},
        {"title": "IRR Analysis", "url": url_for("training.irr.discussion", discussion_id=discussion_id), "icon": "users", "active": active_view == "irr"},
        {"title": "Pairwise Matrix", "url": url_for("training.irr.pairwise_matrix", discussion_id=discussion_id), "icon": "th", "active": active_view == "matrix"},
    ]
    return menu, titles.get(active_view, "")
