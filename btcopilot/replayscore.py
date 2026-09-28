"""A discussion replayed on one model onto a scratch record, scored against a
record Patrick ratified or corrected, never against another model's record,
with the mistakes the watcher looks for counted. Each replay is one line in the
eval ledger [Oracle: R-0590]."""

import datetime
import subprocess
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func

from btcopilot import ledger
from btcopilot.coachmodel import model_for
from btcopilot.extensions import db
from btcopilot.llmutil import resolve_model
from btcopilot.matching import parse_date_flexible
from btcopilot.models import (
    Diagram,
    Discussion,
    ModelCall,
    Observation,
    ObservationKind,
)
from btcopilot.models.qualityrun import Source
from btcopilot.review import adapter
from btcopilot.review.coachscore import compare
from btcopilot.schema import DateCertainty

WATCHED = (
    ObservationKind.ToolRefused,
    ObservationKind.DuplicatePerson,
    ObservationKind.DuplicateEvent,
    ObservationKind.AddWithoutRead,
    ObservationKind.StepCap,
    ObservationKind.QuestionUnsaid,
    ObservationKind.TurnFailed,
)
SCORES = ("people", "pair_bonds", "events", "clusters", "variables")


def replay(
    discussion: Discussion,
    requested: str,
    reference: Diagram,
    cap: Decimal | None = None,
) -> dict:
    """The ledger line the replay appended."""
    started = time.monotonic()
    model = model_for(requested)
    diagram = adapter.coding_diagram(
        discussion.user, f"Replay of session {discussion.id} on {requested}"
    )
    db.session.commit()
    statements = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id))
    copy, replies = adapter.replay_into(
        diagram, discussion, statements, model=model, cap=cap
    )
    mine = adapter.record_of(diagram)
    scores = compare(mine, adapter.record_of(reference))
    calls = ModelCall.query.filter_by(diagram_id=diagram.id).all()
    served = Counter(call.model for call in calls).most_common(1)
    row = {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "kind": ledger.LedgerKind.Replay.value,
        "git": _git(),
        "model": served[0][0] if served else resolve_model(requested),
        "requested": requested,
        "discussion_id": discussion.id,
        "reference_diagram_id": reference.id,
        "scratch_diagram_id": diagram.id,
        "scratch_discussion_id": copy.id,
        "case": None,
        "outcome": None,
        "turns": len(replies),
        "scores": {name: scores[name] for name in SCORES},
        "faults": faults(diagram.id, mine),
        "tokens": {
            "input": sum(c.input_tokens for c in calls),
            "output": sum(c.output_tokens for c in calls),
            "cache_creation": sum(c.cache_creation_tokens for c in calls),
            "cache_read": sum(c.cache_read_tokens for c in calls),
        },
        "cost": float(sum((c.cost_usd for c in calls), Decimal(0))),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "source": Source.Api.value,
    }
    ledger.append(row, ledger.PATH)
    return row


def faults(diagram_id: int, data: dict) -> dict:
    """The watcher's rows on the record, plus two marks of a guessed date on
    its final events: January 1 of any year, and a date of unknown certainty."""
    found = dict(
        db.session.query(Observation.kind, func.count())
        .filter(Observation.diagram_id == diagram_id, Observation.kind.in_(WATCHED))
        .group_by(Observation.kind)
        .all()
    )
    events = adapter.pdp_from(data).events
    days = [parse_date_flexible(e.dateTime) for e in events]
    return {
        **{kind.value: found.get(kind, 0) for kind in WATCHED},
        "jan1_placeholder": sum(
            1 for day in days if day is not None and (day.month, day.day) == (1, 1)
        ),
        "certainty_unknown": sum(
            1 for e in events if e.dateCertainty == DateCertainty.Unknown
        ),
    }


def _git() -> str:
    return subprocess.run(
        ["git", "-C", str(Path(__file__).parent), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
