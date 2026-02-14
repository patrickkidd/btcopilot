"""
Live prompt testing - re-extracts with current prompts.

Unlike run_prompts.py which uses cached Statement.pdp_deltas, this script
actually calls pdp.update() with the current prompts to get fresh extractions.

Usage:
    uv run python -m btcopilot.training.run_prompts_live
    uv run python -m btcopilot.training.run_prompts_live --detailed
    uv run python -m btcopilot.training.run_prompts_live --model gemini-3-flash-preview
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from dataclasses import asdict

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.schema import DiagramData, PDP
from btcopilot.training.models import Feedback
from btcopilot.training.f1_metrics import calculate_statement_f1
from btcopilot import pdp


def run_prompts_live(detailed=False, discussion_id=None, model=None):
    """
    Compute F1 metrics by re-extracting with current prompts.

    Args:
        detailed: If True, show per-statement breakdown
        discussion_id: If set, only test statements from this discussion
        model: If set, override default extraction models with this model

    Returns:
        dict with overall and per-type F1 scores
    """
    nest_asyncio.apply()

    if model:
        from btcopilot.extensions.llm import LLM

        LLM.extractionModel = model
        LLM.extractionModelLarge = model
        print(f"Using model: {model}\n")

    from btcopilot.personal.models import Statement

    query = Feedback.query.filter_by(approved=True, feedback_type="extraction").join(
        Feedback.statement
    )
    if discussion_id:
        query = query.filter(Statement.discussion_id == discussion_id)
    feedbacks = query.order_by(Feedback.id).all()

    if not feedbacks:
        print("No approved GT cases found.")
        return None

    print(
        f"Testing current prompts on {len(feedbacks)} GT cases (live extraction)...\n"
    )

    all_metrics = []
    error_counts = defaultdict(int)

    for fb in feedbacks:
        stmt = fb.statement
        discussion = stmt.discussion

        if not fb.edited_extraction:
            print(f"⚠ Statement {stmt.id}: Missing GT extraction, skipping")
            error_counts["missing_gt"] += 1
            continue

        try:
            # Build diagram data with cumulative PDP BEFORE this statement
            if discussion.diagram:
                diagram_data = discussion.diagram.get_diagram_data()
            else:
                diagram_data = DiagramData()

            # Build cumulative PDP from statements BEFORE this one (exclusive)
            from btcopilot.personal.models import Statement as StmtModel

            prev_stmt = (
                StmtModel.query.filter_by(discussion_id=stmt.discussion_id)
                .filter(StmtModel.order < stmt.order)
                .order_by(StmtModel.order.desc())
                .first()
            )

            if prev_stmt:
                diagram_data.pdp = pdp.cumulative(discussion, prev_stmt)
            else:
                diagram_data.pdp = PDP()

            # Re-extract with current prompts
            _, fresh_deltas = asyncio.run(
                pdp.update(discussion, diagram_data, stmt.text, stmt.order)
            )

            fresh_extraction = asdict(fresh_deltas) if fresh_deltas else {}

            metrics = calculate_statement_f1(fresh_extraction, fb.edited_extraction)
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
            print(f"✗ Statement {stmt.id}: Error: {e}")
            error_counts["extraction_error"] += 1
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
    print(f"LIVE EXTRACTION RESULTS ({len(all_metrics)} cases)")
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
        description="Test extraction prompts with live re-extraction"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show per-statement F1 breakdown",
    )
    parser.add_argument(
        "--discussion",
        type=int,
        help="Only test statements from this discussion ID",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Override extraction model (e.g. gemini-3-flash-preview)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = run_prompts_live(
            detailed=args.detailed, discussion_id=args.discussion, model=args.model
        )
        sys.exit(0 if result and result["count"] > 0 else 1)


if __name__ == "__main__":
    main()
