"""
Inter-Rater Reliability Analysis Routes

Views for analyzing agreement between human coders:
1. IRR Dashboard: List discussions with multiple coders
2. Discussion IRR: Detailed analysis for one discussion
3. Pairwise Matrix: Coder-by-coder comparison
4. System IRR: Aggregate across all multi-coder discussions
"""

from flask import Blueprint, abort, render_template, url_for

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.personal.models import Discussion
from btcopilot.training.irr_metrics import (
    calculate_discussion_irr,
    calculate_statement_irr,
    get_multi_coder_discussions,
    safe_avg,
)

bp = Blueprint("irr", __name__, url_prefix="/irr")


@bp.route("/")
@minimum_role(btcopilot.ROLE_AUDITOR)
def index():
    multi_coder = get_multi_coder_discussions()

    discussions_data = []
    for discussion_id, coder_count, coder_ids in multi_coder:
        discussion = Discussion.query.get(discussion_id)
        if not discussion:
            continue

        irr = calculate_discussion_irr(discussion_id)
        discussions_data.append(
            {
                "discussion": discussion,
                "coder_count": coder_count,
                "coders": irr.coders if irr else coder_ids,
                "statement_count": irr.coded_statement_count if irr else 0,
                "avg_events_f1": irr.avg_events_f1 if irr else None,
                "avg_aggregate_f1": irr.avg_aggregate_f1 if irr else None,
                "avg_symptom_kappa": irr.avg_symptom_kappa if irr else None,
                "avg_anxiety_kappa": irr.avg_anxiety_kappa if irr else None,
                "avg_relationship_kappa": irr.avg_relationship_kappa if irr else None,
                "avg_functioning_kappa": irr.avg_functioning_kappa if irr else None,
            }
        )

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "Inter-Rater Reliability", "url": None},
    ]

    return render_template(
        "training/irr_index.html",
        discussions=discussions_data,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/discussion/<int:discussion_id>")
@minimum_role(btcopilot.ROLE_AUDITOR)
def discussion(discussion_id: int):
    from btcopilot.personal.models import Statement

    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available for this discussion")

    statements = (
        Statement.query.filter_by(discussion_id=discussion_id)
        .order_by(Statement.order)
        .all()
    )
    statement_irrs = []

    for stmt in statements:
        stmt_irr = calculate_statement_irr(stmt.id)
        statement_irrs.append(
            {
                "statement": stmt,
                "irr": stmt_irr,
            }
        )

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {"title": disc.summary or f"Discussion {discussion_id}", "url": None},
    ]

    return render_template(
        "training/irr_discussion.html",
        discussion=disc,
        discussion_irr=irr,
        statement_irrs=statement_irrs,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/discussion/<int:discussion_id>/matrix")
@minimum_role(btcopilot.ROLE_AUDITOR)
def pairwise_matrix(discussion_id: int):
    disc = Discussion.query.get_or_404(discussion_id)

    irr = calculate_discussion_irr(discussion_id)
    if not irr:
        abort(404, "No multi-coder data available")

    coders = sorted(irr.coders)
    matrix = {}

    for pair in irr.pairwise_metrics:
        key_ab = (pair.coder_a, pair.coder_b)
        key_ba = (pair.coder_b, pair.coder_a)
        matrix[key_ab] = pair
        matrix[key_ba] = pair

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {
            "title": disc.summary or f"Discussion {discussion_id}",
            "url": url_for("training.irr.discussion", discussion_id=discussion_id),
        },
        {"title": "Pairwise Matrix", "url": None},
    ]

    return render_template(
        "training/irr_matrix.html",
        discussion=disc,
        coders=coders,
        matrix=matrix,
        discussion_irr=irr,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )


@bp.route("/system")
@minimum_role(btcopilot.ROLE_AUDITOR)
def system():
    multi_coder = get_multi_coder_discussions()
    discussion_ids = [row[0] for row in multi_coder]

    all_irrs = []
    for did in discussion_ids:
        irr = calculate_discussion_irr(did)
        if irr:
            all_irrs.append(irr)

    if not all_irrs:
        abort(404, "No multi-coder discussions available")

    system_metrics = {
        "discussion_count": len(all_irrs),
        "total_statements": sum(irr.coded_statement_count for irr in all_irrs),
        "avg_events_f1": safe_avg([irr.avg_events_f1 for irr in all_irrs]),
        "avg_aggregate_f1": safe_avg([irr.avg_aggregate_f1 for irr in all_irrs]),
        "avg_symptom_kappa": safe_avg([irr.avg_symptom_kappa for irr in all_irrs]),
        "avg_anxiety_kappa": safe_avg([irr.avg_anxiety_kappa for irr in all_irrs]),
        "avg_relationship_kappa": safe_avg(
            [irr.avg_relationship_kappa for irr in all_irrs]
        ),
        "avg_functioning_kappa": safe_avg(
            [irr.avg_functioning_kappa for irr in all_irrs]
        ),
    }

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {"title": "IRR", "url": url_for("training.irr.index")},
        {"title": "System-Wide", "url": None},
    ]

    return render_template(
        "training/irr_system.html",
        system_metrics=system_metrics,
        discussion_irrs=all_irrs,
        breadcrumbs=breadcrumbs,
        current_user=auth.current_user(),
    )
