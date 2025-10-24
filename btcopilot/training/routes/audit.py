import logging
from flask import Blueprint, render_template, request, session

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram, License
from btcopilot.personal.models import Discussion
from btcopilot.training.utils import get_breadcrumbs, get_auditor_id


_log = logging.getLogger(__name__)

# Create the audit blueprint
bp = Blueprint(
    "audit",
    __name__,
    url_prefix="/audit",
    template_folder="../templates",
    static_folder="../static",
)
bp = minimum_role(btcopilot.ROLE_AUDITOR)(bp)


@bp.route("/")
def index():
    user = auth.current_user()

    # Load auditor's own data with all relationships
    auditor = User.query.options(
        db.subqueryload(User.diagrams)
        .subqueryload(Diagram.discussions)
        .subqueryload(Discussion.statements),
        db.subqueryload(User.licenses).subqueryload(License.policy),
        db.subqueryload(User.licenses).subqueryload(License.activations),
    ).get(user.id)

    # Build user summary data
    from btcopilot.training.routes.admin import build_user_summary

    user_summary = build_user_summary(auditor, include_discussion_count=True)

    # Get all discussions from auditor's diagrams
    user_discussions = []
    for diagram in auditor.diagrams:
        for discussion in diagram.discussions:
            user_discussions.append(discussion)

    # Sort discussions by most recent first
    user_discussions.sort(key=lambda d: d.created_at, reverse=True)

    breadcrumbs = get_breadcrumbs("audit")

    return render_template(
        "auditor_dashboard.html",
        user=auditor,
        user_summary=user_summary,
        user_discussions=user_discussions,
        current_user=user,
        btcopilot=btcopilot,
        breadcrumbs=breadcrumbs,
    )
