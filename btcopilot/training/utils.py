"""Common utilities for therapist module"""

from flask import url_for
from btcopilot import auth
import vedana


def get_breadcrumbs(current_page=None):
    """Generate breadcrumbs for therapist pages"""
    breadcrumbs = [
        {"title": "Therapist", "url": url_for("training.therapist_root")},
    ]

    if current_page == "audit":
        breadcrumbs.append({"title": "Audit", "url": None})
    elif current_page == "admin":
        breadcrumbs.append({"title": "Admin", "url": None})
    elif current_page == "admin_feedback":
        breadcrumbs.extend(
            [
                {"title": "Admin", "url": url_for("training.admin.index")},
                {"title": "Feedback", "url": None},
            ]
        )
    elif current_page == "thread":
        breadcrumbs.append({"title": "Audit", "url": url_for("training.audit.index")})
    elif current_page == "prompts":
        breadcrumbs.append({"title": "Prompt Lab", "url": None})

    return breadcrumbs


def check_admin_access():
    """Check if current user has admin access"""
    user = auth.current_user()
    return user and user.has_role(vedana.ROLE_ADMIN)


def get_auditor_id(request, session):
    """Get auditor ID from request headers or use current user's ID"""
    # First check for explicit header (for testing)
    if request.headers.get("X-Auditor-Id"):
        return request.headers.get("X-Auditor-Id")

    # Use current user's ID as auditor ID
    user = auth.current_user()
    if user and user.id:
        return str(user.id)  # Convert to string for consistency

    # This shouldn't happen in practice since routes require login
    return "anonymous"
