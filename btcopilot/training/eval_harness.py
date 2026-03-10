"""
Extraction evaluation harness — per-entity-type F1 breakdown.

Provides structured evaluation results with per-entity-type F1 (People, Events,
PairBonds) reported both per-discussion and as aggregate across all GT discussions.

Output formats:
  - Human-readable: formatted table via format_table()
  - Machine-readable: JSON via format_json()

Usage (standalone):
    uv run python -m btcopilot.training.eval_harness
    uv run python -m btcopilot.training.eval_harness --json
    uv run python -m btcopilot.training.eval_harness --ids 50 51 52
"""

import json
import logging
from dataclasses import dataclass, field, asdict

from btcopilot.training.f1_metrics import (
    F1Metrics,
    CumulativeF1Metrics,
    calculate_cumulative_f1,
    calculate_all_cumulative_f1,
)

_log = logging.getLogger(__name__)

# Targets from MVP_DASHBOARD.md
TARGETS = {
    "People": 0.7,
    "Events": 0.3,
}


@dataclass
class EntityTypeBreakdown:
    """F1 metrics for a single entity type."""

    entity_type: str
    f1: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    ai_count: int = 0
    gt_count: int = 0


@dataclass
class DiscussionEvalResult:
    """Per-discussion evaluation with per-entity-type breakdown."""

    discussion_id: int
    summary: str = ""
    auditor_id: str = ""
    aggregate_f1: float = 0.0
    entity_types: list[EntityTypeBreakdown] = field(default_factory=list)


@dataclass
class AggregateBreakdown:
    """Aggregate F1 across all discussions for a single entity type."""

    entity_type: str
    avg_f1: float = 0.0
    total_tp: int = 0
    total_fp: int = 0
    total_fn: int = 0
    micro_f1: float = 0.0
    micro_precision: float = 0.0
    micro_recall: float = 0.0


@dataclass
class EvalResult:
    """Full evaluation result: per-discussion + aggregate breakdowns."""

    discussion_count: int = 0
    per_discussion: list[DiscussionEvalResult] = field(default_factory=list)
    aggregate: list[AggregateBreakdown] = field(default_factory=list)
    aggregate_f1: float = 0.0


def _metrics_to_breakdown(
    entity_type: str, metrics: F1Metrics, ai_count: int = 0, gt_count: int = 0
) -> EntityTypeBreakdown:
    return EntityTypeBreakdown(
        entity_type=entity_type,
        f1=metrics.f1,
        precision=metrics.precision,
        recall=metrics.recall,
        tp=metrics.tp,
        fp=metrics.fp,
        fn=metrics.fn,
        ai_count=ai_count,
        gt_count=gt_count,
    )


def _cumulative_to_discussion_result(m: CumulativeF1Metrics) -> DiscussionEvalResult:
    return DiscussionEvalResult(
        discussion_id=m.discussion_id,
        summary=m.discussion_summary,
        auditor_id=m.auditor_id,
        aggregate_f1=m.aggregate_micro_f1,
        entity_types=[
            _metrics_to_breakdown(
                "People", m.people_metrics, m.ai_people_count, m.gt_people_count
            ),
            _metrics_to_breakdown(
                "Events", m.events_metrics, m.ai_events_count, m.gt_events_count
            ),
            _metrics_to_breakdown(
                "Structural",
                m.structural_events_metrics,
                m.structural_events_metrics.tp + m.structural_events_metrics.fp,
                m.structural_events_metrics.tp + m.structural_events_metrics.fn,
            ),
            _metrics_to_breakdown(
                "Shift",
                m.shift_events_metrics,
                m.shift_events_metrics.tp + m.shift_events_metrics.fp,
                m.shift_events_metrics.tp + m.shift_events_metrics.fn,
            ),
            _metrics_to_breakdown(
                "PairBonds",
                m.pair_bonds_metrics,
                m.pair_bonds_metrics.tp + m.pair_bonds_metrics.fp,
                m.pair_bonds_metrics.tp + m.pair_bonds_metrics.fn,
            ),
        ],
    )


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _calc_micro_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Returns (precision, recall, f1)."""
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return precision, recall, f1


def build_eval_result(cumulative_metrics: list[CumulativeF1Metrics]) -> EvalResult:
    """Build a structured EvalResult from cumulative F1 metrics."""
    per_disc = [_cumulative_to_discussion_result(m) for m in cumulative_metrics]

    n = len(per_disc)
    if n == 0:
        return EvalResult()

    # Build aggregate per entity type
    entity_names = ["People", "Events", "Structural", "Shift", "PairBonds"]
    aggregates = []
    for i, name in enumerate(entity_names):
        total_tp = sum(d.entity_types[i].tp for d in per_disc)
        total_fp = sum(d.entity_types[i].fp for d in per_disc)
        total_fn = sum(d.entity_types[i].fn for d in per_disc)
        avg_f1 = sum(d.entity_types[i].f1 for d in per_disc) / n
        micro_p, micro_r, micro_f1 = _calc_micro_f1(total_tp, total_fp, total_fn)
        aggregates.append(
            AggregateBreakdown(
                entity_type=name,
                avg_f1=avg_f1,
                total_tp=total_tp,
                total_fp=total_fp,
                total_fn=total_fn,
                micro_f1=micro_f1,
                micro_precision=micro_p,
                micro_recall=micro_r,
            )
        )

    all_tp = sum(a.total_tp for a in aggregates)
    all_fp = sum(a.total_fp for a in aggregates)
    all_fn = sum(a.total_fn for a in aggregates)
    _, _, agg_f1 = _calc_micro_f1(all_tp, all_fp, all_fn)

    return EvalResult(
        discussion_count=n,
        per_discussion=per_disc,
        aggregate=aggregates,
        aggregate_f1=agg_f1,
    )


def format_table(result: EvalResult) -> str:
    """Format evaluation result as a human-readable table."""
    if result.discussion_count == 0:
        return "No discussions evaluated."

    lines = []
    lines.append("=" * 80)
    lines.append(
        f"EXTRACTION EVALUATION — Per-Entity-Type F1 ({result.discussion_count} discussions)"
    )
    lines.append(
        f"Targets: People F1 > {TARGETS['People']}, Events F1 > {TARGETS['Events']}"
    )
    lines.append("=" * 80)
    lines.append("")

    # Per-discussion tables
    for d in result.per_discussion:
        lines.append(f"Discussion {d.discussion_id}: {d.summary}")
        lines.append(f"  Auditor: {d.auditor_id}")
        lines.append(
            f"  {'Entity Type':<12} {'F1':>6} {'Prec':>6} {'Rec':>6} "
            f"{'TP':>4} {'FP':>4} {'FN':>4} {'AI#':>4} {'GT#':>4}"
        )
        lines.append(f"  {'-' * 62}")
        for e in d.entity_types:
            lines.append(
                f"  {e.entity_type:<12} {e.f1:>6.3f} {e.precision:>6.3f} {e.recall:>6.3f} "
                f"{e.tp:>4} {e.fp:>4} {e.fn:>4} {e.ai_count:>4} {e.gt_count:>4}"
            )
        lines.append(f"  {'Aggregate':<12} {d.aggregate_f1:>6.3f}")
        lines.append("")

    # Aggregate table
    lines.append("-" * 80)
    lines.append(f"AGGREGATE ({result.discussion_count} discussions)")
    lines.append(
        f"  {'Entity Type':<12} {'Avg F1':>7} {'Micro F1':>9} {'Micro P':>8} "
        f"{'Micro R':>8} {'TP':>5} {'FP':>5} {'FN':>5}"
    )
    lines.append(f"  {'-' * 68}")
    for a in result.aggregate:
        target = ""
        if a.entity_type in TARGETS:
            target_f1 = TARGETS[a.entity_type]
            target = f"  {'PASS' if a.avg_f1 > target_f1 else 'FAIL'} (>{target_f1})"
        lines.append(
            f"  {a.entity_type:<12} {a.avg_f1:>7.3f} {a.micro_f1:>9.3f} {a.micro_precision:>8.3f} "
            f"{a.micro_recall:>8.3f} {a.total_tp:>5} {a.total_fp:>5} {a.total_fn:>5}{target}"
        )
    lines.append(f"  {'Overall':<12} {result.aggregate_f1:>7.3f}")
    lines.append("=" * 80)

    return "\n".join(lines)


def format_json(result: EvalResult) -> dict:
    """Format evaluation result as a machine-readable JSON-serializable dict.

    Schema:
    {
        "discussion_count": int,
        "aggregate_f1": float,
        "aggregate": [
            {
                "entity_type": str,  // "People" | "Events" | "PairBonds"
                "avg_f1": float,
                "micro_f1": float,
                "micro_precision": float,
                "micro_recall": float,
                "total_tp": int,
                "total_fp": int,
                "total_fn": int
            }
        ],
        "per_discussion": [
            {
                "discussion_id": int,
                "summary": str,
                "auditor_id": str,
                "aggregate_f1": float,
                "entity_types": [
                    {
                        "entity_type": str,
                        "f1": float,
                        "precision": float,
                        "recall": float,
                        "tp": int,
                        "fp": int,
                        "fn": int,
                        "ai_count": int,
                        "gt_count": int
                    }
                ]
            }
        ]
    }
    """
    return asdict(result)


def run_eval(discussion_ids: list[int] | None = None) -> EvalResult:
    """Run evaluation on specified discussions (or all with approved GT).

    Must be called within a Flask app context.
    """
    if discussion_ids:
        metrics = []
        for disc_id in discussion_ids:
            try:
                m = calculate_cumulative_f1(disc_id)
                metrics.append(m)
            except ValueError as e:
                _log.warning(f"Could not evaluate discussion {disc_id}: {e}")
                continue
    else:
        system = calculate_all_cumulative_f1(include_synthetic=True)
        metrics = system.per_discussion

    return build_eval_result(metrics)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Extraction evaluation harness — per-entity-type F1 breakdown"
    )
    parser.add_argument(
        "--ids", nargs="+", type=int, help="Discussion IDs to evaluate"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    args = parser.parse_args()

    from btcopilot.app import create_app

    app = create_app()
    with app.app_context():
        result = run_eval(discussion_ids=args.ids)

        if result.discussion_count == 0:
            print("No discussions with approved GT found.")
            sys.exit(1)

        if args.json:
            print(json.dumps(format_json(result), indent=2))
        else:
            print(format_table(result))
            # Also print JSON to stderr for scripting
            print(
                "\n--- JSON output (use --json for clean JSON to stdout) ---",
                file=sys.stderr,
            )
            print(json.dumps(format_json(result), indent=2), file=sys.stderr)

        sys.exit(0)


if __name__ == "__main__":
    main()
