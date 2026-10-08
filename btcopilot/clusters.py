"""Grouping the record's events into clusters: the rules propose, the model rules.

The candidates are computed from the record with no model call at all, and are
a proposal rather than a boundary. The grouping the record already has is handed
to the model with its ids and kept unless the record now says otherwise; the
model may merge, split, or reach for a further event whenever it says in one
sentence what made the old shape wrong. One check is about kind rather than
edges: a group spanning more than ten years is refused, and a stored group that
fails it is not handed back as existing. Spec and ruling ids: doc/CLUSTERS.md.
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
# grouped by the older rules re-groups on its next event-changing turn. 6: the
# prompt lines the books contradict reworded and the ten-year check added, so
# every record regroups on its next event change [Oracle: R-0836, R-0838].
# 7: two groups never share years, the person's own shown to the model and
# counted, so every record regroups on its next event change [Oracle: R-0839].
DETECTION_VERSION = 7

NODAL_KINDS = frozenset(
    {EventKind.Death, EventKind.Married, EventKind.Divorced, EventKind.Separated}
)
SHIFT_FIELDS = ("symptom", "anxiety", "relationship", "functioning")

# How far either side of a nodal event or shift a related event is proposed as
# part of the same cluster. A suggestion to the model, not a limit on what it
# may hand back: an event outside it joins when the model says why. Same for
# CALM_GAP_DAYS, the stretch with nothing recorded that proposes a break. The
# floor of three events is the one number that is ruled and enforced
# (MIN_CLUSTER_EVENTS in schema.py), at the model's answer and again at the write.
SPAN_DAYS = 548
# The grouping answer's token limit, thinking included: room for the thinking
# (its budget is 1024, yet calls on a 91-event record used up to 2454) and, per
# event the record may group, its id in the answer and its share of the names,
# reasons and changes (accepted answers used about 9). 89 groupable events get
# 6232 tokens; with no limit, one answer repeated a sentence for 63000.
THINKING_ROOM = 4096
PER_EVENT = 24
CALM_GAP_DAYS = 730
# A returned group whose dated events span more than this is refused and the
# model is asked again with the reason [Oracle: R-0837]. A rule about kind, not
# edges: a group that long is a stage of the household or the family's ordinary
# level, not a disturbance of it. The sources bound the number on both sides.
# Above: the longest run of dated events any of them draws as one period of
# stress is five years, the longest named family period a six-year plateau of
# illness, and the one decade accepted as a single tag was events leading up to
# a death held together by one man's long illness (Family Therapy in Clinical
# Practice ch. 21 and ch. 3; the seminar; theory.md T105 to T108 in the corpus
# research). Below: Bowen's typical stage of the household is "ten years"
# (Basic Series 3, T1), and his own ten-year narrative chapter is several
# periods of stress with calm between (ch. 21, T81). Ten is the smallest whole
# number no wave on record reaches and the first a stage does. It binds nothing
# inside the range the sources place waves, so the model still judges every
# edge [Oracle: R-0374].
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
    """Which check refused a grouping, so refusals are counted by kind."""

    Missing = "missing"
    UnknownEvent = "unknown_event"
    TooSmall = "too_small"
    InTwoGroups = "in_two_groups"
    NoName = "no_name"
    NoReason = "no_reason"
    UnknownGroup = "unknown_group"
    GroupTwice = "group_twice"
    NoChangeReason = "no_change_reason"
    OutsideWords = "outside_words"
    TooLong = "too_long"
    Overlap = "overlap"
    LeftOut = "left_out"
    CutOff = "cut_off"
    Unreadable = "unreadable"
    CallFailed = "call_failed"


class ClusterError(Exception):
    """The model's grouping is not a legal reworking of the candidates."""

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
    """Whether a group's dated events span more than MAX_SPAN_YEARS
    [Oracle: R-0837]."""
    return bool(dates) and max(dates) > _years_after(min(dates), MAX_SPAN_YEARS)


Span = tuple[datetime.date, datetime.date]


def span_of(dates: list[datetime.date]) -> Span | None:
    """The years the timeline draws for a group: its first dated event to its
    last; nothing for a group with no dated event of its own."""
    return (min(dates), max(dates)) if dates else None


def overlapping(a: Span, b: Span) -> bool:
    """Whether two groups would share a day on the timeline [Oracle: R-0839].
    Two groups that only touch on one day do not: the page draws neighbouring
    pills apart at a seam (web/src/picture.ts, `edges`), so touching is the
    one closeness it can still draw as two."""
    return a[0] < b[1] and b[0] < a[1]


def _overlap(
    spans: list[tuple[str, Span]],
) -> tuple[tuple[str, Span], tuple[str, Span]] | None:
    """The first pair of groups whose years overlap, or nothing."""
    for n, (label, span) in enumerate(spans):
        for other, theirs in spans[n + 1 :]:
            if overlapping(span, theirs):
                return (label, span), (other, theirs)
    return None


def _said(label: str, span: Span) -> str:
    return f"{label} ({span[0].isoformat()} to {span[1].isoformat()})"


def silence(gap: datetime.timedelta) -> str:
    """The stretch with nothing recorded before a proposed group, in the plain
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


def joinable(data: DiagramData) -> list[Event]:
    """Every dated event a cluster may hold: the scaffolding is held out."""
    events = _dated(data)
    marked = [e for e in events if is_nodal_or_shift(e)]
    if not marked:
        return []
    opens = parse_date(marked[0].dateTime)
    return [e for e in events if not _scaffold(e, opens)]


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
    """The clusters the record itself asserts, with no model in the loop."""
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
    change: str | None = None


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


def _title(cluster: dict) -> str:
    return cluster.get("name") or cluster.get("title") or ""


def _sculpted(cluster: ModelCluster, was: dict) -> bool:
    """Whether the model handed a stored grouping back other than as it was."""
    return set(cluster.eventIds) != set(was.get("eventIds") or []) or (
        cluster.name != _title(was)
    )


def _check(
    response: ClusterListResponse | None,
    cands: list[Candidate],
    free: list[Event],
    stored: dict[str, dict],
    fixed: list[tuple[str, Span]] = (),
    theirs: set[int] = frozenset(),
) -> list[ModelCluster]:
    """`fixed` is the years of the groups the person made, which the model
    may not touch, and `theirs` the events in them: a returned group is
    measured without those events, as the write will store it."""
    if response is None:
        raise ClusterError("No grouping came back.", ClusterCheck.Missing)

    known = {e.id for e in free}
    when = {e.id: parse_date(e.dateTime) for e in free}
    shapes = {frozenset(candidate.eventIds) for candidate in cands}
    marked = {i for candidate in cands for i in candidate.nodalOrShiftIds}
    seen: set[int] = set()
    claimed: set[str] = set()
    drawn = [(f"the group this person made, {name!r}", span) for name, span in fixed]
    for cluster in response.clusters:
        unknown = [event_id for event_id in cluster.eventIds if event_id not in known]
        if unknown:
            raise ClusterError(
                f"Events {unknown} are not among the events you were given.",
                ClusterCheck.UnknownEvent,
            )
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Group {cluster.eventIds} holds fewer than {MIN_CLUSTER_EVENTS} events; "
                "anything smaller is never a cluster.",
                ClusterCheck.TooSmall,
            )
        repeated = seen & set(cluster.eventIds)
        if repeated:
            raise ClusterError(
                f"Events {sorted(repeated)} are in two clusters.",
                ClusterCheck.InTwoGroups,
            )
        seen.update(cluster.eventIds)
        if not cluster.name.strip():
            raise ClusterError("Every cluster needs a name.", ClusterCheck.NoName)
        if not cluster.reason.strip():
            raise ClusterError("Every cluster needs a reason.", ClusterCheck.NoReason)
        if cluster.id is not None:
            if cluster.id not in stored:
                raise ClusterError(
                    f"Group {cluster.id!r} is not one of the groups this record "
                    "already has.",
                    ClusterCheck.UnknownGroup,
                )
            if cluster.id in claimed:
                raise ClusterError(
                    f"Group {cluster.id!r} came back twice.", ClusterCheck.GroupTwice
                )
            claimed.add(cluster.id)
        was = stored.get(cluster.id) if cluster.id is not None else None
        changed = (
            _sculpted(cluster, was)
            if was is not None
            else frozenset(cluster.eventIds) not in shapes
        )
        if changed and not (cluster.change or "").strip():
            raise ClusterError(
                f"Cluster {cluster.name!r} is not the grouping you were given "
                "and says no reason for the change.",
                ClusterCheck.NoChangeReason,
            )
        spanned = [when[event_id] for event_id in cluster.eventIds]
        if too_long(spanned):
            raise ClusterError(
                f"Cluster {cluster.name!r} runs from {min(spanned).year} to "
                f"{max(spanned).year}: a group of more than {MAX_SPAN_YEARS} years "
                "is this family's ordinary level, not a disturbance of it. Return "
                "the groups inside it.",
                ClusterCheck.TooLong,
            )
        spoken = " ".join([cluster.name, cluster.reason, cluster.change or ""]).lower()
        outside = [word for word in OUTSIDE_WORDS if word in spoken]
        if outside:
            raise ClusterError(
                f"Cluster {cluster.name!r} uses {outside}, which the definitions "
                "you were given do not contain.",
                ClusterCheck.OutsideWords,
            )
        own = span_of([when[i] for i in cluster.eventIds if i not in theirs])
        if own:
            drawn.append((f"the group {cluster.name!r}", own))
    dropped = marked - seen
    if dropped:
        raise ClusterError(
            f"Events {sorted(dropped)} were left out.", ClusterCheck.LeftOut
        )
    # The timeline is one line, so two groups never share a day [Oracle: R-0839].
    shared = _overlap(drawn)
    if shared:
        (first, span), (second, other) = shared
        said = _said(first, span)
        raise ClusterError(
            f"{said[0].upper()}{said[1:]} and {_said(second, other)} overlap "
            "in time. The timeline is one line, so two groups never share a day: "
            "give each its own years, or make them one group.",
            ClusterCheck.Overlap,
        )
    return response.clusters


def _stored(data: DiagramData) -> list[dict]:
    return [
        cluster
        for cluster in data.clusters
        if isinstance(cluster, dict) and cluster.get("id") is not None
    ]


def _dates(
    cluster: dict, when: dict[int, datetime.date], held: set[int] = frozenset()
) -> list[datetime.date]:
    return [
        when[i] for i in cluster.get("eventIds") or [] if i in when and i not in held
    ]


def _theirs(data: DiagramData) -> tuple[set[int], list[tuple[str, Span]]]:
    """The events in the groups the person made, and each such group's name and
    years as the timeline draws them. Such a group's own dates stand in where
    its events are not dated in the record."""
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


def _holds(
    cluster: dict,
    when: dict[int, datetime.date],
    held: set[int],
    around: list[tuple[str, Span]],
) -> ClusterCheck | None:
    """Which definitional check a stored grouping fails, or nothing."""
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
    """The stored model groupings that pass the checks, by id, and each one that
    fails with a sentence naming its years and the check it fails."""
    when = {e.id: parse_date(e.dateTime) for e in _dated(data)}
    held, fixed = _theirs(data)
    model = [c for c in _stored(data) if _regroupable(c)]
    around = {
        str(c["id"]): (f"the group {_title(c)!r}", span_of(_dates(c, when, held)))
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
            (cluster, check, f"Stored grouping {cluster['id']} {name} fails {why}")
        )
    return kept, failing


def mine(data: DiagramData) -> dict[str, dict]:
    """The stored groupings the model made and may be handed back as existing.
    One that fails a check is left out: keeping what is there protects a
    reading, not a category error, so its events fall back to the proposal and
    the record regroups on this run [Oracle: R-0838, R-0839]. A model group
    whose years overlap another stored group's, the person's own included, is
    such a one; the person's own groups are never regrouped and so never fail.
    Two model groups overlapping each other both fail: neither has a better
    claim to the years."""
    kept, failing = _judged(data)
    for _, _, why in failing:
        _log.info(f"{why} and is not handed back")
    return kept


def broken(data: DiagramData) -> list[tuple[dict, ClusterCheck, str]]:
    """The stored model groupings that fail a check, each with the check and a
    sentence naming its years and the check."""
    return _judged(data)[1]


def answer_schema(stored: dict[str, dict]) -> dict:
    """The answer's shape, with `id` limited to the groups the record holds and
    left out when it holds none, and every group's events, name and reason
    required. Offered a free-text id, the grouping model wrote one for every
    new group, and the check refused each answer; with nothing required, it
    once left out every group's events."""
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


def _answered(ask, prompt: str, schema: dict, limit: int) -> "ClusterListResponse":
    """An answer cut off at its limit, unreadable, or never given is refused
    like any other, so grouping never fails the turn."""
    try:
        return ask(prompt, schema, limit)
    except OutputTruncatedError as cut:
        raise ClusterError(
            "Your answer ran past its length limit. Give each name, reason and "
            "change in one short sentence.",
            ClusterCheck.CutOff,
        ) from cut
    except Unreadable as garbled:
        raise ClusterError(
            "Your answer was not the JSON asked for.", ClusterCheck.Unreadable
        ) from garbled
    except (Billed, *UNANSWERED) as failed:
        raise ClusterError(
            f"The grouping call failed: {type(failed).__name__}",
            ClusterCheck.CallFailed,
        ) from failed


def detect_clusters(data: DiagramData, ask, refused=None) -> ClusterResult:
    """`ask` takes the prompt, the answer's schema and its token limit and
    returns the model's ClusterListResponse; `refused`, when given, hears each
    refused answer with its attempt number."""
    cache_key = compute_cache_key(_dated(data))
    cands = candidates(data)
    if not cands:
        return ClusterResult(clusters=[], cacheKey=cache_key)

    free = joinable(data)
    taken = {str(cluster["id"]) for cluster in _stored(data)}
    existing = mine(data)
    theirs, fixed = _theirs(data)
    prompt = _prompt(cands, free, existing, fixed)
    schema = answer_schema(existing)
    limit = THINKING_ROOM + PER_EVENT * len(free)
    _log.info(
        f"Grouping {len(free)} events: {len(existing)} groups already there, "
        f"{len(cands)} proposed"
    )
    answer = None
    try:
        answer = _answered(ask, prompt, schema, limit)
        named = _check(answer, cands, free, existing, fixed, theirs)
    except ClusterError as rejected:
        _log.warning(f"Grouping sent back: {rejected}")
        if refused:
            refused(1, rejected, answer)
        answer = None
        try:
            answer = _answered(
                ask,
                prompt + prompts.CLUSTER_REJECTED.format(why=rejected),
                schema,
                limit,
            )
            named = _check(answer, cands, free, existing, fixed, theirs)
        except ClusterError as again:
            if refused:
                refused(2, again, answer)
            raise

    when = {e.id: e.dateTime for e in free}
    clusters, changes = [], []
    for cluster in named:
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
        if cluster.change:
            changes.append(cluster.change)
            _log.info(f"Regrouped {cluster.name!r}: {cluster.change}")
    return ClusterResult(clusters=clusters, cacheKey=cache_key, changes=changes)


def years(start: str, end: str) -> str:
    first, last = parse_date(start).year, parse_date(end).year
    return str(first) if first == last else f"{first}–{last}"


def _one_axis(cands: list[Candidate], when: dict) -> list[list[int]]:
    """Proposals whose years overlap as one fallback group, whatever their
    people: the fallback stores what it is given, and the timeline is one line
    [Oracle: R-0839]. Proposals that only touch on a day stay two."""
    joined: list[list[int]] = []
    for candidate in cands:
        ids = candidate.eventIds
        if joined and overlapping(
            (when[joined[-1][0]], when[joined[-1][-1]]), (when[ids[0]], when[ids[-1]])
        ):
            joined[-1] = sorted(joined[-1] + ids, key=lambda i: (when[i], i))
        else:
            joined.append(list(ids))
    return joined


def _apart(
    ids: list[int], when: dict, held: set[int], spans: list[Span]
) -> list[list[int]]:
    """A proposal's events less the person's own and any dated inside the years
    of a group the person made, cut wherever such a group falls between two of
    them, so no piece shares a day with theirs [Oracle: R-0839]."""
    pieces: list[list[int]] = [[]]
    for event_id in ids:
        day = when[event_id]
        if event_id in held or any(start < day < end for start, end in spans):
            continue
        if pieces[-1] and any(
            overlapping((when[pieces[-1][-1]], day), span) for span in spans
        ):
            pieces.append([])
        pieces[-1].append(event_id)
    return pieces


def by_years(data: DiagramData, cache_key: str) -> ClusterResult:
    """The rules' groups, each titled with the years it spans, for a turn whose
    grouping answers were all refused. Proposals sharing years are joined, and
    cut around the groups the person made, as the write would otherwise store
    them across each other or across theirs."""
    taken = {str(cluster["id"]) for cluster in _stored(data)}
    held, fixed = _theirs(data)
    spans = [span for _, span in fixed]
    when = {e.id: parse_date(e.dateTime) for e in joinable(data)}
    cands = candidates(data)
    marked = {i for candidate in cands for i in candidate.nodalOrShiftIds}
    made = []
    for group in _one_axis(cands, when):
        for ids in _apart(group, when, held, spans):
            if len(ids) < MIN_CLUSTER_EVENTS or not marked & set(ids):
                continue
            cluster_id = next_id(taken)
            taken.add(cluster_id)
            start, end = when[ids[0]].isoformat(), when[ids[-1]].isoformat()
            title = years(start, end)
            made.append(
                Cluster(
                    id=cluster_id,
                    title=title,
                    name=title,
                    summary="",
                    eventIds=ids,
                    startDate=start,
                    endDate=end,
                    source=ClusterSource.Model,
                )
            )
    return ClusterResult(clusters=made, cacheKey=cache_key)


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


def _source(cluster: dict) -> ClusterSource | None:
    source = cluster.get("source")
    return ClusterSource(source) if source else None


def _regroupable(cluster: dict) -> bool:
    """Only a grouping the model is known to have made may be regrouped.
    A cluster of unknown provenance is treated as the user's, because the coach
    does not overwrite what the user asked for and the cost is asymmetric:
    guessing wrong about the model loses a name the user chose."""
    return _source(cluster) is ClusterSource.Model


def _detected(stored: list[dict], detected: list[Cluster], dates: dict) -> dict:
    """The model's grouping, with every event a grouping it may not touch owns
    held out. Each group already carries its own id, the model's own statement
    of which stored grouping it is, so what the coach said about it last turn
    still points at something the record holds. A grouping that arrives under
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
                f"Grouping {cluster.eventIds} arrived holding fewer than "
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
                f"Grouping {cluster.id} is not one the model may write over.",
                ClusterCheck.UnknownGroup,
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
    grouping it reshaped, in story rather than in the language of grouping."""

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
    have it still be there next turn. The rules propose the groups; the model
    decides them, keeping what is already there unless the record now says
    otherwise. It never invents a member, and it never touches a cluster the
    user made — those events are held out of the detection and a model grouping
    that overlaps one yields the overlap to it.
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

    def refused(attempt: int, error: ClusterError, answer) -> None:
        groups = answer.clusters if answer else []
        observe(
            ObservationKind.ClusterRefused,
            {
                "attempt": attempt,
                "check": error.check.value,
                "detail": str(error),
                "groups": len(groups),
                "events": sum(len(g.eventIds) for g in groups),
                "reason": error.check.value,
            },
        )

    try:
        result = detect_clusters(
            data,
            lambda prompt, schema, limit: metered.structured(
                prompt, ClusterListResponse, schema, limit
            ),
            refused,
        )
    except ClusterError as failed:
        # Both answers refused: the rules' groups go in under their years, unless
        # the model's own groups are already there to keep [Oracle: R-0780]. A
        # stored group that fails the check is not one to keep [Oracle: R-0838].
        kept, failing = _judged(data)
        fallback = not kept
        observe(
            ObservationKind.ClusterFailed,
            {
                "check": failed.check.value,
                "detail": str(failed),
                "fallback": fallback,
                "reason": failed.check.value,
            },
        )
        _log.warning(f"Turn {turn_id} grouping refused twice: {failed}")
        if not fallback:
            # The model's groups that pass are kept; one that fails a check is
            # removed, its events dots until a regroup passes [Oracle: R-0840].
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
        result = by_years(data, cache_key)
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
