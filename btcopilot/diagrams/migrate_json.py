"""Convert every pickled diagram row to the stored JSON form.

Idempotent: rows already in JSON are counted and skipped. Prints ids and counts
only, never record content.

    python -m btcopilot.diagrams.migrate_json
"""

import logging
import sys

from btcopilot import diagramjson
from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram

_log = logging.getLogger(__name__)

BATCH = 100


def run() -> tuple[int, int, int]:
    ids = [row[0] for row in db.session.query(Diagram.id).order_by(Diagram.id).all()]
    converted = skipped = failed = 0
    for start in range(0, len(ids), BATCH):
        for diagram_id in ids[start : start + BATCH]:
            diagram = db.session.get(Diagram, diagram_id)
            if not diagram.data or diagramjson.is_json(diagram.data):
                skipped += 1
                continue
            try:
                diagram.data = diagramjson.store(diagram.data)
            except (TypeError, ValueError, KeyError, AttributeError):
                failed += 1
                _log.exception(f"Diagram {diagram_id} did not convert")
                db.session.rollback()
                continue
            converted += 1
        db.session.commit()
    return converted, skipped, failed


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    with create_app().app_context():
        converted, skipped, failed = run()
    print(f"converted={converted} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
