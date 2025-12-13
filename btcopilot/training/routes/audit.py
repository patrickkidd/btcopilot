import logging
from flask import Blueprint, render_template, request, session

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram, License, AccessRight
from btcopilot.personal.models import Discussion
from btcopilot.training.utils import (
    get_breadcrumbs,
    get_auditor_id,
    get_discussion_gt_statuses,
    GtStatus,
)


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
    current_user = auth.current_user()

    # Admins can view other users' audit dashboards via ?user_id=X
    target_user_id = request.args.get("user_id", type=int)
    if target_user_id and current_user.has_role(btcopilot.ROLE_ADMIN):
        viewing_user_id = target_user_id
    else:
        viewing_user_id = current_user.id

    # Load target user's data with all relationships
    auditor = User.query.options(
        db.subqueryload(User.diagrams)
        .subqueryload(Diagram.discussions)
        .subqueryload(Discussion.statements),
        db.subqueryload(User.licenses).subqueryload(License.policy),
        db.subqueryload(User.licenses).subqueryload(License.activations),
    ).get(viewing_user_id)

    if not auditor:
        from flask import abort

        abort(404)

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
    all_discussions = []
    for diagram in auditor.diagrams:
        for discussion in diagram.discussions:
            all_discussions.append(discussion)
    for diagram, access_right in shared_diagrams_with_rights:
        for discussion in diagram.discussions:
            all_discussions.append(discussion)

    # Compute GT statuses for all discussions
    discussion_ids = [d.id for d in all_discussions]
    gt_statuses = get_discussion_gt_statuses(discussion_ids)

    # Sort: Full GT first, then Partial, then None; within each group by created_at desc
    gt_sort_order = {GtStatus.Full: 0, GtStatus.Partial: 1, GtStatus.None_: 2}

    def sort_key(d):
        gt = gt_statuses.get(d.id, {})
        status = gt.get("status", GtStatus.None_)
        return (
            gt_sort_order.get(status, 2),
            -(d.created_at.timestamp() if d.created_at else 0),
        )

    all_discussions.sort(key=sort_key)

    # Calculate F1 metrics for approved ground truth
    from btcopilot.training.f1_metrics import calculate_system_f1

    f1_metrics = calculate_system_f1()

    breadcrumbs = get_breadcrumbs("audit")

    # Add user info to breadcrumbs if viewing another user (admin only)
    viewing_other_user = viewing_user_id != current_user.id
    if viewing_other_user:
        breadcrumbs.append({"title": auditor.username, "url": None})

    return render_template(
        "auditor_dashboard.html",
        user=auditor,
        user_discussions=all_discussions,
        shared_diagrams_with_rights=shared_diagrams_with_rights,
        current_user=current_user,
        btcopilot=btcopilot,
        breadcrumbs=breadcrumbs,
        f1_metrics=f1_metrics,
        viewing_other_user=viewing_other_user,
        gt_statuses=gt_statuses,
        GtStatus=GtStatus,
    )
