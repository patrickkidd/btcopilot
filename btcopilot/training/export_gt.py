"""
Export approved ground truth cases for manual prompt optimization with Claude Code.

Usage:
    uv run python -m btcopilot.training.export_gt [output_path]
    uv run python -m btcopilot.training.export_gt instance/gt_export.json
"""

import json
import sys
from pathlib import Path

from btcopilot.app import create_app
from btcopilot.training.models import Feedback


def export_gt_cases(output_path=None):
    """
    Export approved ground truth cases to JSON for Claude Code analysis.

    Args:
        output_path: Path to write JSON file (default: instance/gt_export.json)

    Returns:
        dict with exported case count and output path
    """
    if output_path is None:
        output_path = "instance/gt_export.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    feedbacks = (
        Feedback.query.filter_by(approved=True, feedback_type="extraction")
        .join(Feedback.statement)
        .order_by(Feedback.id)
        .all()
    )

    if not feedbacks:
        print("No approved GT cases found. Code some GT first!")
        return {"count": 0, "path": None}

    cases = []
    for fb in feedbacks:
        stmt = fb.statement
        discussion = stmt.discussion

        full_discussion_text = "\n".join(
            f"{s.speaker.name if s.speaker else 'Unknown'}: {s.text}"
            for s in discussion.statements
        )

        case = {
            "statement_id": stmt.id,
            "feedback_id": fb.id,
            "auditor_id": fb.auditor_id,
            "statement_text": stmt.text,
            "speaker_name": stmt.speaker.name if stmt.speaker else None,
            "discussion_context": full_discussion_text,
            "ai_extraction": stmt.pdp_deltas,
            "gt_extraction": fb.edited_extraction,
            "comment": fb.comment,
        }
        cases.append(case)

    with open(output_path, "w") as f:
        json.dump(cases, f, indent=2)

    print(f"Exported {len(cases)} approved GT cases to {output_path}")
    print(f"\nNext steps:")
    print(f"1. Open Claude Code")
    print(f"2. Paste contents of {output_path}")
    print(
        f"3. Ask Claude to analyze AI vs GT discrepancies and propose prompt improvements"
    )
    print(
        f"4. Test proposed prompts with: uv run python -m btcopilot.training.run_prompts"
    )

    return {"count": len(cases), "path": str(output_path)}


def main():
    app = create_app()
    with app.app_context():
        output_path = sys.argv[1] if len(sys.argv) > 1 else None
        result = export_gt_cases(output_path)
        sys.exit(0 if result["count"] > 0 else 1)


if __name__ == "__main__":
    main()
