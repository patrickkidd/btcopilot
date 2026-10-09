"""A real turn run again on each shadow model, for comparison only [R-0596].

The shadow gets the same words, the chat as it stood and a copy of the record
as the real turn found it. It writes onto a scratch record that is thrown away
when it ends; what it said, the tools it called and what it spent are kept on
the real turn's row. The user never sees it and is never charged for it.
"""

import datetime
import logging
import time
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import aliased

from btcopilot import diagramjson, extensions, record
from btcopilot.admin.setting import shadow_candidates
from btcopilot.coachmodel import model_for
from btcopilot.llmutil import MODEL_ALIASES, Spent, gemini_on_bedrock, resolve_model
from btcopilot.pricing import cost, price
from btcopilot.coachturn import RECENT_INTERACTIONS, CoachTurn, prompt_version
from btcopilot.extensions import db
from btcopilot.models import (
    AccessRight,
    Change,
    Diagram,
    Discussion,
    Interaction,
    ModelCall,
    Observation,
    ProductEvent,
    Purpose,
    ShadowTurn,
    Speaker,
    Statement,
    User,
)
from btcopilot.models.preferences import PrefKey
from btcopilot.review.models import Pick
from btcopilot.turnlog import TurnEventKind

_log = logging.getLogger(__name__)

TASK = "coach_shadow"
QUEUE = "shadow"

# What a scratch record leaves behind, all thrown away with it. The model calls
# are not: they move to the real record so the spend stays visible.
SCRATCH_ROWS = (AccessRight, Change, Interaction, Observation, ProductEvent)

# How far back the cost of a coach turn's shadows is averaged, and what they
# are guessed to cost when none ran in that time.
RECENT = datetime.timedelta(days=30)
PER_TURN_GUESS = Decimal("0.19")

# Conversation Feedback turns itself off this long after the latest of the
# coach's last reply being written, the person's last vote and the switch going
# on, so the time spent reading and voting never counts against it [R-0637].
IDLE = datetime.timedelta(minutes=5)


def switch(user: User, models: list, now: datetime.datetime) -> None:
    if unknown := set(models) - set(shadow_candidates()):
        raise ValueError(f"not a shadow model: {', '.join(sorted(unknown))}")
    if not models:
        user.set_prefs(shadow_models=[], shadow_since=None)
    elif user.pref(PrefKey.ShadowModels):
        user.set_prefs(shadow_models=models)
    else:
        user.set_prefs(shadow_models=models, shadow_since=now.isoformat())


def last_reply(user: User, before: int | None = None) -> datetime.datetime | None:
    query = (
        select(func.max(Statement.created_at))
        .join(Discussion, Statement.speaker_id == Discussion.chat_ai_speaker_id)
        .join(Diagram, Discussion.diagram_id == Diagram.id)
        .where(Discussion.user_id == user.id, Diagram.scratch.is_(False))
    )
    if before is not None:
        query = query.where(Statement.id < before)
    return db.session.scalar(query)


def last_vote(user: User) -> datetime.datetime | None:
    return db.session.scalar(
        select(func.max(Pick.updated_at)).where(
            Pick.user_id == user.id, Pick.choice.isnot(None)
        )
    )


def expiry(
    user: User, now: datetime.datetime, before: int | None = None
) -> datetime.datetime | None:
    """When Conversation Feedback turns itself off, None once it is off; past
    that time it is turned off here, and a model no longer a shadow candidate,
    or one the app no longer offers, is dropped. `before` counts only the
    coach's replies written before that statement."""
    # read raw: a model the app has since dropped fails the setting's own check
    stored = list((user.preferences or {}).get(PrefKey.ShadowModels.value) or ())
    kept = [
        alias
        for alias in stored
        if alias in MODEL_ALIASES and alias in shadow_candidates()
    ]
    if kept != stored:
        for alias in stored:
            if alias not in MODEL_ALIASES:
                _log.warning(f"shadow model {alias} is no longer offered; skipped")
        user.set_prefs(shadow_models=kept)
        switch(user, kept, now)
        db.session.commit()
    if not kept:
        return None
    times = [last_reply(user, before), last_vote(user)]
    if since := user.pref(PrefKey.ShadowSince):
        times.append(datetime.datetime.fromisoformat(since))
    started = max(filter(None, times), default=None)
    ends = started + IDLE if started else now
    if ends > now:
        return ends
    switch(user, [], now)
    db.session.commit()
    return None


def start(turn: CoachTurn, statement_id: int, model: str, before: bytes | None):
    """Keep the record as the real turn found it and hand the shadow over."""
    _queue(
        turn.turn_id, turn.discussion, statement_id, model, diagramjson.store(before)
    )


def _queue(
    turn_id: str, discussion: Discussion, statement_id: int, model: str, snapshot: bytes
) -> None:
    if gemini_on_bedrock(resolve_model(model)):
        _log.warning(f"shadow model {model} is Gemini, not on Bedrock; skipped")
        return
    row = ShadowTurn(
        turn_id=turn_id,
        user_id=discussion.user_id,
        diagram_id=discussion.diagram_id,
        discussion_id=discussion.id,
        statement_id=statement_id,
        model=model,
        snapshot=snapshot.decode("utf-8"),
    )
    db.session.add(row)
    db.session.commit()
    enqueue(row.id)


def rewound(said: Statement) -> list[Change]:
    """The changes taken back off today's record to reach the record as it
    stood before the turn these words started: that turn's and every change
    after it, newest first, whoever made them. Row ids give the order; turn
    ids carry none."""
    diagram = said.discussion.diagram
    first = (
        select(func.min(Change.id))
        .where(
            Change.diagram_id == diagram.id,
            or_(Change.turn_id == said.turn_id, Change.created_at >= said.created_at),
        )
        .scalar_subquery()
    )
    return (
        Change.query.filter(Change.diagram_id == diagram.id, Change.id >= first)
        .order_by(Change.id.desc())
        .all()
    )


def rebuilt(said: Statement) -> bytes:
    """The record as it stood before the turn these words started."""
    data = diagramjson.loads(said.discussion.diagram.data)
    for change in rewound(said):
        record.rewind(data, change.deltas)
    kindless = [e["id"] for e in data.get("events") or [] if e.get("kind") is None]
    if kindless:
        raise ValueError(
            f"record {said.discussion.diagram.id} before statement {said.id} holds "
            f"events {kindless} with no kind"
        )
    return diagramjson.dumps(data)


def _mine(user: User):
    return (
        Statement.query.join(Discussion, Statement.discussion_id == Discussion.id)
        .join(Diagram, Discussion.diagram_id == Diagram.id)
        .filter(Discussion.user_id == user.id, Diagram.scratch.is_(False))
    )


def pending(user: User, model: str) -> list[Statement]:
    """The words that started each of this person's past coach turns that
    ended in a reply and have not yet run on this model, oldest first."""
    reply = aliased(Statement)
    return (
        _mine(user)
        .filter(
            Statement.speaker_id == Discussion.chat_user_speaker_id,
            Statement.turn_id.isnot(None),
            exists().where(
                reply.turn_id == Statement.turn_id,
                reply.speaker_id == Discussion.chat_ai_speaker_id,
            ),
            ~exists().where(
                ShadowTurn.turn_id == Statement.turn_id, ShadowTurn.model == model
            ),
        )
        .order_by(Statement.id)
        .all()
    )


def untraced(user: User) -> int:
    """Replies written before replies kept their turn id: no turn to run again."""
    return (
        _mine(user)
        .filter(
            Statement.speaker_id == Discussion.chat_ai_speaker_id,
            Statement.turn_id.is_(None),
        )
        .count()
    )


def estimate(turns: list[Statement], model: str) -> tuple[Decimal, int]:
    """What running these turns on the model would cost, priced from the real
    turns' own token counts, and how many turns have no counts to price."""
    counts = (
        db.session.query(
            func.sum(ModelCall.input_tokens),
            func.sum(ModelCall.output_tokens),
            func.sum(ModelCall.cache_creation_tokens),
            func.sum(ModelCall.cache_read_tokens),
            func.count(func.distinct(ModelCall.turn_id)),
        )
        .filter(
            ModelCall.turn_id.in_([said.turn_id for said in turns]),
            ModelCall.purpose == Purpose.Coach,
        )
        .one()
    )
    fresh, output, written, read, metered = (n or 0 for n in counts)
    name = resolve_model(model)
    # a model with no charge to write its cache reads those tokens as input
    if not price(name).cache_write:
        fresh, written = fresh + written, 0
    spent = Spent(input=fresh, output=output, cache_creation=written, cache_read=read)
    return cost(name, spent), len(turns) - metered


def spend(now: datetime.datetime) -> dict:
    """Across everyone: what all the shadows of one coach turn cost together
    on average over the last 30 days, or a guess when none ran, and what the
    shadows have cost this calendar month."""
    usd, turns = (
        db.session.query(
            func.sum(ShadowTurn.cost_usd), func.count(func.distinct(ShadowTurn.turn_id))
        )
        .filter(ShadowTurn.cost_usd.isnot(None), ShadowTurn.created_at >= now - RECENT)
        .one()
    )
    month = db.session.scalar(
        select(func.sum(ModelCall.cost_usd)).where(
            ModelCall.purpose == Purpose.Shadow,
            ModelCall.created_at
            >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        )
    )
    return {
        "per_turn_usd": round(float(usd / turns if turns else PER_TURN_GUESS), 2),
        "month_usd": round(float(month or 0), 2),
    }


def backfill(user: User, model: str) -> int:
    """Run each of this person's past turns again on the model, over the record
    as it stood before each one. Returns how many were handed over."""
    turns = pending(user, model)
    for said in turns:
        _queue(said.turn_id, said.discussion, said.id, model, rebuilt(said))
    return len(turns)


def enqueue(row_id: int) -> None:
    extensions.celery.send_task(TASK, args=[row_id])


def run(row_id: int) -> None:
    row = ShadowTurn.query.filter_by(id=row_id).one()
    said = db.session.get(Statement, row.statement_id)
    diagram = Diagram(
        user_id=row.user_id,
        name=f"shadow {row_id}",
        data=row.snapshot.encode("utf-8"),
        scratch=True,
    )
    db.session.add(diagram)
    db.session.flush()
    copy = _copy(said, diagram)
    _interactions(row, diagram)
    row.prompt_version = prompt_version()
    db.session.commit()
    shadow_id = f"shadow-{row_id}"
    started = time.monotonic()
    try:
        turn = CoachTurn(
            copy,
            said.spoken,
            purpose=Purpose.Shadow,
            model=model_for(row.model),
            statement_id=said.id,
            turn_id=shadow_id,
            scratch=True,
        )
        row.text = turn.run()["statement"]
        row.tool_calls = [
            {"name": e["name"], "args": e["args"], "refusal": e["refusal"]}
            for e in turn.kept
            if e["type"] == TurnEventKind.ToolCall.value
        ]
        spent = turn.model.spent
        row.input_tokens = spent.input
        row.output_tokens = spent.output
        row.cache_creation_tokens = spent.cache_creation
        row.cache_read_tokens = spent.cache_read
    # Stored on the row so the comparison shows the shadow broke, then raised.
    except Exception as error:
        db.session.rollback()
        row.error = f"{type(error).__name__}: {error}"
        raise
    finally:
        row.duration_ms = round((time.monotonic() - started) * 1000)
        ModelCall.query.filter_by(diagram_id=diagram.id).update(
            {"diagram_id": row.diagram_id}
        )
        row.cost_usd = (
            db.session.query(func.sum(ModelCall.cost_usd))
            .filter_by(turn_id=shadow_id)
            .scalar()
        )
        _drop(diagram, copy)
        row.snapshot = None
        db.session.commit()
        _log.info(f"coach_shadow {row.turn_id} on {row.model}: {row.cost_usd} USD")


def _copy(said: Statement, diagram: Diagram) -> Discussion:
    """A session on the scratch record for the scratch turn's reply, with the
    real one's speakers. The words before it are read from the real family,
    so none are copied. The title is copied so the scratch turn does not name
    the session again."""
    real = said.discussion
    copy = Discussion(
        user_id=real.user_id,
        diagram_id=diagram.id,
        title=real.title,
        title_set_by_user=True,
        kind=real.kind,
        discussion_date=real.discussion_date,
    )
    speakers = {
        s.id: Speaker(name=s.name, type=s.type, person_id=s.person_id)
        for s in real.speakers
    }
    copy.speakers = list(speakers.values())
    db.session.add(copy)
    db.session.flush()
    copy.chat_user_speaker_id = speakers[real.chat_user_speaker_id].id
    copy.chat_ai_speaker_id = speakers[real.chat_ai_speaker_id].id
    db.session.flush()
    db.session.refresh(copy)
    return copy


def _interactions(row: ShadowTurn, diagram: Diagram) -> None:
    """What the user had been looking at when the real turn ran, so the scratch
    turn's prompt carries the same block."""
    for seen in (
        Interaction.query.filter(
            Interaction.diagram_id == row.diagram_id,
            Interaction.created_at <= row.created_at,
        )
        .order_by(Interaction.id.desc())
        .limit(RECENT_INTERACTIONS)
    ):
        db.session.add(
            Interaction(
                diagram_id=diagram.id,
                user_id=seen.user_id,
                session_id=seen.session_id,
                kind=seen.kind,
                item_kind=seen.item_kind,
                item_id=seen.item_id,
                created_at=seen.created_at,
            )
        )


def _drop(diagram: Diagram, copy: Discussion) -> None:
    for rows in SCRATCH_ROWS:
        rows.query.filter_by(diagram_id=diagram.id).delete()
    # the session and its speakers point at each other
    copy.chat_user_speaker_id = None
    copy.chat_ai_speaker_id = None
    db.session.flush()
    db.session.delete(copy)
    db.session.delete(diagram)
