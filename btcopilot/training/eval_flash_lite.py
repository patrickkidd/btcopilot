"""
Evaluate gemini-3.1-flash-lite-preview for full-conversation extraction (extract_full).

Runs pdp.extract_full() on discussions 48-53 using gemini-3.1-flash-lite-preview,
then compares the resulting PDP against GT (auditor-approved cumulative PDP)
using the same F1 matching logic as calculate_cumulative_f1().

Usage:
    export $(grep -v '^#' ~/.openclaw/.env | xargs)
    uv run python -m btcopilot.training.eval_flash_lite
    uv run python -m btcopilot.training.eval_flash_lite --model gemini-2.5-flash  # baseline
"""

import argparse
import asyncio
import sys
import time

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.schema import DiagramData, PDP
from btcopilot import pdp
from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    match_pair_bonds,
    calculate_f1_from_counts,
    calculate_sarf_macro_f1,
)

DISCUSSION_IDS = [48, 49, 50, 51, 52, 53]


def eval_extract_full(model: str, discussion_ids: list[int], detailed: bool = False):
    """Run extract_full() with given model on specified discussions, compute F1 vs GT."""
    nest_asyncio.apply()

    import btcopilot.llmutil as llmutil

    original_model = llmutil.EXTRACTION_MODEL
    original_model_large = llmutil.EXTRACTION_MODEL_LARGE

    llmutil.EXTRACTION_MODEL = model
    llmutil.EXTRACTION_MODEL_LARGE = model
    print(f"Model: {model}")
    print(f"Method: pdp.extract_full() (single-prompt full conversation)")
    print(f"Discussions: {discussion_ids}")
    print()

    from btcopilot.personal.models import Discussion, Statement
    from btcopilot.training.models import Feedback

    results = []
    errors = []
    run_start = time.time()

    for disc_id in discussion_ids:
        print(f"Discussion {disc_id}...", end=" ", flush=True)
        disc_start = time.time()

        discussion = Discussion.query.get(disc_id)
        if not discussion:
            print(f"NOT FOUND")
            errors.append((disc_id, "not found"))
            continue

        # Find approved auditor for GT
        approved_fb = (
            Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
            .filter(Statement.discussion_id == disc_id)
            .filter(Feedback.approved == True)
            .filter(Feedback.feedback_type == "extraction")
            .first()
        )
        if not approved_fb:
            print(f"NO GT")
            errors.append((disc_id, "no approved GT"))
            continue

        auditor_id = approved_fb.auditor_id

        try:
            # Run extract_full with empty PDP (fresh extraction)
            diagram_data = DiagramData()
            diagram_data.pdp = PDP()
            ai_pdp, ai_deltas = asyncio.run(
                pdp.extract_full(discussion, diagram_data)
            )

            # Build GT PDP from auditor-approved statements
            last_stmt = max(
                discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
            )
            gt_pdp = pdp.cumulative(discussion, last_stmt, auditor_id=auditor_id)

            # Match and compute F1
            people_result, id_map = match_people(ai_pdp.people, gt_pdp.people)
            events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
            bonds_result = match_pair_bonds(
                ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map
            )

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
            agg_metrics = calculate_f1_from_counts(total_tp, total_fp, total_fn)

            # SARF variables
            sarf_f1s = {}
            if events_result.matched_pairs:
                sarf_f1s = calculate_sarf_macro_f1(events_result.matched_pairs)

            elapsed = time.time() - disc_start

            result = {
                "discussion_id": disc_id,
                "people_f1": people_metrics.f1,
                "events_f1": events_metrics.f1,
                "pair_bonds_f1": bonds_metrics.f1,
                "aggregate_f1": agg_metrics.f1,
                "symptom_f1": sarf_f1s.get("symptom", 0.0),
                "anxiety_f1": sarf_f1s.get("anxiety", 0.0),
                "relationship_f1": sarf_f1s.get("relationship", 0.0),
                "functioning_f1": sarf_f1s.get("functioning", 0.0),
                "ai_people": len(ai_pdp.people),
                "gt_people": len(gt_pdp.people),
                "ai_events": len(ai_pdp.events),
                "gt_events": len(gt_pdp.events),
                "ai_bonds": len(ai_pdp.pair_bonds),
                "gt_bonds": len(gt_pdp.pair_bonds),
                "elapsed": elapsed,
            }
            results.append(result)

            print(
                f"People={people_metrics.f1:.3f} Events={events_metrics.f1:.3f} "
                f"PairBonds={bonds_metrics.f1:.3f} Agg={agg_metrics.f1:.3f} "
                f"({elapsed:.1f}s)"
            )

            if detailed:
                print(f"  AI: {len(ai_pdp.people)}p {len(ai_pdp.events)}e {len(ai_pdp.pair_bonds)}b")
                print(f"  GT: {len(gt_pdp.people)}p {len(gt_pdp.events)}e {len(gt_pdp.pair_bonds)}b")
                print(f"  People: TP={people_metrics.tp} FP={people_metrics.fp} FN={people_metrics.fn}")
                print(f"  Events: TP={events_metrics.tp} FP={events_metrics.fp} FN={events_metrics.fn}")
                print(f"  Bonds:  TP={bonds_metrics.tp} FP={bonds_metrics.fp} FN={bonds_metrics.fn}")
                if sarf_f1s:
                    print(f"  SARF: symptom={sarf_f1s.get('symptom', 0):.3f} "
                          f"anxiety={sarf_f1s.get('anxiety', 0):.3f} "
                          f"relationship={sarf_f1s.get('relationship', 0):.3f} "
                          f"functioning={sarf_f1s.get('functioning', 0):.3f}")
                print()

        except Exception as e:
            elapsed = time.time() - disc_start
            print(f"ERROR ({elapsed:.1f}s): {e}")
            errors.append((disc_id, str(e)))
            continue

    total_elapsed = time.time() - run_start

    # Aggregate across all discussions
    if results:
        n = len(results)
        avg = {
            key: sum(r[key] for r in results) / n
            for key in [
                "people_f1", "events_f1", "pair_bonds_f1", "aggregate_f1",
                "symptom_f1", "anxiety_f1", "relationship_f1", "functioning_f1",
            ]
        }

        print()
        print("=" * 70)
        print(f"EXTRACT_FULL F1 RESULTS — {model}")
        print(f"  {n} discussions, {total_elapsed:.0f}s total")
        print("=" * 70)
        print(f"  People F1:      {avg['people_f1']:.3f}")
        print(f"  Events F1:      {avg['events_f1']:.3f}")
        print(f"  PairBonds F1:   {avg['pair_bonds_f1']:.3f}")
        print(f"  Aggregate F1:   {avg['aggregate_f1']:.3f}")
        print(f"  Symptom F1:     {avg['symptom_f1']:.3f}")
        print(f"  Anxiety F1:     {avg['anxiety_f1']:.3f}")
        print(f"  Relationship F1: {avg['relationship_f1']:.3f}")
        print(f"  Functioning F1:  {avg['functioning_f1']:.3f}")
        print("=" * 70)

        if errors:
            print(f"\nErrors ({len(errors)}):")
            for disc_id, err in errors:
                print(f"  Discussion {disc_id}: {err}")

        return {"model": model, "avg": avg, "results": results, "errors": errors}

    print("No valid results.")
    return None

    # Restore original model (not strictly needed since script exits)
    llmutil.EXTRACTION_MODEL = original_model
    llmutil.EXTRACTION_MODEL_LARGE = original_model_large


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate extract_full() with a specific model"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.1-flash-lite-preview",
        help="Model to test (default: gemini-3.1-flash-lite-preview)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show per-discussion detailed breakdown",
    )
    parser.add_argument(
        "--discussions",
        type=int,
        nargs="+",
        default=DISCUSSION_IDS,
        help="Discussion IDs to evaluate (default: 48 49 50 51 52 53)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = eval_extract_full(
            model=args.model,
            discussion_ids=args.discussions,
            detailed=args.detailed,
        )
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
