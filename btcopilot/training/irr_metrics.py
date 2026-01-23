"""Inter-Rater Reliability metrics: agreement and F1 scores between human coders."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from sklearn.metrics import cohen_kappa_score

from btcopilot.schema import PDPDeltas, from_dict
from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    match_pair_bonds,
    calculate_f1_from_counts,
    F1Metrics,
)

_log = logging.getLogger(__name__)

SARF_VARIABLES = ["symptom", "anxiety", "relationship", "functioning"]


@dataclass
class CoderPairMetrics:
    coder_a: str
    coder_b: str
    people_f1: float = 0.0
    events_f1: float = 0.0
    pair_bonds_f1: float = 0.0
    aggregate_f1: float = 0.0
    symptom_kappa: float | None = None
    anxiety_kappa: float | None = None
    relationship_kappa: float | None = None
    functioning_kappa: float | None = None
    percent_agreement: float = 0.0
    matched_event_count: int = 0


@dataclass
class StatementIRRMetrics:
    statement_id: int
    coders: list[str] = field(default_factory=list)
    coder_pairs: list[CoderPairMetrics] = field(default_factory=list)
    avg_people_f1: float | None = None
    avg_events_f1: float | None = None
    avg_aggregate_f1: float | None = None
    avg_symptom_kappa: float | None = None
    avg_anxiety_kappa: float | None = None
    avg_relationship_kappa: float | None = None
    avg_functioning_kappa: float | None = None


@dataclass
class DiscussionIRRMetrics:
    discussion_id: int
    coders: list[str] = field(default_factory=list)
    statement_count: int = 0
    coded_statement_count: int = 0
    pairwise_metrics: list[CoderPairMetrics] = field(default_factory=list)
    fleiss_symptom: float | None = None
    fleiss_anxiety: float | None = None
    fleiss_relationship: float | None = None
    fleiss_functioning: float | None = None
    avg_events_f1: float | None = None
    avg_aggregate_f1: float | None = None
    avg_symptom_kappa: float | None = None
    avg_anxiety_kappa: float | None = None
    avg_relationship_kappa: float | None = None
    avg_functioning_kappa: float | None = None


def safe_avg(values: list[float | None]) -> float | None:
    """Average non-None values, return None if no valid values."""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def calculate_cohens_kappa(values_a: list[str], values_b: list[str]) -> float | None:
    if len(values_a) < 2 or len(values_b) < 2:
        return None
    if len(values_a) != len(values_b):
        return None
    try:
        return cohen_kappa_score(values_a, values_b)
    except ValueError:
        return None


def calculate_fleiss_kappa(ratings_matrix: list[list[int]]) -> float | None:
    if not ratings_matrix or len(ratings_matrix) < 2:
        return None

    n_items = len(ratings_matrix)
    n_categories = len(ratings_matrix[0])
    n_raters = sum(ratings_matrix[0])

    if n_raters < 2 or n_categories < 2:
        return None

    # Calculate P_i (agreement for each item)
    p_i_list = []
    for row in ratings_matrix:
        if sum(row) != n_raters:
            return None
        sum_sq = sum(n_ij * n_ij for n_ij in row)
        p_i = (sum_sq - n_raters) / (n_raters * (n_raters - 1))
        p_i_list.append(p_i)

    p_bar = sum(p_i_list) / n_items

    # Calculate P_j (proportion of all assignments to each category)
    p_j_list = []
    total_assignments = n_items * n_raters
    for j in range(n_categories):
        col_sum = sum(row[j] for row in ratings_matrix)
        p_j_list.append(col_sum / total_assignments)

    p_e = sum(p_j * p_j for p_j in p_j_list)

    if p_e == 1.0:
        return 1.0 if p_bar == 1.0 else None

    kappa = (p_bar - p_e) / (1 - p_e)
    return kappa


def calculate_sarf_kappa_for_pair(matched_pairs: list[tuple], variable_name: str) -> float | None:
    coder_a_values = []
    coder_b_values = []

    for event_a, event_b in matched_pairs:
        val_a = getattr(event_a, variable_name, None)
        val_b = getattr(event_b, variable_name, None)

        # Include if at least one coder assigned a value
        if val_a is not None or val_b is not None:
            coder_a_values.append(str(val_a) if val_a else "none")
            coder_b_values.append(str(val_b) if val_b else "none")

    return calculate_cohens_kappa(coder_a_values, coder_b_values)


def calculate_pairwise_irr(
    extraction_a: PDPDeltas,
    extraction_b: PDPDeltas,
    coder_a_id: str,
    coder_b_id: str,
) -> CoderPairMetrics:
    people_result, id_map = match_people(extraction_a.people, extraction_b.people)
    events_result = match_events(extraction_a.events, extraction_b.events, id_map)
    bonds_result = match_pair_bonds(extraction_a.pair_bonds, extraction_b.pair_bonds, id_map)

    people_tp = len(people_result.matched_pairs)
    people_fp = len(people_result.ai_unmatched)
    people_fn = len(people_result.gt_unmatched)

    events_tp = len(events_result.matched_pairs)
    events_fp = len(events_result.ai_unmatched)
    events_fn = len(events_result.gt_unmatched)

    bonds_tp = len(bonds_result.matched_pairs)
    bonds_fp = len(bonds_result.ai_unmatched)
    bonds_fn = len(bonds_result.gt_unmatched)

    people_f1 = calculate_f1_from_counts(people_tp, people_fp, people_fn).f1
    events_f1 = calculate_f1_from_counts(events_tp, events_fp, events_fn).f1
    bonds_f1 = calculate_f1_from_counts(bonds_tp, bonds_fp, bonds_fn).f1

    total_tp = people_tp + events_tp + bonds_tp
    total_fp = people_fp + events_fp + bonds_fp
    total_fn = people_fn + events_fn + bonds_fn
    aggregate_f1 = calculate_f1_from_counts(total_tp, total_fp, total_fn).f1

    symptom_kappa = calculate_sarf_kappa_for_pair(events_result.matched_pairs, "symptom")
    anxiety_kappa = calculate_sarf_kappa_for_pair(events_result.matched_pairs, "anxiety")
    relationship_kappa = calculate_sarf_kappa_for_pair(events_result.matched_pairs, "relationship")
    functioning_kappa = calculate_sarf_kappa_for_pair(events_result.matched_pairs, "functioning")

    total_unique = total_tp + total_fp + total_fn
    percent_agreement = total_tp / total_unique if total_unique > 0 else 1.0

    return CoderPairMetrics(
        coder_a=coder_a_id,
        coder_b=coder_b_id,
        people_f1=people_f1,
        events_f1=events_f1,
        pair_bonds_f1=bonds_f1,
        aggregate_f1=aggregate_f1,
        symptom_kappa=symptom_kappa,
        anxiety_kappa=anxiety_kappa,
        relationship_kappa=relationship_kappa,
        functioning_kappa=functioning_kappa,
        percent_agreement=percent_agreement,
        matched_event_count=events_tp,
    )


def calculate_statement_irr(statement_id: int) -> StatementIRRMetrics | None:
    """Calculate IRR for a single statement across all coders."""
    from btcopilot.training.models import Feedback

    feedbacks = Feedback.query.filter(
        Feedback.statement_id == statement_id,
        Feedback.feedback_type == "extraction",
        Feedback.edited_extraction.isnot(None),
    ).all()

    if len(feedbacks) < 2:
        return None

    extractions = {fb.auditor_id: from_dict(PDPDeltas, fb.edited_extraction) for fb in feedbacks}

    coder_ids = sorted(extractions.keys())
    coder_pairs = []

    for coder_a, coder_b in combinations(coder_ids, 2):
        pair_metrics = calculate_pairwise_irr(
            extractions[coder_a], extractions[coder_b], coder_a, coder_b
        )
        coder_pairs.append(pair_metrics)

    return StatementIRRMetrics(
        statement_id=statement_id,
        coders=coder_ids,
        coder_pairs=coder_pairs,
        avg_people_f1=safe_avg([cp.people_f1 for cp in coder_pairs]),
        avg_events_f1=safe_avg([cp.events_f1 for cp in coder_pairs]),
        avg_aggregate_f1=safe_avg([cp.aggregate_f1 for cp in coder_pairs]),
        avg_symptom_kappa=safe_avg([cp.symptom_kappa for cp in coder_pairs]),
        avg_anxiety_kappa=safe_avg([cp.anxiety_kappa for cp in coder_pairs]),
        avg_relationship_kappa=safe_avg([cp.relationship_kappa for cp in coder_pairs]),
        avg_functioning_kappa=safe_avg([cp.functioning_kappa for cp in coder_pairs]),
    )


def calculate_discussion_irr(discussion_id: int) -> DiscussionIRRMetrics | None:
    """Calculate IRR aggregated across all statements in a discussion."""
    from btcopilot.personal.models import Statement

    statements = Statement.query.filter_by(discussion_id=discussion_id).all()
    if not statements:
        return None

    statement_metrics = []
    all_coders = set()

    for stmt in statements:
        irr = calculate_statement_irr(stmt.id)
        if irr and irr.coder_pairs:
            statement_metrics.append(irr)
            all_coders.update(irr.coders)

    if not statement_metrics:
        return None

    pair_aggregates: dict[tuple[str, str], list[CoderPairMetrics]] = defaultdict(list)

    for stmt_irr in statement_metrics:
        for cp in stmt_irr.coder_pairs:
            key = tuple(sorted([cp.coder_a, cp.coder_b]))
            pair_aggregates[key].append(cp)

    def avg_pair_metrics(pairs: list[CoderPairMetrics]) -> CoderPairMetrics:
        return CoderPairMetrics(
            coder_a=pairs[0].coder_a,
            coder_b=pairs[0].coder_b,
            people_f1=safe_avg([p.people_f1 for p in pairs]) or 0.0,
            events_f1=safe_avg([p.events_f1 for p in pairs]) or 0.0,
            pair_bonds_f1=safe_avg([p.pair_bonds_f1 for p in pairs]) or 0.0,
            aggregate_f1=safe_avg([p.aggregate_f1 for p in pairs]) or 0.0,
            symptom_kappa=safe_avg([p.symptom_kappa for p in pairs]),
            anxiety_kappa=safe_avg([p.anxiety_kappa for p in pairs]),
            relationship_kappa=safe_avg([p.relationship_kappa for p in pairs]),
            functioning_kappa=safe_avg([p.functioning_kappa for p in pairs]),
            percent_agreement=safe_avg([p.percent_agreement for p in pairs]) or 0.0,
            matched_event_count=sum(p.matched_event_count for p in pairs),
        )

    pairwise = [avg_pair_metrics(pairs) for pairs in pair_aggregates.values()]

    return DiscussionIRRMetrics(
        discussion_id=discussion_id,
        coders=sorted(all_coders),
        statement_count=len(statements),
        coded_statement_count=len(statement_metrics),
        pairwise_metrics=pairwise,
        avg_events_f1=safe_avg([p.events_f1 for p in pairwise]),
        avg_aggregate_f1=safe_avg([p.aggregate_f1 for p in pairwise]),
        avg_symptom_kappa=safe_avg([p.symptom_kappa for p in pairwise]),
        avg_anxiety_kappa=safe_avg([p.anxiety_kappa for p in pairwise]),
        avg_relationship_kappa=safe_avg([p.relationship_kappa for p in pairwise]),
        avg_functioning_kappa=safe_avg([p.functioning_kappa for p in pairwise]),
    )


def get_statement_extractions(statement_id: int) -> dict[str, PDPDeltas]:
    from btcopilot.training.models import Feedback

    feedbacks = Feedback.query.filter(
        Feedback.statement_id == statement_id,
        Feedback.feedback_type == "extraction",
        Feedback.edited_extraction.isnot(None),
    ).all()

    return {fb.auditor_id: from_dict(PDPDeltas, fb.edited_extraction) for fb in feedbacks}


def get_multi_coder_discussions() -> list[tuple[int, int, list[str]]]:
    """
    Find discussions with 2+ coders who have submitted extraction feedback.

    Returns list of (discussion_id, coder_count, coder_ids).
    """
    from sqlalchemy import func, literal_column

    from btcopilot.extensions import db
    from btcopilot.personal.models import Statement
    from btcopilot.training.models import Feedback

    subquery = (
        db.session.query(
            Statement.discussion_id,
            func.count(func.distinct(Feedback.auditor_id)).label("coder_count"),
            func.string_agg(func.distinct(Feedback.auditor_id), literal_column("','")).label(
                "coder_ids"
            ),
        )
        .join(Statement, Feedback.statement_id == Statement.id)
        .filter(Feedback.feedback_type == "extraction")
        .filter(Feedback.edited_extraction.isnot(None))
        .group_by(Statement.discussion_id)
        .having(func.count(func.distinct(Feedback.auditor_id)) >= 2)
        .all()
    )

    return [(row[0], row[1], row[2].split(",") if row[2] else []) for row in subquery]
