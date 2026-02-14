"""
Test current extraction prompts against approved ground truth.

Computes F1 metrics on all approved GT cases using current prompts in prompts.py.
Use this to measure improvement after updating prompts based on Claude Code analysis.

Usage:
    uv run python -m btcopilot.training.run_prompts
    uv run python -m btcopilot.training.run_prompts --detailed
"""

import argparse
import sys
from collections import defaultdict

from btcopilot.app import create_app
from btcopilot.training.models import Feedback
from btcopilot.training.f1_metrics import calculate_statement_f1


def run_prompts(detailed=False):
    """
    Compute F1 metrics for current prompts on all approved GT.

    Args:
        detailed: If True, show per-statement breakdown

    Returns:
        dict with overall and per-type F1 scores
    """
    feedbacks = (
        Feedback.query.filter_by(approved=True, feedback_type="extraction")
        .join(Feedback.statement)
        .order_by(Feedback.id)
        .all()
    )

    if not feedbacks:
        print(
            "No approved GT cases found. Run export_gt.py first to see available cases."
        )
        return None

    print(f"Testing current prompts on {len(feedbacks)} approved GT cases...\n")

    all_metrics = []
    error_counts = defaultdict(int)

    for fb in feedbacks:
        stmt = fb.statement

        if not stmt.pdp_deltas or not fb.edited_extraction:
            print(f"⚠ Statement {stmt.id}: Missing AI or GT extraction, skipping")
            error_counts["missing_extraction"] += 1
            continue

        try:
            metrics = calculate_statement_f1(stmt.pdp_deltas, fb.edited_extraction)
            metrics.statement_id = stmt.id
            all_metrics.append(metrics)

            if detailed:
                print(f"Statement {stmt.id}:")
                print(f"  Aggregate F1: {metrics.aggregate_micro_f1:.3f}")
                print(f"  People F1:    {metrics.people_f1:.3f}")
                print(f"  Events F1:    {metrics.events_f1:.3f}")
                print(f"  Symptom F1:   {metrics.symptom_macro_f1:.3f}")
                print(f"  Anxiety F1:   {metrics.anxiety_macro_f1:.3f}")
                print(f"  Relationship F1: {metrics.relationship_macro_f1:.3f}")
                print(f"  Functioning F1:  {metrics.functioning_macro_f1:.3f}")
                print()

        except Exception as e:
            print(f"✗ Statement {stmt.id}: Error calculating F1: {e}")
            error_counts["calculation_error"] += 1
            continue

    if not all_metrics:
        print("No valid GT cases could be evaluated.")
        return None

    avg_aggregate_f1 = sum(m.aggregate_micro_f1 for m in all_metrics) / len(all_metrics)
    avg_people_f1 = sum(m.people_f1 for m in all_metrics) / len(all_metrics)
    avg_events_f1 = sum(m.events_f1 for m in all_metrics) / len(all_metrics)
    avg_symptom_f1 = sum(m.symptom_macro_f1 for m in all_metrics) / len(all_metrics)
    avg_anxiety_f1 = sum(m.anxiety_macro_f1 for m in all_metrics) / len(all_metrics)
    avg_relationship_f1 = sum(m.relationship_macro_f1 for m in all_metrics) / len(
        all_metrics
    )
    avg_functioning_f1 = sum(m.functioning_macro_f1 for m in all_metrics) / len(
        all_metrics
    )

    print("=" * 60)
    print(f"OVERALL RESULTS ({len(all_metrics)} cases)")
    print("=" * 60)
    print(f"Aggregate F1:     {avg_aggregate_f1:.3f}")
    print(f"People F1:        {avg_people_f1:.3f}")
    print(f"Events F1:        {avg_events_f1:.3f}")
    print(f"Symptom F1:       {avg_symptom_f1:.3f}")
    print(f"Anxiety F1:       {avg_anxiety_f1:.3f}")
    print(f"Relationship F1:  {avg_relationship_f1:.3f}")
    print(f"Functioning F1:   {avg_functioning_f1:.3f}")
    print("=" * 60)

    if error_counts:
        print(f"\nErrors:")
        for error_type, count in error_counts.items():
            print(f"  {error_type}: {count}")

    print(f"\nTo improve these scores:")
    print(f"1. Export GT: uv run python -m btcopilot.training.export_gt")
    print(f"2. Analyze with Claude Code to propose prompt improvements")
    print(f"3. Update btcopilot/personal/prompts.py")
    print(f"4. Re-run: uv run python -m btcopilot.training.run_prompts")

    return {
        "count": len(all_metrics),
        "aggregate_f1": avg_aggregate_f1,
        "people_f1": avg_people_f1,
        "events_f1": avg_events_f1,
        "symptom_f1": avg_symptom_f1,
        "anxiety_f1": avg_anxiety_f1,
        "relationship_f1": avg_relationship_f1,
        "functioning_f1": avg_functioning_f1,
        "errors": dict(error_counts),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test extraction prompts against approved GT"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show per-statement F1 breakdown",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = run_prompts(detailed=args.detailed)
        sys.exit(0 if result and result["count"] > 0 else 1)


if __name__ == "__main__":
    main()
