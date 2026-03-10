"""
F1 validation — runs extract_full() and compares against GT.

Unlike run_prompts_live.py which re-extracts per-statement, this script calls
extract_full() once per discussion to get a complete PDP (2-pass split extraction),
then compares against the cumulative GT built from approved Feedback.

Usage:
    uv run python -m btcopilot.training.run_extract_full_f1
    uv run python -m btcopilot.training.run_extract_full_f1 --discussion 50
    uv run python -m btcopilot.training.run_extract_full_f1 --model gemini-2.5-flash
"""

import argparse
import asyncio
import sys
import time

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.schema import DiagramData, PDP
from btcopilot.training.models import Feedback
from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    match_pair_bonds,
    calculate_f1_from_counts,
    calculate_sarf_macro_f1,
)
from btcopilot import pdp


def run_extract_full_f1(discussion_id=None, model=None):
    nest_asyncio.apply()

    if model:
        import btcopilot.llmutil as llmutil

        llmutil.EXTRACTION_MODEL_LARGE = model
        print(f"Using model: {model}\n")

    from btcopilot.personal.models import Discussion, Statement

    # Find discussions with approved GT
    query = (
        Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
        .filter(Feedback.approved == True)
        .filter(Feedback.feedback_type == "extraction")
    )
    if discussion_id:
        query = query.filter(Statement.discussion_id == discussion_id)

    disc_ids = sorted(
        set(r[0] for r in query.with_entities(Statement.discussion_id).all())
    )

    if not disc_ids:
        print("No discussions with approved GT found.")
        return None

    print(f"Validating extraction on {len(disc_ids)} discussion(s)...\n")

    results = []
    run_start = time.time()

    errors = []

    for disc_id in disc_ids:
        discussion = Discussion.query.get(disc_id)
        print(f"Disc {disc_id} ({discussion.summary})...", end=" ", flush=True)
        disc_start = time.time()

        # Build empty DiagramData for fresh extraction
        diagram_data = DiagramData()

        try:
            ai_pdp, _ = asyncio.run(pdp.extract_full(discussion, diagram_data))
        except Exception as e:
            elapsed = time.time() - disc_start
            print(f"EXTRACTION FAILED ({elapsed:.1f}s): {e}")
            errors.append((disc_id, str(e)))
            continue

        # Build GT PDP from approved feedback
        approved_fb = (
            Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
            .filter(Statement.discussion_id == disc_id)
            .filter(Feedback.approved == True)
            .filter(Feedback.feedback_type == "extraction")
            .first()
        )
        auditor_id = approved_fb.auditor_id
        last_stmt = max(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))
        gt_pdp = pdp.cumulative(discussion, last_stmt, auditor_id=auditor_id)

        # Match and score
        people_result, id_map = match_people(
            ai_pdp.people, gt_pdp.people, ai_pdp.pair_bonds, gt_pdp.pair_bonds
        )
        events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
        bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

        people_f1_metrics = calculate_f1_from_counts(
            len(people_result.matched_pairs),
            len(people_result.ai_unmatched),
            len(people_result.gt_unmatched),
        )
        events_f1_metrics = calculate_f1_from_counts(
            len(events_result.matched_pairs),
            len(events_result.ai_unmatched),
            len(events_result.gt_unmatched),
        )
        bonds_f1_metrics = calculate_f1_from_counts(
            len(bonds_result.matched_pairs),
            len(bonds_result.ai_unmatched),
            len(bonds_result.gt_unmatched),
        )

        total_tp = people_f1_metrics.tp + events_f1_metrics.tp + bonds_f1_metrics.tp
        total_fp = people_f1_metrics.fp + events_f1_metrics.fp + bonds_f1_metrics.fp
        total_fn = people_f1_metrics.fn + events_f1_metrics.fn + bonds_f1_metrics.fn
        aggregate = calculate_f1_from_counts(total_tp, total_fp, total_fn)

        sarf = {}
        if events_result.matched_pairs:
            sarf, _ = calculate_sarf_macro_f1(events_result.matched_pairs)

        elapsed = time.time() - disc_start
        result = {
            "discussion_id": disc_id,
            "summary": discussion.summary,
            "people_f1": people_f1_metrics.f1,
            "events_f1": events_f1_metrics.f1,
            "pair_bonds_f1": bonds_f1_metrics.f1,
            "aggregate_f1": aggregate.f1,
            "ai_people": len(ai_pdp.people),
            "gt_people": len(gt_pdp.people),
            "ai_events": len(ai_pdp.events),
            "gt_events": len(gt_pdp.events),
            "ai_bonds": len(ai_pdp.pair_bonds),
            "gt_bonds": len(gt_pdp.pair_bonds),
            "people_tp": people_f1_metrics.tp,
            "people_fp": people_f1_metrics.fp,
            "people_fn": people_f1_metrics.fn,
            "events_tp": events_f1_metrics.tp,
            "events_fp": events_f1_metrics.fp,
            "events_fn": events_f1_metrics.fn,
            "sarf": sarf,
            "elapsed": elapsed,
        }
        results.append(result)

        print(
            f"People={people_f1_metrics.f1:.3f} Events={events_f1_metrics.f1:.3f} "
            f"Bonds={bonds_f1_metrics.f1:.3f} Agg={aggregate.f1:.3f} ({elapsed:.1f}s)"
        )

    # Summary
    if not results:
        print("\nNo discussions could be evaluated.")
        if errors:
            print(f"Errors: {errors}")
        return None

    n = len(results)
    total_elapsed = time.time() - run_start
    avg_people = sum(r["people_f1"] for r in results) / n
    avg_events = sum(r["events_f1"] for r in results) / n
    avg_bonds = sum(r["pair_bonds_f1"] for r in results) / n
    avg_aggregate = sum(r["aggregate_f1"] for r in results) / n

    print()
    print("=" * 60)
    print(f"F1 ({n} discussions, {total_elapsed:.0f}s)")
    print("=" * 60)
    print(f"People F1:      {avg_people:.3f}  (target > 0.7)")
    print(f"Events F1:      {avg_events:.3f}  (target > 0.3)")
    print(f"PairBonds F1:   {avg_bonds:.3f}")
    print(f"Aggregate F1:   {avg_aggregate:.3f}")
    print()

    # Per-discussion detail
    for r in results:
        print(f"  Disc {r['discussion_id']} ({r['summary']}):")
        print(
            f"    People:    F1={r['people_f1']:.3f}  "
            f"(AI:{r['ai_people']} GT:{r['gt_people']} TP:{r['people_tp']} FP:{r['people_fp']} FN:{r['people_fn']})"
        )
        print(
            f"    Events:    F1={r['events_f1']:.3f}  "
            f"(AI:{r['ai_events']} GT:{r['gt_events']} TP:{r['events_tp']} FP:{r['events_fp']} FN:{r['events_fn']})"
        )
        print(f"    PairBonds: F1={r['pair_bonds_f1']:.3f}")
        if r["sarf"]:
            print(
                f"    SARF: S={r['sarf'].get('symptom', 0):.3f} "
                f"A={r['sarf'].get('anxiety', 0):.3f} "
                f"R={r['sarf'].get('relationship', 0):.3f} "
                f"F={r['sarf'].get('functioning', 0):.3f}"
            )
    print("=" * 60)

    # Target check
    people_pass = avg_people > 0.7
    events_pass = avg_events > 0.3
    print(f"\nPeople > 0.7: {'PASS' if people_pass else 'FAIL'} ({avg_people:.3f})")
    print(f"Events > 0.3: {'PASS' if events_pass else 'FAIL'} ({avg_events:.3f})")

    if errors:
        print(f"\nExtraction failures ({len(errors)}):")
        for disc_id, err in errors:
            print(f"  Disc {disc_id}: {err[:100]}")

    return {
        "count": n,
        "people_f1": avg_people,
        "events_f1": avg_events,
        "pair_bonds_f1": avg_bonds,
        "aggregate_f1": avg_aggregate,
        "per_discussion": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate extraction F1 against GT"
    )
    parser.add_argument(
        "--discussion",
        type=int,
        help="Only test this discussion ID",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Override extraction model",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = run_extract_full_f1(
            discussion_id=args.discussion, model=args.model
        )
        sys.exit(0 if result and result["count"] > 0 else 1)


if __name__ == "__main__":
    main()
