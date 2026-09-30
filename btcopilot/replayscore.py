"""A discussion replayed on one model onto a scratch record, scored against a
record Patrick ratified or corrected, never against another model's record,
with the mistakes the watcher looks for counted. Each replay is one line in the
eval ledger [Oracle: R-0597]."""

import contextlib
import datetime
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func

from btcopilot import ledger, prompts, shadow
from btcopilot.coachmodel import COACH_EFFORT, model_for
from btcopilot.extensions import db
from btcopilot.llmutil import resolve_model
from btcopilot.matching import parse_date_flexible
from btcopilot.models import (
    Diagram,
    Discussion,
    ModelCall,
    Observation,
    ObservationKind,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
)
from btcopilot.models.qualityrun import Source
from btcopilot.promptdir import PromptDir
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
)
SCORES = ("people", "pair_bonds", "events", "clusters", "variables")


def replay(
    discussion: Discussion,
    requested: str,
    reference: Diagram,
    cap: Decimal | None = None,
    thinking: str = COACH_EFFORT,
    prompt: Path | None = None,
    statements: list[Statement] | None = None,
    start: bytes | None = None,
    expected: dict | None = None,
    key: str | None = None,
) -> dict:
    """The ledger line the replay appended, plus the model calls it made and
    each replayed turn's id beside the id of the turn it replays. Without
    `statements` the whole discussion is replayed; it starts from `start`, or
    an empty record, and is scored against `expected`, or the reference."""
    started = time.monotonic()
    model = model_for(requested, thinking)
    diagram = adapter.coding_diagram(
        discussion.user,
        f"Replay of session {discussion.id} on {requested}",
        scratch=True,
    )
    if start is not None:
        diagram.data = start
    db.session.commit()
    if statements is None:
        statements = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id))
    with agent_prompt_from(prompt):
        copy, replies = adapter.replay_into(
            diagram, discussion, statements, model=model, cap=cap
        )
    mine = adapter.record_of(diagram)
    scores = compare(
        mine, adapter.record_of(reference) if expected is None else expected
    )
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
        "case": key,
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
    return {
        **row,
        "calls": len(calls),
        "pairs": [
            (said.turn_id, reply["turn_id"])
            for said, reply in zip(adapter.spoken(statements), replies)
        ],
    }


def turned(user_id: int, limit: int | None = None) -> list[Statement]:
    """The person's own words that started a live coach turn, oldest first,
    leaving out the words of earlier replays."""
    return (
        Statement.query.join(Discussion, Statement.discussion_id == Discussion.id)
        .join(Diagram, Discussion.diagram_id == Diagram.id)
        .join(Speaker, Statement.speaker_id == Speaker.id)
        .filter(
            Discussion.user_id == user_id,
            Diagram.scratch.is_(False),
            Speaker.type == SpeakerType.Subject,
            Statement.kind == StatementKind.Turn,
            Statement.turn_id.isnot(None),
            Statement.text.isnot(None),
        )
        .order_by(Statement.id)
        .limit(limit)
        .all()
    )


def anchor(diagram: Diagram, said: Statement | None) -> tuple[bytes, int]:
    """The record and its version as they stood before the turn these words
    started, or as they stand now without words."""
    if said is None:
        return diagram.data, diagram.version
    taken = shadow.rewound(said)
    version = taken[-1].version - 1 if taken else diagram.version
    return shadow.rebuilt(said), version


def prompt_version(path: Path | None) -> str:
    with agent_prompt_from(path):
        return hashlib.sha256(prompts.get_agent_prompt().encode()).hexdigest()[:12]


def kept(key: str) -> bool:
    """Whether the ledger already holds a replay under this key."""
    if not ledger.PATH.exists():
        return False
    rows = (json.loads(line) for line in ledger.PATH.read_text().splitlines())
    return any(
        row["kind"] == ledger.LedgerKind.Replay.value and row["case"] == key
        for row in rows
    )


@contextlib.contextmanager
def agent_prompt_from(path: Path | None):
    """The coach's main prompt read from `path` for the length of the block,
    its fragments and every other prompt still read from the usual places."""
    if path is None:
        yield
        return
    usual = prompts.files
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(path, Path(tmp) / "agent.prompty")
        chosen = PromptDir([Path(tmp), *usual().dirs])
        prompts.files = lambda: chosen
        prompts._agent_fixed.cache_clear()
        try:
            yield
        finally:
            prompts.files = usual
            prompts._agent_fixed.cache_clear()


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
