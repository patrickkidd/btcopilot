"""Grouping the record's events into clusters: a clinician's survey, judged
cluster by cluster.

The model is given the record's events, the clusters the person made (fixed),
its own earlier clusters, and the rules' proposal as a hint, and points to the
periods when the family was stirred up, named for what the family was going
through. Most events sit outside any period. The code keeps every cluster it
returns except one spanning more than ten years, one overlapping a cluster the
person made, or one overlapping a kept cluster with more events; a dropped
cluster's events stay dots, and one dropped cluster never costs the others
[Oracle: R-0841]. Spec and ruling ids: doc/CLUSTERS.md.
"""

import datetime
import enum
import json
import logging
from dataclasses import dataclass, field

from btcopilot.extensions import db
from btcopilot.llmutil import (
    PDP_FORCE_REQUIRED,
    PDP_SCHEMA_DESCRIPTIONS,
    UNANSWERED,
    Billed,
    OutputTruncatedError,
    Unreadable,
    dataclass_to_json_schema,
)
from btcopilot.metered import Metered
from btcopilot import record
from btcopilot.models import Author, Change, Observation, ObservationKind, Purpose
from btcopilot import prompts
from btcopilot.models import Diagram
from btcopilot.schema import (
    MIN_CLUSTER_EVENTS,
    Cluster,
    ClusterResult,
    ClusterSource,
    DiagramData,
    Event,
    EventKind,
    ItemKind,
    PairBond,
    asdict,
    from_dict,
    hash_sarf_dicts,
    parse_date,
)

_log = logging.getLogger(__name__)

# Bumped whenever the candidate rules or the naming prompt change, so a record
# grouped by the older rules re-groups on its next event-changing turn. 8: the
# survey prompt, judged cluster by cluster, the fallback gone [Oracle: R-0841,
# R-0843].
DETECTION_VERSION = 8

NODAL_KINDS = frozenset(
    {EventKind.Death, EventKind.Married, EventKind.Divorced, EventKind.Separated}
)
SHIFT_FIELDS = ("symptom", "anxiety", "relationship", "functioning")

# How far either side of a nodal event or shift a related event is proposed as
# part of the same cluster, and the silence that cuts a proposal. Both shape only
# the hint the model is shown, never what it may hand back. The floor of three
# events is the one number that is ruled and enforced (MIN_CLUSTER_EVENTS in
# schema.py), at the model's answer and again at the write.
SPAN_DAYS = 548
CALM_GAP_DAYS = 730
# The grouping answer's token limit, thinking included: room for the thinking
# (its budget is 1024, yet calls on a 91-event record used up to 2454) and, per
# event the record may group, its id in the answer and its share of the names
# and reasons. With no limit, one answer repeated a sentence for 63000 tokens.
THINKING_ROOM = 4096
PER_EVENT = 24
# A returned cluster spanning more than this is the history, not a period, and
# is dropped [Oracle: R-0837, R-0841]. The sources bound the number: the longest
# run any of them draws as one period of stress is five or six years, and
# Bowen's typical stage of the household is ten (Family Therapy in Clinical
# Practice ch. 21 and ch. 3; Basic Series 3). It binds nothing inside the range
# the sources place periods, so the model still judges every edge.
MAX_SPAN_YEARS = 10

# Diagnostic and popular-psychology words the definitions the model is given do
# not contain. The prompt forbids vocabulary from outside those definitions;
# this is the part of that instruction the record can hold it to.
OUTSIDE_WORDS = (
    "toxic",
    "narcissis",
    "gaslight",
    "codepend",
    "dysfunctional",
    "trauma",
    "inner child",
    "love language",
    "red flag",
    "boundaries",
    "enmesh",
    "manipulat",
    "abusive",
    "passive-aggressive",
    "attachment style",
    "emotional labor",
)


class ClusterCheck(enum.StrEnum):
    """Why a cluster was dropped, or why an answer could not be read, so each
    is counted by kind."""

    # the answer as a whole could not be read
    Missing = "missing"
    CutOff = "cut_off"
    Unreadable = "unreadable"
    CallFailed = "call_failed"
    # one returned cluster
    TooSmall = "too_small"
    TooLong = "too_long"
    Overlap = "overlap"
    OutsideWords = "outside_words"


class ClusterError(Exception):
    """The model gave no answer that could be read."""

    def __init__(self, message: str, check: ClusterCheck):
        super().__init__(message)
        self.check = check


def _enum_value(val):
    """Extract enum value or return as-is for non-enum types."""
    return val.value if hasattr(val, "value") else val


def is_nodal_or_shift(event: Event) -> bool:
    """A nodal kind, or any recorded shift."""
    return event.kind in NODAL_KINDS or any(
        getattr(event, name) is not None for name in SHIFT_FIELDS
    )


def _scaffold(event: Event, opens: datetime.date) -> bool:
    """Early births give people ages and generations and are diagnostically
    inert [Oracle: R-0037]; the diagnostic period opens at the first nodal
    event or shift [Oracle: R-0038]."""
    return (
        event.kind.isStructural()
        and not is_nodal_or_shift(event)
        and parse_date(event.dateTime) < opens
    )


def _people(event: Event) -> set[int]:
    ids = {event.person, event.spouse, event.child}
    ids.update(event.relationshipTargets or [])
    ids.update(event.relationshipTriangles or [])
    return {person_id for person_id in ids if person_id is not None}


def _bonds(people: set[int], bonds: list[PairBond]) -> set[int]:
    return {
        bond.id
        for bond in bonds
        if bond.id is not None and (bond.person_a in people or bond.person_b in people)
    }


def _years_after(day: datetime.date, count: int) -> datetime.date:
    try:
        return day.replace(year=day.year + count)
    except ValueError:  # the 29th of February
        return day.replace(year=day.year + count, day=28)


def too_long(dates: list[datetime.date]) -> bool:
    """Whether a cluster's dated events span more than MAX_SPAN_YEARS
    [Oracle: R-0837]."""
    return bool(dates) and max(dates) > _years_after(min(dates), MAX_SPAN_YEARS)


Span = tuple[datetime.date, datetime.date]


def span_of(dates: list[datetime.date]) -> Span | None:
    """The years the timeline draws for a cluster: its first dated event to its
    last; nothing for a cluster with no dated event of its own."""
    return (min(dates), max(dates)) if dates else None


def overlapping(a: Span, b: Span) -> bool:
    """Whether two clusters would share a day on the timeline [Oracle: R-0839].
    Two clusters that only touch on one day do not: the page draws neighbouring
    pills apart at a seam (web/src/picture.ts, `edges`), so touching is the
    one closeness it can still draw as two."""
    return a[0] < b[1] and b[0] < a[1]


def _said(label: str, span: Span) -> str:
    return f"{label} ({span[0].isoformat()} to {span[1].isoformat()})"


def silence(gap: datetime.timedelta) -> str:
    """The span with nothing recorded before a proposed group, in the plain
    words the model is shown: "38 years and 4 months", "7 months", "12 days"."""
    years, rest = divmod(gap.days, 365)
    months = rest // 30
    parts = [
        f"{n} {word}{'' if n == 1 else 's'}"
        for n, word in ((years, "year"), (months, "month"))
        if n
    ]
    return (
        " and ".join(parts)
        if parts
        else f"{gap.days} day{'' if gap.days == 1 else 's'}"
    )


def _dated(data: DiagramData) -> list[Event]:
    events = [
        from_dict(Event, chunk)
        for chunk in data.events
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]
    dated = [e for e in events if parse_date(e.dateTime)]
    return sorted(dated, key=lambda e: (parse_date(e.dateTime), e.id))


def _stored(data: DiagramData) -> list[dict]:
    return [
        cluster
        for cluster in data.clusters
        if isinstance(cluster, dict) and cluster.get("id") is not None
    ]


def _source(cluster: dict) -> ClusterSource | None:
    source = cluster.get("source")
    return ClusterSource(source) if source else None


def _regroupable(cluster: dict) -> bool:
    """Only a grouping the model is known to have made may be regrouped.
    A cluster of unknown provenance is treated as the user's, because the coach
    does not overwrite what the user asked for and the cost is asymmetric:
    guessing wrong about the model loses a name the user chose."""
    return _source(cluster) is ClusterSource.Model


def _held(data: DiagramData) -> set[int]:
    """The events in the clusters the person made, which the model never sees
    as its own to group [Oracle: R-0841]."""
    return {
        event_id
        for cluster in _stored(data)
        if not _regroupable(cluster)
        for event_id in cluster.get("eventIds") or []
    }


def joinable(data: DiagramData) -> list[Event]:
    """Every dated event a cluster may hold: the scaffolding is held out, and so
    are the events of the clusters the person made, which stay theirs."""
    events = _dated(data)
    marked = [e for e in events if is_nodal_or_shift(e)]
    if not marked:
        return []
    opens = parse_date(marked[0].dateTime)
    theirs = _held(data)
    return [e for e in events if not _scaffold(e, opens) and e.id not in theirs]


def _split(ids: list[int], when: dict, marked: set[int]) -> list[list[int]]:
    """Two years with nothing nodal and no shift in them is not one cluster.
    Cut between two such events that far apart, at the widest silence."""
    ordered = [event_id for event_id in ids if event_id in marked]
    cuts = set()
    for first, second in zip(ordered, ordered[1:]):
        if (when[second] - when[first]).days < CALM_GAP_DAYS:
            continue
        between = ids[ids.index(first) : ids.index(second) + 1]
        cuts.add(
            max(
                (
                    ((when[later] - when[earlier]).days, ids.index(later))
                    for earlier, later in zip(between, between[1:])
                ),
            )[1]
        )
    pieces, piece = [], []
    for index, event_id in enumerate(ids):
        if index in cuts:
            pieces.append(piece)
            piece = []
        piece.append(event_id)
    pieces.append(piece)
    return pieces


@dataclass
class Candidate:
    eventIds: list[int]
    nodalOrShiftIds: list[int]
    startDate: str
    endDate: str


def candidates(data: DiagramData) -> list[Candidate]:
    """The runs of events close in time that the record itself suggests, with
    no model in the loop: a hint to the model, never stored as a cluster
    [Oracle: R-0841, R-0843]."""
    free = joinable(data)
    marked = [e for e in free if is_nodal_or_shift(e)]
    if not marked:
        return []

    bonds = [
        from_dict(PairBond, chunk)
        for chunk in data.pair_bonds
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]
    reach = {e.id: (_people(e), _bonds(_people(e), bonds)) for e in free}
    when = {e.id: parse_date(e.dateTime) for e in free}

    groups: list[set[int]] = []
    for seed in marked:
        near = {
            e.id
            for e in free
            if abs((when[e.id] - when[seed.id]).days) <= SPAN_DAYS
            and (
                e.id == seed.id
                or reach[e.id][0] & reach[seed.id][0]
                or reach[e.id][1] & reach[seed.id][1]
            )
        }
        touching = [group for group in groups if group & near]
        for group in touching:
            groups.remove(group)
            near |= group
        groups.append(near)

    marked_ids = {e.id for e in marked}
    kept = [
        Candidate(
            eventIds=ids,
            nodalOrShiftIds=[i for i in ids if i in marked_ids],
            startDate=when[ids[0]].isoformat(),
            endDate=when[ids[-1]].isoformat(),
        )
        for group in groups
        for ids in _split(
            sorted(group, key=lambda event_id: (when[event_id], event_id)),
            when,
            marked_ids,
        )
        if len(ids) >= MIN_CLUSTER_EVENTS
        and any(event_id in marked_ids for event_id in ids)
    ]
    return sorted(kept, key=lambda c: (c.startDate, c.eventIds[0]))


@dataclass
class ModelCluster:
    id: str | None = None
    eventIds: list[int] = field(default_factory=list)
    name: str = ""
    reason: str = ""


@dataclass
class ClusterListResponse:
    clusters: list[ModelCluster] = field(default_factory=list)


def compute_cache_key(events: list[Event]) -> str:
    event_data = [
        {
            "id": e.id,
            "dateTime": e.dateTime,
            "symptom": _enum_value(e.symptom) if e.symptom else None,
            "anxiety": _enum_value(e.anxiety) if e.anxiety else None,
            "relationship": _enum_value(e.relationship) if e.relationship else None,
            "functioning": _enum_value(e.functioning) if e.functioning else None,
        }
        for e in events
    ]
    return hash_sarf_dicts([{"detectionVersion": DETECTION_VERSION}] + event_data)


def _event_json(event: Event) -> dict:
    chunk = {
        "id": event.id,
        "date": event.dateTime,
        "kind": _enum_value(event.kind),
        "description": event.description or "",
        "people": sorted(_people(event)),
    }
    for name in SHIFT_FIELDS:
        value = getattr(event, name)
        if value is not None:
            chunk[name] = _enum_value(value)
    if event.notes:
        chunk["notes"] = event.notes
    return chunk


def _before(candidate: Candidate, when: dict[int, datetime.date]) -> str:
    """One plain line on the silence before a proposed group, so the model
    reads the gap instead of inferring it from two date strings: Kerr weighs
    "the time spacing between events" (Family Evaluation, line 3355)."""
    first = parse_date(candidate.startDate)
    earlier = [day for day in when.values() if day < first]
    if not earlier:
        return "first group in the record"
    return f"{silence(first - max(earlier))} with nothing recorded before this group"


def _title(cluster: dict) -> str:
    return cluster.get("name") or cluster.get("title") or ""


def _prompt(
    cands: list[Candidate],
    free: list[Event],
    stored: dict[str, dict],
    fixed: list[tuple[str, Span]],
) -> str:
    by_id = {e.id: e for e in free}
    when = {e.id: parse_date(e.dateTime) for e in free}
    blocks = [
        {
            "candidate": n + 1,
            "before": _before(candidate, when),
            "nodalOrShiftIds": candidate.nodalOrShiftIds,
            "events": [_event_json(by_id[i]) for i in candidate.eventIds],
        }
        for n, candidate in enumerate(cands)
    ]
    grouped = {i for candidate in cands for i in candidate.eventIds}
    return prompts.CLUSTER_PROMPT.format(
        existing=json.dumps(
            [
                {
                    "id": cluster_id,
                    "name": _title(cluster),
                    "reason": cluster.get("reason") or cluster.get("summary") or "",
                    "eventIds": cluster.get("eventIds") or [],
                }
                for cluster_id, cluster in stored.items()
            ],
            indent=2,
        ),
        theirs=json.dumps(
            [
                {"name": name, "from": span[0].isoformat(), "to": span[1].isoformat()}
                for name, span in fixed
            ],
            indent=2,
        ),
        candidates=json.dumps(blocks, indent=2),
        unclustered=json.dumps(
            [_event_json(e) for e in free if e.id not in grouped], indent=2
        ),
    )


def _dates(
    cluster: dict, when: dict[int, datetime.date], held: set[int] = frozenset()
) -> list[datetime.date]:
    return [
        when[i] for i in cluster.get("eventIds") or [] if i in when and i not in held
    ]


def _theirs(data: DiagramData) -> tuple[set[int], list[tuple[str, Span]]]:
    """The events in the clusters the person made, and each such cluster's name
    and years as the timeline draws them. Such a cluster's own dates stand in
    where its events are not dated in the record."""
    when = {e.id: parse_date(e.dateTime) for e in _dated(data)}
    events: set[int] = set()
    spans: list[tuple[str, Span]] = []
    for cluster in _stored(data):
        if _regroupable(cluster):
            continue
        events.update(cluster.get("eventIds") or [])
        span = span_of(_dates(cluster, when))
        if span is None and cluster.get("startDate") and cluster.get("endDate"):
            span = (parse_date(cluster["startDate"]), parse_date(cluster["endDate"]))
        if span:
            spans.append((_title(cluster), span))
    return events, spans


@dataclass
class Dropped:
    """A returned cluster the code did not keep, with the model's whole answer
    for it, so what it chose and what it overlapped can be read later."""

    check: ClusterCheck
    why: str
    name: str
    start: str | None
    end: str | None
    eventIds: list[int]


def _dropped(
    check: ClusterCheck, why: str, cluster: ModelCluster, span: Span | None
) -> Dropped:
    return Dropped(
        check=check,
        why=why,
        name=cluster.name,
        start=span[0].isoformat() if span else None,
        end=span[1].isoformat() if span else None,
        eventIds=list(cluster.eventIds),
    )


def _merged(
    answer: ClusterListResponse, known: set[int], stored: dict[str, dict]
) -> list[ModelCluster]:
    """The answer's clusters with events the record does not hold stripped, an
    id the record does not hold dropped, and a cluster returned twice (the same
    id, or the same events) merged into one; the first name stands."""
    out: list[ModelCluster] = []
    for cluster in answer.clusters:
        ids = [i for i in dict.fromkeys(cluster.eventIds) if i in known]
        if len(ids) < len(cluster.eventIds):
            _log.info(
                f"Cluster {cluster.name!r} named events the record does not hold: "
                f"{[i for i in cluster.eventIds if i not in known]}"
            )
        cid = cluster.id if cluster.id in stored else None
        twin = next(
            (c for c in out if (cid and c.id == cid) or set(c.eventIds) == set(ids)),
            None,
        )
        if twin is not None:
            twin.eventIds = list(dict.fromkeys(twin.eventIds + ids))
            twin.id = twin.id or cid
            continue
        out.append(
            ModelCluster(id=cid, eventIds=ids, name=cluster.name, reason=cluster.reason)
        )
    return out


def judge(
    answer: ClusterListResponse,
    free: list[Event],
    fixed: list[tuple[str, Span]],
    stored: dict[str, dict],
) -> tuple[list[ModelCluster], list[Dropped]]:
    """Every returned cluster kept, except one spanning more than ten years, one
    overlapping a cluster the person made, or one overlapping a kept cluster
    with more events; judged one by one, largest first, so one dropped cluster
    never costs the others [Oracle: R-0841]. A cluster left with fewer than
    three events of its own, or named in words outside the given terms, is
    dropped too [Oracle: R-0215, R-0195]. An event already in a kept cluster
    is not in a second one."""
    known = {e.id for e in free}
    when = {e.id: parse_date(e.dateTime) for e in free}
    kept: list[ModelCluster] = []
    held: list[tuple[str, Span]] = []
    placed: set[int] = set()
    dropped: list[Dropped] = []
    ordered = sorted(
        _merged(answer, known, stored),
        key=lambda c: (
            -len(c.eventIds),
            min((when[i] for i in c.eventIds), default=datetime.date.max),
        ),
    )
    for cluster in ordered:
        cluster.eventIds = [i for i in cluster.eventIds if i not in placed]
        dates = [when[i] for i in cluster.eventIds]
        span = span_of(dates)
        label = f"the cluster {cluster.name!r}"
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            dropped.append(
                _dropped(
                    ClusterCheck.TooSmall,
                    f"{label} holds fewer than {MIN_CLUSTER_EVENTS} events of its own",
                    cluster,
                    span,
                )
            )
            continue
        if too_long(dates):
            dropped.append(
                _dropped(
                    ClusterCheck.TooLong,
                    f"{_said(label, span)} spans more than {MAX_SPAN_YEARS} years: "
                    "the history, not a period",
                    cluster,
                    span,
                )
            )
            continue
        over = next((f for f in fixed if overlapping(span, f[1])), None)
        if over:
            dropped.append(
                _dropped(
                    ClusterCheck.Overlap,
                    f"{_said(label, span)} shares years with the cluster this person "
                    f"made, {_said(repr(over[0]), over[1])}: the person's reading wins",
                    cluster,
                    span,
                )
            )
            continue
        over = next((h for h in held if overlapping(span, h[1])), None)
        if over:
            dropped.append(
                _dropped(
                    ClusterCheck.Overlap,
                    f"{_said(label, span)} shares years with {_said(over[0], over[1])}, "
                    "which holds more events: one line, so the larger stays",
                    cluster,
                    span,
                )
            )
            continue
        spoken = f"{cluster.name} {cluster.reason}".lower()
        outside = [word for word in OUTSIDE_WORDS if word in spoken]
        if outside:
            dropped.append(
                _dropped(
                    ClusterCheck.OutsideWords,
                    f"{label} uses {outside}, which the given terms do not contain",
                    cluster,
                    span,
                )
            )
            continue
        kept.append(cluster)
        held.append((label, span))
        placed.update(cluster.eventIds)
    # judged largest first, stored in the order of the line
    kept.sort(key=lambda c: (min(when[i] for i in c.eventIds), c.eventIds[0]))
    return kept, dropped


def _holds(
    cluster: dict,
    when: dict[int, datetime.date],
    held: set[int],
    around: list[tuple[str, Span]],
) -> ClusterCheck | None:
    """Which judgement a stored cluster fails, or nothing."""
    dates = _dates(cluster, when, held)
    if too_long(dates):
        return ClusterCheck.TooLong
    span = span_of(dates)
    if span and any(overlapping(span, other) for _, other in around):
        return ClusterCheck.Overlap
    return None


def _judged(
    data: DiagramData,
) -> tuple[dict[str, dict], list[tuple[dict, ClusterCheck, str]]]:
    """The stored model clusters that pass the judgements, by id, and each one
    that fails with a sentence naming its years and the check it fails."""
    when = {e.id: parse_date(e.dateTime) for e in _dated(data)}
    held, fixed = _theirs(data)
    model = [c for c in _stored(data) if _regroupable(c)]
    around = {
        str(c["id"]): (f"the cluster {_title(c)!r}", span_of(_dates(c, when, held)))
        for c in model
    }
    kept, failing = {}, []
    for cluster in model:
        others = fixed + [
            said
            for cid, said in around.items()
            if cid != str(cluster["id"]) and said[1]
        ]
        check = _holds(cluster, when, held, others)
        if check is None:
            kept[str(cluster["id"])] = cluster
            continue
        span = span_of(_dates(cluster, when, held))
        name = _said(_title(cluster), span) if span else repr(_title(cluster))
        why = (
            f"the {MAX_SPAN_YEARS}-year check"
            if check is ClusterCheck.TooLong
            else "the overlap check"
        )
        failing.append(
            (cluster, check, f"Stored cluster {cluster['id']} {name} fails {why}")
        )
    return kept, failing


def mine(data: DiagramData) -> dict[str, dict]:
    """The stored clusters the model made and is shown as its own earlier
    reading. One that fails a judgement is left out and dropped: keeping what
    is there protects a reading, not a category error [Oracle: R-0838, R-0839,
    R-0840]. Two model clusters overlapping each other both fail: neither has a
    better claim to the years."""
    kept, failing = _judged(data)
    for _, _, why in failing:
        _log.info(f"{why} and is not handed back")
    return kept


def broken(data: DiagramData) -> list[tuple[dict, ClusterCheck, str]]:
    """The stored model clusters that fail a judgement, each with the check and
    a sentence naming its years and the check."""
    return _judged(data)[1]


def answer_schema(stored: dict[str, dict]) -> dict:
    """The answer's shape, with `id` limited to the clusters the record holds
    and left out when it holds none, and every cluster's events, name and
    reason required. Offered a free-text id, the grouping model wrote one for
    every new cluster; with nothing required, it once left out every cluster's
    events."""
    schema = dataclass_to_json_schema(
        ClusterListResponse, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )
    group = schema["properties"]["clusters"]["items"]
    group["required"] = ["eventIds", "name", "reason"]
    fields = group["properties"]
    if stored:
        fields["id"]["enum"] = sorted(stored)
    else:
        del fields["id"]
    return schema


def _answered(ask, prompt: str, schema: dict, limit: int) -> ClusterListResponse:
    """One answer, or the reason none could be read: cut off at its limit,
    not the JSON asked for, never given, or empty."""
    try:
        answer = ask(prompt, schema, limit)
    except OutputTruncatedError as cut:
        raise ClusterError(
            "The answer ran past its length limit.", ClusterCheck.CutOff
        ) from cut
    except Unreadable as garbled:
        raise ClusterError(
            "The answer was not the JSON asked for.", ClusterCheck.Unreadable
        ) from garbled
    except (Billed, *UNANSWERED) as failed:
        raise ClusterError(
            f"The grouping call failed: {type(failed).__name__}",
            ClusterCheck.CallFailed,
        ) from failed
    if answer is None or not answer.clusters:
        raise ClusterError("No clusters came back.", ClusterCheck.Missing)
    return answer


def detect_clusters(data: DiagramData, ask, dropped=None, unread=None) -> ClusterResult:
    """`ask` takes the prompt, the answer's schema and its token limit and
    returns the model's ClusterListResponse; `dropped`, when given, hears each
    returned cluster the judgement did not keep, and `unread` each answer that
    could not be read, with its attempt number. One call per regroup; a second
    only when the first answer cannot be read at all, and when that one cannot
    be either, a ClusterError says so and nothing changes [Oracle: R-0841]."""
    cache_key = compute_cache_key(_dated(data))
    cands = candidates(data)
    if not cands:
        return ClusterResult(clusters=[], cacheKey=cache_key)

    free = joinable(data)
    taken = {str(cluster["id"]) for cluster in _stored(data)}
    existing = mine(data)
    _, fixed = _theirs(data)
    prompt = _prompt(cands, free, existing, fixed)
    schema = answer_schema(existing)
    limit = THINKING_ROOM + PER_EVENT * len(free)
    _log.info(
        f"Grouping {len(free)} events: {len(existing)} clusters already there, "
        f"{len(fixed)} the person's own, {len(cands)} proposed"
    )
    try:
        answer = _answered(ask, prompt, schema, limit)
    except ClusterError as first:
        _log.warning(f"Grouping answer could not be read, asking once more: {first}")
        if unread:
            unread(1, first)
        try:
            answer = _answered(ask, prompt, schema, limit)
        except ClusterError as second:
            if unread:
                unread(2, second)
            raise

    kept, left = judge(answer, free, fixed, existing)
    for one in left:
        _log.warning(
            f"Cluster dropped ({one.check.value}): {one.why}; the model's answer "
            f"was {one.name!r} {one.start} to {one.end} {one.eventIds}"
        )
        if dropped:
            dropped(one)

    when = {e.id: e.dateTime for e in free}
    clusters = []
    for cluster in kept:
        spanned = sorted(when[event_id] for event_id in cluster.eventIds)
        cluster_id = cluster.id or next_id(taken)
        taken.add(cluster_id)
        clusters.append(
            Cluster(
                id=cluster_id,
                title=cluster.name,
                name=cluster.name,
                summary=cluster.reason,
                reason=cluster.reason,
                eventIds=list(cluster.eventIds),
                startDate=spanned[0],
                endDate=spanned[-1],
                source=ClusterSource.Model,
            )
        )
    return ClusterResult(clusters=clusters, cacheKey=cache_key)


STORED_FIELDS = (
    "title",
    "name",
    "summary",
    "reason",
    "eventIds",
    "startDate",
    "endDate",
    "source",
)


def next_id(taken: set[str]) -> str:
    return record.next_key("c", taken)


def _detected(stored: list[dict], detected: list[Cluster], dates: dict) -> dict:
    """The model's clusters, with every event a cluster it may not touch owns
    held out. Each cluster already carries its own id, the model's own statement
    of which stored cluster it is, so what the coach said about it last turn
    still points at something the record holds. A cluster that arrives under
    the minimum is a bug in whatever produced it and raises; one that only falls
    under it once the held-out events are taken out stays dots on the line."""
    theirs = {
        event_id
        for c in stored
        if not _regroupable(c)
        for event_id in c.get("eventIds") or []
    }
    others = {str(c["id"]) for c in stored if not _regroupable(c)}
    taken = {str(c["id"]) for c in stored}
    kept: dict[str, Cluster] = {}
    for cluster in detected:
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Cluster {cluster.eventIds} arrived holding fewer than "
                f"{MIN_CLUSTER_EVENTS} events.",
                ClusterCheck.TooSmall,
            )
        event_ids = [e for e in cluster.eventIds if e in dates and e not in theirs]
        if len(event_ids) < MIN_CLUSTER_EVENTS:
            continue
        cluster.eventIds = event_ids
        cluster.source = ClusterSource.Model
        cluster.name = cluster.name or cluster.title
        spanned = sorted(dates[e] for e in event_ids)
        cluster.startDate, cluster.endDate = spanned[0], spanned[-1]
        cluster.id = str(cluster.id) if cluster.id else next_id(taken | set(kept))
        if cluster.id in others:
            raise ClusterError(
                f"Cluster {cluster.id} is not one the model may write over.",
                ClusterCheck.Missing,
            )
        kept[cluster.id] = cluster
    return kept


def _deltas(stored: list[dict], detected: list[Cluster], dates: dict) -> list[dict]:
    stored = [c for c in stored if isinstance(c, dict) and c.get("id") is not None]
    held = {str(c["id"]): c for c in stored if _regroupable(c)}
    kept = _detected(stored, detected, dates)

    deltas = [
        {
            "item_kind": ItemKind.Cluster.value,
            "item_id": cluster_id,
            "field": None,
            "after": None,
        }
        for cluster_id in held
        if cluster_id not in kept
    ]
    for cluster_id, cluster in kept.items():
        was = held.get(cluster_id, {})
        now = asdict(cluster)
        deltas += [
            {
                "item_kind": ItemKind.Cluster.value,
                "item_id": cluster_id,
                "field": field_name,
                "after": now[field_name],
            }
            for field_name in STORED_FIELDS
            if now[field_name] != was.get(field_name)
        ]
    return deltas


@dataclass
class Regroup:
    """What one recompute did: the record change it wrote, and one sentence per
    cluster it reshaped, in story rather than in the language of grouping; the
    survey names freely and says nothing of changes, so the list is empty."""

    change: Change
    sentences: list[str]


def _events(data: DiagramData) -> list[Event]:
    return [
        from_dict(Event, chunk)
        for chunk in data.events
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]


def behind(data: DiagramData) -> bool:
    """Whether the record's events changed since its last grouping."""
    return compute_cache_key(_events(data)) != data.clusterCacheKey


def sync(
    diagram_id: int,
    *,
    turn_id: str,
    user_id: int,
    session_id: int | None = None,
    metered: Metered | None = None,
    force: bool = False,
) -> Regroup | None:
    """Re-group the record's events and store the grouping. `force` regroups a
    record whose events are as they were at its last grouping.

    Clusters are stored, not derived on read, so the coach can point at one and
    have it still be there next turn. The model surveys the record and names
    its periods; the code keeps each returned cluster that passes the three
    judgements and drops the rest, each drop a warning and an observations
    row carrying the model's answer for it. It never invents a member, and it
    never touches a cluster the person made: those events are held out of
    what the model sees and of what it may store.
    """
    diagram = db.session.get(Diagram, diagram_id)
    data = diagram.get_diagram_data()
    events = _events(data)
    cache_key = compute_cache_key(events)
    if not force and cache_key == data.clusterCacheKey:
        return None

    dates = {e.id: e.dateTime for e in events if e.dateTime}
    metered = metered or Metered(user_id, diagram_id, turn_id, Purpose.Cluster)

    def observe(kind: ObservationKind, detail: dict) -> None:
        db.session.add(
            Observation(
                diagram_id=diagram_id, turn_id=turn_id, kind=kind, detail=detail
            )
        )

    def dropped(one: Dropped) -> None:
        # Each dropped cluster is counted by kind, with the model's whole answer
        # for it, so what it chose and what it overlapped can be read later
        # [Oracle: R-0780, R-0841].
        observe(
            ObservationKind.ClusterRefused,
            {
                "attempt": 1,
                "check": one.check.value,
                "detail": one.why,
                "reason": one.check.value,
                "name": one.name,
                "start": one.start,
                "end": one.end,
                "eventIds": one.eventIds,
                "groups": 1,
                "events": len(one.eventIds),
            },
        )

    def unread(attempt: int, error: ClusterError) -> None:
        # An answer that could not be read is counted too [Oracle: R-0780].
        observe(
            ObservationKind.ClusterRefused,
            {
                "attempt": attempt,
                "check": error.check.value,
                "detail": str(error),
                "reason": error.check.value,
                "groups": 0,
                "events": 0,
            },
        )

    try:
        result = detect_clusters(
            data,
            lambda prompt, schema, limit: metered.structured(
                prompt, ClusterListResponse, schema, limit
            ),
            dropped,
            unread,
        )
    except ClusterError as failed:
        # No answer could be read twice: nothing is named this run, and the
        # line shows the events alone where nothing passes; never a cluster
        # named after its years [Oracle: R-0843]. A stored model cluster that
        # fails a judgement is removed all the same [Oracle: R-0840].
        kept, failing = _judged(data)
        observe(
            ObservationKind.ClusterFailed,
            {
                "check": failed.check.value,
                "detail": str(failed),
                "fallback": False,
                "reason": failed.check.value,
            },
        )
        _log.warning(f"Turn {turn_id} grouping answer unreadable twice: {failed}")
        for cluster, check, why in failing:
            _log.warning(f"Turn {turn_id} removes: {why}")
            observe(
                ObservationKind.ClusterFailed,
                {
                    "check": check.value,
                    "detail": why,
                    "fallback": False,
                    "reason": check.value,
                    "removed": str(cluster["id"]),
                },
            )
        if not failing:
            return None
        change = record.apply(
            diagram_id,
            [
                {
                    "item_kind": ItemKind.Cluster.value,
                    "item_id": str(cluster["id"]),
                    "field": None,
                    "after": None,
                }
                for cluster, _, _ in failing
            ],
            author=Author.Coach,
            turn_id=turn_id,
            user_id=user_id,
            session_id=session_id,
        )
        return Regroup(change=change, sentences=[])
    deltas = _deltas(data.clusters, result.clusters, dates)
    deltas.append(
        {
            "item_kind": ItemKind.Diagram.value,
            "item_id": None,
            "field": "clusterCacheKey",
            "after": cache_key,
        }
    )
    change = record.apply(
        diagram_id,
        deltas,
        author=Author.Coach,
        turn_id=turn_id,
        user_id=user_id,
        session_id=session_id,
    )
    return Regroup(change=change, sentences=result.changes)
