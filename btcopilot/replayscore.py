"""A discussion replayed on one model onto a scratch record, scored against a
record Patrick ratified or corrected, never against another model's record,
with the mistakes the watcher looks for counted. Each replay is one row in the
replay passes table and one line in the eval ledger [Oracle: R-0597]."""

import contextlib
import datetime
import hashlib
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func

import btcopilot
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
    ReplayPass,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
)
from btcopilot.models.qualityrun import Source
from btcopilot.models.replaypass import PARTS
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
    case: str | None = None,
    after: ReplayPass | None = None,
) -> dict:
    """The ledger line the replay appended, plus the model calls it made and
    each replayed turn's id beside the id of the turn it replays. Without
    `statements` the whole discussion is replayed; it starts from `start`, or
    an empty record, and is scored against `expected`, or the reference. The
    pass is kept under `case`, the person and the statements replayed. After
    a kept pass, the replay goes on in that pass's scratch session and record,
    and is charged only for its own calls."""
    started = time.monotonic()
    model = model_for(requested, thinking)
    if after is None:
        diagram = adapter.coding_diagram(
            discussion.user,
            f"Replay of session {discussion.id} on {requested}",
            scratch=True,
        )
        if start is not None:
            diagram.data = start
        db.session.commit()
        session = None
    else:
        diagram = db.session.get(Diagram, after.scratch_diagram_id)
        (session,) = diagram.discussions
    before = (
        db.session.query(func.coalesce(func.max(ModelCall.id), 0))
        .filter(ModelCall.diagram_id == diagram.id)
        .scalar()
    )
    if cap is not None:
        cap += adapter.spent(diagram.id)
    if statements is None:
        statements = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id))
    with agent_prompt_from(prompt):
        copy, replies = adapter.replay_into(
            diagram, discussion, statements, model=model, cap=cap, copy=session
        )
    mine = adapter.record_of(diagram)
    scores = compare(
        mine, adapter.record_of(reference) if expected is None else expected
    )
    calls = ModelCall.query.filter(
        ModelCall.diagram_id == diagram.id, ModelCall.id > before
    ).all()
    served = Counter(call.model for call in calls).most_common(1)
    tokens = {
        "input": sum(c.input_tokens for c in calls),
        "output": sum(c.output_tokens for c in calls),
        "cache_creation": sum(c.cache_creation_tokens for c in calls),
        "cache_read": sum(c.cache_read_tokens for c in calls),
    }
    cost = sum((c.cost_usd for c in calls), Decimal(0))
    kept_pass = ReplayPass(
        model=resolve_model(requested),
        thinking=thinking,
        prompt=prompt_version(prompt),
        case=case,
        turns=len(replies),
        calls=len(calls),
        input_tokens=tokens["input"],
        cache_creation_tokens=tokens["cache_creation"],
        cache_read_tokens=tokens["cache_read"],
        output_tokens=tokens["output"],
        cost_usd=cost,
        **{name: scores[name] for name in PARTS},
        overall=ReplayPass.overall_of(scores),
        release=btcopilot.__version__,
        source=Source.Api,
        scratch_diagram_id=diagram.id,
    )
    db.session.add(kept_pass)
    db.session.commit()
    row = {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "kind": ledger.LedgerKind.Replay.value,
        "git": btcopilot.__version__,
        "model": served[0][0] if served else resolve_model(requested),
        "requested": requested,
        "discussion_id": discussion.id,
        "reference_diagram_id": reference.id,
        "scratch_diagram_id": diagram.id,
        "scratch_discussion_id": copy.id,
        "case": kept_pass.key if case else None,
        "outcome": None,
        "turns": len(replies),
        "scores": {name: scores[name] for name in PARTS},
        "faults": faults(diagram.id, mine),
        "tokens": tokens,
        "cost": float(cost),
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
    """The words that started each live coach turn the person took, oldest
    first, leaving out the words of earlier replays. A turn is a run of their
    statements that a coach reply answered; a resent message repeats the run's
    words, and the run's first statement anchors the turn because its changes
    can predate the resend. Older turns carry their turn id on the reply, on
    the first send or nowhere, so none is required."""
    rows = (
        Statement.query.join(Discussion, Statement.discussion_id == Discussion.id)
        .join(Diagram, Discussion.diagram_id == Diagram.id)
        .join(Speaker, Statement.speaker_id == Speaker.id)
        .filter(
            Discussion.user_id == user_id,
            Diagram.scratch.is_(False),
            Statement.kind == StatementKind.Turn,
            Statement.text.isnot(None),
        )
        .order_by(Statement.discussion_id, Statement.order, Statement.id)
        .all()
    )
    starts, run = [], []
    for row in rows:
        if run and row.discussion_id != run[0].discussion_id:
            run = []
        if row.speaker.type == SpeakerType.Subject:
            run.append(row)
        elif run:
            if len({s.text for s in run}) > 1:
                raise ValueError(
                    f"statements {[s.id for s in run]} are one turn with different words"
                )
            starts.append(run[0])
            run = []
    return sorted(starts, key=lambda s: s.id)[:limit]


def anchor(diagram: Diagram, said: Statement | None) -> tuple[bytes, int]:
    """The record and its version as they stood before the turn these words
    started, or as they stand now without words."""
    if said is None:
        return diagram.data, diagram.version
    taken = shadow.rewound(said)
    if not taken:
        return shadow.rebuilt(said), diagram.version
    oldest = taken[-1]
    if oldest.version is None:
        raise ValueError(
            f"diagram_changes row {oldest.id} on diagram {diagram.id} has no version"
        )
    return shadow.rebuilt(said), oldest.version - 1


def prompt_version(path: Path | None) -> str:
    with agent_prompt_from(path):
        return hashlib.sha256(prompts.get_agent_prompt().encode()).hexdigest()[:12]


def kept(case: str, prompt: str, model: str, thinking: str) -> list[ReplayPass]:
    """The passes already kept under this key, oldest first."""
    return (
        ReplayPass.query.filter_by(
            case=case, prompt=prompt, model=model, thinking=thinking
        )
        .order_by(ReplayPass.id)
        .all()
    )


@contextlib.contextmanager
def agent_prompt_from(folder: Path | None):
    """The prompts in `folder`, the coach's agent.prompty or any of its
    fragments/, read in place of the usual ones for the length of the block;
    whatever the folder does not hold is still read from the usual places."""
    if folder is None:
        yield
        return
    usual = prompts.files
    chosen = PromptDir([folder, *usual().dirs])
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
