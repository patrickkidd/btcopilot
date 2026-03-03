"""
Experiment: Simplified extraction prompt (strip SARF clinical variables).

Hypothesis: The current extraction prompt asks Gemini to extract people, events
(with 4 SARF variables + relationship targets + triangles per event), and pair
bonds simultaneously. Events F1 is ~0.29. If we remove SARF variables from the
extraction task, the model can focus attention on correctly identifying events,
dates, and person references — potentially boosting Events F1 above 0.4.

Usage:
    # Test on all discussions with approved GT:
    uv run python -m btcopilot.experiments.test_simplified_extraction

    # Test on a specific discussion:
    uv run python -m btcopilot.experiments.test_simplified_extraction --discussion 48

    # Show detailed per-entity breakdowns:
    uv run python -m btcopilot.experiments.test_simplified_extraction --detailed
"""

import argparse
import asyncio
import sys
import time

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.schema import DiagramData, PDP, asdict
from btcopilot.training.f1_metrics import (
    calculate_f1_from_counts,
    match_people,
    match_events,
    match_pair_bonds,
)
from btcopilot import pdp as pdp_module


def _compute_f1_for_pdp(ai_pdp: PDP, gt_pdp: PDP) -> dict:
    """Compute F1 metrics comparing an AI-extracted PDP to ground truth."""
    people_result, id_map = match_people(ai_pdp.people, gt_pdp.people)
    events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
    bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

    people_metrics = calculate_f1_from_counts(
        len(people_result.matched_pairs),
        len(people_result.ai_unmatched),
        len(people_result.gt_unmatched),
    )
    events_metrics = calculate_f1_from_counts(
        len(events_result.matched_pairs),
        len(events_result.ai_unmatched),
        len(events_result.gt_unmatched),
    )
    bonds_metrics = calculate_f1_from_counts(
        len(bonds_result.matched_pairs),
        len(bonds_result.ai_unmatched),
        len(bonds_result.gt_unmatched),
    )

    total_tp = people_metrics.tp + events_metrics.tp + bonds_metrics.tp
    total_fp = people_metrics.fp + events_metrics.fp + bonds_metrics.fp
    total_fn = people_metrics.fn + events_metrics.fn + bonds_metrics.fn
    aggregate = calculate_f1_from_counts(total_tp, total_fp, total_fn)

    return {
        "aggregate_f1": aggregate.f1,
        "people_f1": people_metrics.f1,
        "events_f1": events_metrics.f1,
        "pair_bonds_f1": bonds_metrics.f1,
        "people_counts": {"tp": people_metrics.tp, "fp": people_metrics.fp, "fn": people_metrics.fn},
        "events_counts": {"tp": events_metrics.tp, "fp": events_metrics.fp, "fn": events_metrics.fn},
        "bonds_counts": {"tp": bonds_metrics.tp, "fp": bonds_metrics.fp, "fn": bonds_metrics.fn},
    }


def run_experiment(discussion_id: int | None = None, detailed: bool = False):
    """
    Run simplified vs full extraction experiment.

    For each discussion with approved GT, runs extract_full() twice:
    1. With the full (production) prompt
    2. With the simplified (no-SARF) prompt

    Compares F1 scores side-by-side.
    """
    nest_asyncio.apply()

    from btcopilot.personal.models import Discussion, Statement
    from btcopilot.training.models import Feedback

    # Find discussions with approved GT
    query = (
        Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
        .filter(Feedback.approved == True)
        .filter(Feedback.feedback_type == "extraction")
    )
    if discussion_id:
        query = query.filter(Statement.discussion_id == discussion_id)

    discussion_ids = sorted(set(
        disc_id for (disc_id,) in
        query.with_entities(Statement.discussion_id).distinct().all()
    ))

    if not discussion_ids:
        print("No discussions with approved GT found.")
        return None

    print(f"Running simplified extraction experiment on {len(discussion_ids)} discussion(s)...\n")
    print("=" * 78)

    all_full_results = []
    all_simple_results = []
    errors = []

    for i, disc_id in enumerate(discussion_ids, 1):
        discussion = Discussion.query.get(disc_id)
        if not discussion:
            print(f"[{i}/{len(discussion_ids)}] Discussion {disc_id}: NOT FOUND, skipping")
            continue

        summary = (discussion.summary or "")[:50]
        print(f"\n[{i}/{len(discussion_ids)}] Discussion {disc_id}: {summary}")
        print("-" * 78)

        # Build diagram data
        if discussion.diagram:
            diagram_data = discussion.diagram.get_diagram_data()
        else:
            diagram_data = DiagramData()

        # Clear any existing PDP so extract_full starts fresh
        diagram_data.pdp = PDP()

        # Build GT PDP for comparison
        approved_feedback = (
            Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
            .filter(Statement.discussion_id == disc_id)
            .filter(Feedback.approved == True)
            .filter(Feedback.feedback_type == "extraction")
            .first()
        )
        if not approved_feedback:
            print("  No approved GT, skipping")
            continue

        last_stmt = max(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))
        gt_pdp = pdp_module.cumulative(discussion, last_stmt, auditor_id=approved_feedback.auditor_id)

        # --- Run FULL extraction ---
        try:
            print("  Full prompt...", end=" ", flush=True)
            t0 = time.time()
            full_pdp, _ = asyncio.run(
                pdp_module.extract_full(discussion, diagram_data, simplified=False)
            )
            full_elapsed = time.time() - t0
            full_results = _compute_f1_for_pdp(full_pdp, gt_pdp)
            full_results["elapsed"] = full_elapsed
            all_full_results.append(full_results)
            print(f"done ({full_elapsed:.1f}s)")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(("full", disc_id, str(e)))
            full_results = None

        # --- Run SIMPLIFIED extraction ---
        try:
            print("  Simplified prompt...", end=" ", flush=True)
            t0 = time.time()
            simple_pdp, _ = asyncio.run(
                pdp_module.extract_full(discussion, diagram_data, simplified=True)
            )
            simple_elapsed = time.time() - t0
            simple_results = _compute_f1_for_pdp(simple_pdp, gt_pdp)
            simple_results["elapsed"] = simple_elapsed
            all_simple_results.append(simple_results)
            print(f"done ({simple_elapsed:.1f}s)")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(("simplified", disc_id, str(e)))
            simple_results = None

        # Print comparison for this discussion
        if full_results and simple_results:
            _print_comparison(full_results, simple_results, detailed=detailed)

    # Print aggregate results
    if all_full_results and all_simple_results:
        _print_aggregate(all_full_results, all_simple_results)

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for mode, disc_id, err in errors:
            print(f"  [{mode}] Discussion {disc_id}: {err}")

    return {
        "full": all_full_results,
        "simplified": all_simple_results,
        "errors": errors,
    }


def _print_comparison(full: dict, simple: dict, detailed: bool = False):
    """Print side-by-side comparison of full vs simplified results."""
    def _delta(f, s):
        d = s - f
        return f"+{d:.3f}" if d >= 0 else f"{d:.3f}"

    print(f"\n  {'Metric':<20} {'Full':>8} {'Simple':>8} {'Delta':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")
    print(f"  {'Aggregate F1':<20} {full['aggregate_f1']:>8.3f} {simple['aggregate_f1']:>8.3f} {_delta(full['aggregate_f1'], simple['aggregate_f1']):>8}")
    print(f"  {'People F1':<20} {full['people_f1']:>8.3f} {simple['people_f1']:>8.3f} {_delta(full['people_f1'], simple['people_f1']):>8}")
    print(f"  {'Events F1':<20} {full['events_f1']:>8.3f} {simple['events_f1']:>8.3f} {_delta(full['events_f1'], simple['events_f1']):>8}")
    print(f"  {'PairBonds F1':<20} {full['pair_bonds_f1']:>8.3f} {simple['pair_bonds_f1']:>8.3f} {_delta(full['pair_bonds_f1'], simple['pair_bonds_f1']):>8}")

    if detailed:
        print(f"\n  Counts (TP/FP/FN):")
        for entity in ["people", "events", "bonds"]:
            fc = full[f"{entity}_counts"]
            sc = simple[f"{entity}_counts"]
            print(f"    {entity.title():>10}: Full={fc['tp']}/{fc['fp']}/{fc['fn']}  Simple={sc['tp']}/{sc['fp']}/{sc['fn']}")


def _print_aggregate(full_list: list[dict], simple_list: list[dict]):
    """Print aggregate comparison across all discussions."""
    n = min(len(full_list), len(simple_list))
    if n == 0:
        return

    def _avg(results, key):
        return sum(r[key] for r in results[:n]) / n

    def _delta(f, s):
        d = s - f
        return f"+{d:.3f}" if d >= 0 else f"{d:.3f}"

    print("\n")
    print("=" * 78)
    print(f"AGGREGATE RESULTS ({n} discussions)")
    print("=" * 78)
    print(f"\n  {'Metric':<20} {'Full':>8} {'Simple':>8} {'Delta':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")

    for metric, label in [
        ("aggregate_f1", "Aggregate F1"),
        ("people_f1", "People F1"),
        ("events_f1", "Events F1"),
        ("pair_bonds_f1", "PairBonds F1"),
    ]:
        f_avg = _avg(full_list, metric)
        s_avg = _avg(simple_list, metric)
        print(f"  {label:<20} {f_avg:>8.3f} {s_avg:>8.3f} {_delta(f_avg, s_avg):>8}")

    f_time = sum(r["elapsed"] for r in full_list[:n])
    s_time = sum(r["elapsed"] for r in simple_list[:n])
    print(f"\n  Total time: Full={f_time:.1f}s  Simple={s_time:.1f}s")
    print("=" * 78)

    # Verdict
    f_events = _avg(full_list, "events_f1")
    s_events = _avg(simple_list, "events_f1")
    if s_events > f_events:
        improvement = ((s_events - f_events) / max(f_events, 0.001)) * 100
        print(f"\n  RESULT: Simplified prompt improved Events F1 by {improvement:.1f}%")
        if s_events >= 0.4:
            print(f"  TARGET MET: Events F1 >= 0.4 ({s_events:.3f})")
        else:
            print(f"  TARGET NOT MET: Events F1 = {s_events:.3f} (need >= 0.4)")
    else:
        print(f"\n  RESULT: Simplified prompt did NOT improve Events F1")
        print(f"  Full={f_events:.3f}  Simple={s_events:.3f}")


def main():
    parser = argparse.ArgumentParser(
        description="Experiment: Compare simplified vs full extraction prompts"
    )
    parser.add_argument(
        "--discussion",
        type=int,
        help="Only test this discussion ID (default: all with GT)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show per-entity TP/FP/FN counts",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = run_experiment(
            discussion_id=args.discussion,
            detailed=args.detailed,
        )
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
