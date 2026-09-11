"""The ground truth the harness reads, written out when a cut is ratified.

One file per cut, beside the export the training app already writes and in the
same shape, so the scorer needs no second reader.
"""

import json
from pathlib import Path

from flask import current_app

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Item, ReviewStatus

FILENAME = "gt_review_cut_{cut_id}.json"


def path_for(cut) -> Path:
    folder = Path(current_app.instance_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / FILENAME.format(cut_id=cut.id)


def cases(cut) -> list[dict]:
    discussion = db.session.get(adapter.Discussion, cut.discussion_id)
    case = adapter.case_diagram(discussion)
    record = adapter.record_of(case)
    settled = {
        str(item.item_id)
        for item in Item.query.filter_by(
            cut_id=cut.id, status=ReviewStatus.Settled
        ).all()
        if item.item_id
    }
    statements = adapter.statements_between(
        cut.discussion_id, cut.start_statement_id, cut.end_statement_id
    )
    last = statements[-1] if statements else None
    return [
        {
            "statement_id": last.id if last else None,
            "cut_id": cut.id,
            "statement_text": last.text if last else None,
            "speaker_name": (
                last.speaker.name if last and last.speaker else None
            ),
            "discussion_context": "\n".join(
                f"{s.speaker.name if s.speaker else 'Unknown'}: {s.text}"
                for s in statements
            ),
            "gt_extraction": {
                collection: [
                    entry
                    for entry in record.get(collection) or []
                    if str(entry.get("id")) in settled
                ]
                for collection in ("people", "events", "pair_bonds")
            },
        }
    ]


def write(cut) -> Path:
    path = path_for(cut)
    path.write_text(json.dumps(cases(cut), indent=2, default=str))
    return path
