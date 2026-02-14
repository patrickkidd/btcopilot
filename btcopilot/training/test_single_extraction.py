#!/usr/bin/env python3
"""
Test extraction for a single statement.

Usage:
    uv run python -m btcopilot.training.test_single_extraction <statement_id>
    uv run python -m btcopilot.training.test_single_extraction 1840
    uv run python -m btcopilot.training.test_single_extraction 1840 --simulate

Modes:
    Default: Shows current Diagram blob state (what app sees NOW after all extractions)
    --simulate: Simulates extraction at statement time using pdp.cumulative()
                (matches what app saw when this statement was originally processed)

This shows the exact inputs and outputs of the extraction pipeline for debugging.
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Test extraction for a single statement"
    )
    parser.add_argument("statement_id", type=int, help="Statement ID to test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full prompt")
    parser.add_argument(
        "--simulate",
        "-s",
        action="store_true",
        help="Simulate extraction at statement time using pdp.cumulative() "
        "instead of current Diagram blob",
    )
    args = parser.parse_args()

    from btcopilot.app import create_app

    app = create_app()
    with app.app_context():
        from btcopilot.personal.models import Statement, Discussion
        from btcopilot.schema import DiagramData, PDP, PDPDeltas, asdict
        from btcopilot.personal.prompts import (
            DATA_EXTRACTION_PROMPT,
            DATA_EXTRACTION_EXAMPLES,
            DATA_EXTRACTION_CONTEXT,
        )
        from btcopilot.llmutil import gemini_structured
        from btcopilot import pdp

        stmt = Statement.query.get(args.statement_id)
        if not stmt:
            print(f"Statement {args.statement_id} not found")
            sys.exit(1)

        discussion = stmt.discussion
        print("=" * 80)
        print(f"STATEMENT {args.statement_id}")
        print("=" * 80)
        print(f"Speaker: {stmt.speaker.name if stmt.speaker else 'Unknown'}")
        print(f"Order: {stmt.order}")
        print(f"Text: {stmt.text}")
        print()

        # Build diagram_data based on mode - ALWAYS use simulate mode now
        # (matching what extract_next_statement does)
        if discussion.diagram:
            diagram_data = discussion.diagram.get_diagram_data()
        else:
            diagram_data = DiagramData()
        diagram_data.pdp = pdp.cumulative(discussion, stmt)
        print(f"Mode: SIMULATE (using pdp.cumulative from prior statement deltas)")

        # Show comparison of both approaches
        cumulative_pdp = pdp.cumulative(discussion, stmt)
        if discussion.diagram:
            blob_data = discussion.diagram.get_diagram_data()
            blob_people = len(blob_data.pdp.people)
            blob_events = len(blob_data.pdp.events)
        else:
            blob_people = 0
            blob_events = 0
        print(
            f"  pdp.cumulative() has: {len(cumulative_pdp.people)} people, {len(cumulative_pdp.events)} events"
        )
        print(f"  Diagram blob has: {blob_people} people, {blob_events} events")

        reference_date = (
            discussion.discussion_date
            if discussion.discussion_date
            else datetime.now().date()
        )

        # Use conversation history up to and including this statement (same as app)
        conversation_history = discussion.conversation_history(stmt.order)

        print("=" * 80)
        print("INPUTS TO EXTRACTION")
        print("=" * 80)
        print(f"Reference date: {reference_date}")
        print()
        print("--- Conversation History ---")
        print(
            conversation_history[:2000]
            if len(conversation_history) > 2000
            else conversation_history
        )
        if len(conversation_history) > 2000:
            print(f"... ({len(conversation_history)} chars total)")
        print()
        print("--- PDP Context (what extraction sees) ---")
        print(f"People: {[p.name for p in diagram_data.pdp.people]}")
        print(f"Events: {len(diagram_data.pdp.events)}")
        print(f"PairBonds: {len(diagram_data.pdp.pair_bonds)}")
        print()

        # Build the full prompt
        full_prompt = (
            DATA_EXTRACTION_PROMPT.format(current_date=reference_date.isoformat())
            + DATA_EXTRACTION_EXAMPLES
            + DATA_EXTRACTION_CONTEXT.format(
                diagram_data=asdict(diagram_data),
                conversation_history=conversation_history,
                user_message=stmt.text,
            )
        )

        if args.verbose:
            print("=" * 80)
            print("FULL PROMPT")
            print("=" * 80)
            print(full_prompt)
            print()

        print("=" * 80)
        print("RUNNING EXTRACTION...")
        print("=" * 80)

        extracted = asyncio.run(gemini_structured(full_prompt, PDPDeltas))

        print()
        print("=" * 80)
        print("EXTRACTION RESULT")
        print("=" * 80)
        print(json.dumps(asdict(extracted), indent=2, default=str))
        print()

        # Compare with stored result
        print("=" * 80)
        print("STORED pdp_deltas (from database)")
        print("=" * 80)
        if stmt.pdp_deltas:
            print(json.dumps(stmt.pdp_deltas, indent=2, default=str))
        else:
            print("(None)")
        print()

        # Check GT if available
        from btcopilot.training.models import Feedback

        feedback = Feedback.query.filter_by(
            statement_id=args.statement_id,
            feedback_type="extraction",
            approved=True,
        ).first()

        if feedback:
            print("=" * 80)
            print("GROUND TRUTH (approved feedback)")
            print("=" * 80)
            print(json.dumps(feedback.edited_extraction, indent=2, default=str))
            print()

            # Show differences
            gt_people = [
                p.get("name") for p in feedback.edited_extraction.get("people", [])
            ]
            ai_people = [p.name for p in extracted.people]

            print("=" * 80)
            print("COMPARISON")
            print("=" * 80)
            print(f"AI extracted people: {ai_people}")
            print(f"GT people: {gt_people}")

            gt_events = len(feedback.edited_extraction.get("events", []))
            ai_events = len(extracted.events)
            print(f"AI extracted events: {ai_events}")
            print(f"GT events: {gt_events}")


if __name__ == "__main__":
    main()
