"""Run lit-review AI coder extraction and store results as Feedback.

Runs extract_full() with literature-grounded SARF definitions for each
discussion that has approved GT, then stores the cumulative PDP as a
Feedback record on the last statement with auditor_id="litreview-ai".

Usage:
    uv run python -m btcopilot.training.run_litreview_extract
    uv run python -m btcopilot.training.run_litreview_extract --discussion 50
    uv run python -m btcopilot.training.run_litreview_extract --clear
"""

import argparse
import asyncio
import time

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.schema import DiagramData, PDP, asdict
from btcopilot.personal.models import Discussion, Statement, SpeakerType
from btcopilot.training.models import Feedback
from btcopilot.training.litreview import (
    AUDITOR_ID,
    LITREVIEW_PASS2_PROMPT,
    LITREVIEW_SARF_REVIEW_PROMPT,
)
from btcopilot import pdp


def _last_subject_stmt(discussion):
    return (
        Statement.query.filter_by(discussion_id=discussion.id)
        .join(Statement.speaker)
        .filter_by(type=SpeakerType.Subject)
        .order_by(Statement.order.desc())
        .first()
    )


def _clear_existing(discussion_id=None):
    query = Feedback.query.filter_by(auditor_id=AUDITOR_ID, feedback_type="extraction")
    if discussion_id:
        stmt_ids = [
            s.id for s in Statement.query.filter_by(discussion_id=discussion_id).all()
        ]
        query = query.filter(Feedback.statement_id.in_(stmt_ids))
    count = query.delete(synchronize_session=False)
    db.session.commit()
    return count


def run(discussion_id=None, clear=False):
    nest_asyncio.apply()

    if clear:
        count = _clear_existing(discussion_id)
        print(f"Cleared {count} existing litreview-ai feedback records.")
        if not discussion_id:
            return

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
        return

    print(f"Running litreview extraction on {len(disc_ids)} discussion(s)...\n")

    for disc_id in disc_ids:
        discussion = Discussion.query.get(disc_id)
        last_stmt = _last_subject_stmt(discussion)
        if not last_stmt:
            print(f"Disc {disc_id}: no subject statements, skipping")
            continue

        # Clear any existing litreview feedback for this discussion
        _clear_existing(disc_id)

        print(f"Disc {disc_id} ({discussion.summary})...", end=" ", flush=True)
        start = time.time()

        diagram_data = DiagramData()
        try:
            ai_pdp, _ = asyncio.run(
                pdp.extract_full(
                    discussion,
                    diagram_data,
                    pass2_prompt=LITREVIEW_PASS2_PROMPT,
                    sarf_review_prompt=LITREVIEW_SARF_REVIEW_PROMPT,
                )
            )
        except Exception as e:
            elapsed = time.time() - start
            print(f"FAILED ({elapsed:.1f}s): {e}")
            continue

        pdp_dict = asdict(ai_pdp)
        fb = Feedback(
            statement_id=last_stmt.id,
            auditor_id=AUDITOR_ID,
            feedback_type="extraction",
            edited_extraction=pdp_dict,
            meta={"prompt": LITREVIEW_PASS2_PROMPT},
        )
        db.session.add(fb)
        db.session.commit()

        elapsed = time.time() - start
        n_people = len(ai_pdp.people)
        n_events = len(ai_pdp.events)
        print(f"OK ({elapsed:.1f}s) — {n_people} people, {n_events} events")

    print("\nDone. View results in the timeline diff viewer.")


def main():
    parser = argparse.ArgumentParser(description="Run lit-review AI coder extraction")
    parser.add_argument("--discussion", type=int, help="Only run on this discussion ID")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing litreview-ai feedback (and exit unless --discussion is set)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run(discussion_id=args.discussion, clear=args.clear)


if __name__ == "__main__":
    main()
