#!/usr/bin/env python3
"""
F1 evaluation script for full-extraction mode.

Usage:
    GOOGLE_GEMINI_API_KEY=... uv run python run_f1_eval.py
    GOOGLE_GEMINI_API_KEY=... uv run python run_f1_eval.py --discussion 36
    GOOGLE_GEMINI_API_KEY=... uv run python run_f1_eval.py --runs 3
"""
import argparse
import time

import nest_asyncio
nest_asyncio.apply()
import asyncio

from btcopilot.app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--discussion", type=int)
    parser.add_argument("--runs", type=int, default=1, help="Number of runs to average")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from btcopilot import pdp as pdp_mod
        from btcopilot.personal.models import Discussion, Statement
        from btcopilot.training.models import Feedback
        from btcopilot.training.f1_metrics import (
            match_people,
            match_events,
            match_pair_bonds,
            calculate_f1_from_counts,
        )
        from btcopilot.schema import DiagramData

        # Find discussions with approved GT
        query = (
            Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
            .filter(Feedback.approved == True)
            .filter(Feedback.feedback_type == "extraction")
        )
        if args.discussion:
            query = query.filter(Statement.discussion_id == args.discussion)

        disc_ids = sorted(
            set(r[0] for r in query.with_entities(Statement.discussion_id).all())
        )

        if not disc_ids:
            print("No discussions with approved GT found.")
            return

        print(f"Evaluating {len(disc_ids)} discussion(s), {args.runs} run(s) each...\n")

        all_run_results = []

        for run_num in range(args.runs):
            if args.runs > 1:
                print(f"\n--- Run {run_num + 1}/{args.runs} ---")

            run_results = []
            for disc_id in disc_ids:
                discussion = Discussion.query.get(disc_id)
                print(f"  Disc {disc_id} ({discussion.summary})...", end=" ", flush=True)
                start = time.time()

                try:
                    ai_pdp, _ = asyncio.run(
                        pdp_mod.extract_full(discussion, DiagramData())
                    )
                except Exception as e:
                    print(f"FAILED ({time.time()-start:.1f}s): {e}")
                    continue

                # Build GT from approved feedback
                approved_fb = (
                    Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
                    .filter(Statement.discussion_id == disc_id)
                    .filter(Feedback.approved == True)
                    .filter(Feedback.feedback_type == "extraction")
                    .first()
                )
                auditor_id = approved_fb.auditor_id
                last_stmt = max(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))
                gt_pdp = pdp_mod.cumulative(discussion, last_stmt, auditor_id=auditor_id)

                # Score
                people_result, id_map = match_people(ai_pdp.people, gt_pdp.people)
                events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
                bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

                pf = calculate_f1_from_counts(len(people_result.matched_pairs), len(people_result.ai_unmatched), len(people_result.gt_unmatched))
                ef = calculate_f1_from_counts(len(events_result.matched_pairs), len(events_result.ai_unmatched), len(events_result.gt_unmatched))
                bf = calculate_f1_from_counts(len(bonds_result.matched_pairs), len(bonds_result.ai_unmatched), len(bonds_result.gt_unmatched))

                elapsed = time.time() - start
                print(f"P={pf.f1:.3f} E={ef.f1:.3f} B={bf.f1:.3f} ({elapsed:.1f}s) [AI:{len(ai_pdp.events)}e GT:{len(gt_pdp.events)}e]")

                if events_result.ai_unmatched or events_result.gt_unmatched:
                    if events_result.ai_unmatched:
                        print(f"    FP ({len(events_result.ai_unmatched)}):", end="")
                        for e in events_result.ai_unmatched[:5]:
                            print(f" '{e.description}'", end="")
                        if len(events_result.ai_unmatched) > 5:
                            print(f" +{len(events_result.ai_unmatched)-5} more", end="")
                        print()
                    if events_result.gt_unmatched:
                        print(f"    FN ({len(events_result.gt_unmatched)}):", end="")
                        for e in events_result.gt_unmatched[:5]:
                            print(f" '{e.description}'", end="")
                        if len(events_result.gt_unmatched) > 5:
                            print(f" +{len(events_result.gt_unmatched)-5} more", end="")
                        print()

                run_results.append({
                    "disc_id": disc_id,
                    "people_f1": pf.f1,
                    "events_f1": ef.f1,
                    "bonds_f1": bf.f1,
                    "events_tp": ef.tp,
                    "events_fp": ef.fp,
                    "events_fn": ef.fn,
                })

            all_run_results.append(run_results)

        # Summary
        if all_run_results:
            n_runs = len(all_run_results)
            n_discs = len(all_run_results[0]) if all_run_results[0] else 0

            avg_events_f1 = sum(
                r["events_f1"] for run in all_run_results for r in run
            ) / max(1, sum(len(run) for run in all_run_results))

            avg_people_f1 = sum(
                r["people_f1"] for run in all_run_results for r in run
            ) / max(1, sum(len(run) for run in all_run_results))

            avg_bonds_f1 = sum(
                r["bonds_f1"] for run in all_run_results for r in run
            ) / max(1, sum(len(run) for run in all_run_results))

            total_tp = sum(r["events_tp"] for run in all_run_results for r in run)
            total_fp = sum(r["events_fp"] for run in all_run_results for r in run)
            total_fn = sum(r["events_fn"] for run in all_run_results for r in run)

            print(f"\n{'='*60}")
            print(f"SUMMARY ({n_discs} discussions, {n_runs} run(s))")
            print(f"{'='*60}")
            print(f"People F1 (avg):    {avg_people_f1:.3f}")
            print(f"Events F1 (avg):    {avg_events_f1:.3f}  (TP={total_tp} FP={total_fp} FN={total_fn})")
            print(f"PairBonds F1 (avg): {avg_bonds_f1:.3f}")
            target = "PASS" if avg_events_f1 > 0.4 else "FAIL"
            print(f"Events F1 > 0.4:    {target}")
            print(f"{'='*60}")


if __name__ == "__main__":
    main()
