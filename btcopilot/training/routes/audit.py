import logging
from flask import Blueprint, render_template, request, session

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram, License, AccessRight
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

    # Get diagrams with granted access
    shared_diagrams_query = (
        db.session.query(Diagram, AccessRight)
        .join(AccessRight, AccessRight.diagram_id == Diagram.id)
        .filter(AccessRight.user_id == auditor.id)
        .options(
            db.subqueryload(Diagram.discussions).subqueryload(Discussion.statements)
        )
    )
    shared_diagrams_with_rights = shared_diagrams_query.all()

    # Get all discussions from owned and shared diagrams
    user_discussions = []
    for diagram in auditor.diagrams:
        for discussion in diagram.discussions:
            user_discussions.append(discussion)
    for diagram, access_right in shared_diagrams_with_rights:
        for discussion in diagram.discussions:
            user_discussions.append(discussion)

    user_discussions.sort(key=lambda d: d.created_at, reverse=True)

    # Calculate F1 metrics for approved ground truth
    from btcopilot.training.f1_metrics import calculate_system_f1

    f1_metrics = calculate_system_f1()

    breadcrumbs = get_breadcrumbs("audit")

    return render_template(
        "auditor_dashboard.html",
        user=auditor,
        user_discussions=user_discussions,
        shared_diagrams_with_rights=shared_diagrams_with_rights,
        current_user=user,
        btcopilot=btcopilot,
        breadcrumbs=breadcrumbs,
        f1_metrics=f1_metrics,
    )
