"""
Inject definition-enhanced extraction as Feedback records for IRR comparison.

Runs extract_full() (which now uses SARF operational definitions in Pass 3)
on GT discussions and stores results as Feedback records with
auditor_id="ai-definitions". These appear in the discussion coding page
auditor dropdown and IRR comparison views.

Usage:
    uv run python -m btcopilot.training.inject_enhanced_extraction
    uv run python -m btcopilot.training.inject_enhanced_extraction --discussion 50
    uv run python -m btcopilot.training.inject_enhanced_extraction --clear
"""

import argparse
import asyncio
import sys
import time

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.schema import DiagramData, PDPDeltas, asdict

AUDITOR_ID = "ai-definitions"


def inject(discussion_id=None, clear=False):
    nest_asyncio.apply()

    from btcopilot.personal.models import Discussion, Statement, SpeakerType, Speaker
    from btcopilot.training.models import Feedback
    from btcopilot import pdp

    if clear:
        count = Feedback.query.filter(
            Feedback.auditor_id == AUDITOR_ID,
        ).delete()
        db.session.commit()
        print(f"Cleared {count} existing '{AUDITOR_ID}' feedback records.")
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

    print(f"Injecting enhanced extraction on {len(disc_ids)} discussion(s)...\n")

    for disc_id in disc_ids:
        discussion = Discussion.query.get(disc_id)
        print(f"Disc {disc_id} ({discussion.summary})...", end=" ", flush=True)
        start = time.time()

        diagram_data = DiagramData()
        try:
            ai_pdp, ai_deltas = asyncio.run(
                pdp.extract_full(discussion, diagram_data)
            )
        except Exception as e:
            print(f"FAILED ({time.time() - start:.1f}s): {e}")
            continue

        # Find last Subject statement
        last_subject_stmt = (
            Statement.query
            .filter_by(discussion_id=disc_id)
            .join(Speaker)
            .filter(Speaker.type == SpeakerType.Subject)
            .order_by(Statement.order.desc())
            .first()
        )
        if not last_subject_stmt:
            print("SKIP (no Subject statements)")
            continue

        # Clear existing ai-definitions feedback for this discussion
        existing = (
            Feedback.query
            .join(Statement, Feedback.statement_id == Statement.id)
            .filter(Statement.discussion_id == disc_id)
            .filter(Feedback.auditor_id == AUDITOR_ID)
            .all()
        )
        for fb in existing:
            db.session.delete(fb)

        # Store full extraction as PDPDeltas on last Subject statement
        deltas_dict = asdict(PDPDeltas(
            people=ai_pdp.people,
            events=ai_pdp.events,
            pair_bonds=ai_pdp.pair_bonds,
        ))
        feedback = Feedback(
            statement_id=last_subject_stmt.id,
            auditor_id=AUDITOR_ID,
            feedback_type="extraction",
            edited_extraction=deltas_dict,
        )
        db.session.add(feedback)
        db.session.commit()

        elapsed = time.time() - start
        print(
            f"OK ({elapsed:.1f}s) — "
            f"{len(ai_pdp.people)} people, "
            f"{len(ai_pdp.events)} events, "
            f"{len(ai_pdp.pair_bonds)} bonds"
        )

    print("\nDone. View in training app:")
    for disc_id in disc_ids:
        print(f"  /training/discussions/{disc_id}?selected_auditor={AUDITOR_ID}")


def main():
    parser = argparse.ArgumentParser(
        description="Inject definition-enhanced extraction as Feedback for IRR comparison"
    )
    parser.add_argument("--discussion", type=int, help="Only this discussion ID")
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear existing ai-definitions feedback before injecting",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        inject(discussion_id=args.discussion, clear=args.clear)


if __name__ == "__main__":
    main()
