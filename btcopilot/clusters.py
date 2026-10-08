"""Noticing the periods of heightened difficulty in a family's events, each held
as a loose hypothesis that something bigger shifted in the family around then.

The rules' runs of events are computed with no model call and go to the model
as a hint only, never stored. The model reads every event, with the periods the
diagram already has (the person's own marked as theirs), and returns the
periods as they should now stand: it may rename, reshape, merge or drop any of
them. The code only backstops: three events at least, nothing over ten years,
and two periods sharing days become one, since the family is one unit. Spec
and ruling ids: doc/CLUSTERS.md.
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
# 8: periods as hypotheses of a family process, the person's own free to
# reshape, overlaps merged, no fallback [Oracle: R-0841 to R-0846].
DETECTION_VERSION = 8

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
# model is asked again with the reason; on the second answer it is dropped and
# the rest kept [Oracle: R-0837, R-0846]. It only catches an answer that draws
# the family's whole span as one period; edges stay the model's call. A group
# that long is a stage of the household or the family's ordinary level, not a
# disturbance of it. The sources bound the number on both sides.
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
# edge [Oracle: R-0842].
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
    NoName = "no_name"
    NoReason = "no_reason"
    UnknownGroup = "unknown_group"
    GroupTwice = "group_twice"
    OutsideWords = "outside_words"
    TooLong = "too_long"
    Merged = "merged"
    CutOff = "cut_off"
    Unreadable = "unreadable"
    CallFailed = "call_failed"


class ClusterError(Exception):
    """The model's answer, or one cluster in it, fails a check. `said` is the
    model's own answer for that cluster, for the observations row."""

    def __init__(self, message: str, check: ClusterCheck, said: dict | None = None):
        super().__init__(message)
        self.check = check
        self.said = said


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
    """Whether two groups would share a day on the timeline [Oracle: R-0845].
    Two groups that only touch on one day do not: the page draws neighbouring
    pills apart at a seam (web/src/picture.ts, `edges`), so touching is the
    one closeness it can still draw as two."""
    return a[0] < b[1] and b[0] < a[1]


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


THEIRS = "the person drew this period"


def _prompt(cands: list[Candidate], free: list[Event], stored: dict[str, dict]) -> str:
    when = {e.id: parse_date(e.dateTime) for e in free}
    existing = []
    for cluster_id, cluster in stored.items():
        shown = {
            "id": cluster_id,
            "name": _title(cluster),
            "reason": cluster.get("reason") or cluster.get("summary") or "",
            "eventIds": cluster.get("eventIds") or [],
        }
        if not _regroupable(cluster):
            shown["note"] = THEIRS
        existing.append(shown)
    return prompts.CLUSTER_PROMPT.format(
        existing=json.dumps(existing, indent=2),
        candidates=json.dumps(
            [
                {"before": _before(candidate, when), "eventIds": candidate.eventIds}
                for candidate in cands
            ],
            indent=2,
        ),
        events=json.dumps([_event_json(e) for e in free], indent=2),
    )


def _title(cluster: dict) -> str:
    return cluster.get("name") or cluster.get("title") or ""


def _sculpted(cluster: ModelCluster, was: dict) -> bool:
    """Whether the model handed a stored grouping back other than as it was."""
    return set(cluster.eventIds) != set(was.get("eventIds") or []) or (
        cluster.name != _title(was)
    )


def _said_of(cluster: ModelCluster, when: dict[int, datetime.date]) -> dict:
    """The model's own answer for one cluster, as an observations row keeps it."""
    dates = [when[i] for i in cluster.eventIds if i in when]
    return {
        "name": cluster.name,
        "eventIds": list(cluster.eventIds),
        "start": min(dates).isoformat() if dates else None,
        "end": max(dates).isoformat() if dates else None,
    }


def _fault(
    cluster: ModelCluster,
    known: set[int],
    stored: dict[str, dict],
    claimed: set[str],
) -> tuple[str, ClusterCheck] | None:
    """What makes one returned cluster unusable before any merge, or nothing."""
    unknown = [event_id for event_id in cluster.eventIds if event_id not in known]
    if unknown:
        return f"Events {unknown} are not among the events you were given.", (
            ClusterCheck.UnknownEvent
        )
    if not cluster.name.strip():
        return "Every period needs a name.", ClusterCheck.NoName
    if not cluster.reason.strip():
        return "Every period needs a reason.", ClusterCheck.NoReason
    if cluster.id is not None and cluster.id not in stored:
        return (
            f"Period {cluster.id!r} is not one this diagram already has.",
            ClusterCheck.UnknownGroup,
        )
    if cluster.id is not None and cluster.id in claimed:
        return f"Period {cluster.id!r} came back twice.", ClusterCheck.GroupTwice
    spoken = " ".join([cluster.name, cluster.reason, cluster.change or ""]).lower()
    outside = [word for word in OUTSIDE_WORDS if word in spoken]
    if outside:
        return (
            f"Period {cluster.name!r} uses {outside}, which the definitions you "
            "were given do not contain.",
            ClusterCheck.OutsideWords,
        )
    return None


def _merged(
    clusters: list[ModelCluster], when: dict[int, datetime.date]
) -> tuple[list[ModelCluster], list[tuple[ModelCluster, ModelCluster]]]:
    """Periods sharing a day or an event made one: the family is one emotional
    unit, so one reading of it never draws two periods over the same days
    [Oracle: R-0845]. The one holding more events carries the name and id, the
    earlier on a tie. Returns the periods and each one absorbed with the period
    it went into."""

    def span(cluster: ModelCluster) -> Span:
        return span_of([when[i] for i in cluster.eventIds])

    out: list[ModelCluster] = []
    absorbed: list[tuple[ModelCluster, ModelCluster]] = []
    for cluster in sorted(clusters, key=lambda c: (span(c)[0], span(c)[1])):
        last = out[-1] if out else None
        if last is None or not (
            overlapping(span(last), span(cluster))
            or set(last.eventIds) & set(cluster.eventIds)
        ):
            out.append(cluster)
            continue
        keep, lose = (
            (last, cluster)
            if len(last.eventIds) >= len(cluster.eventIds)
            else (cluster, last)
        )
        events = sorted(
            set(last.eventIds) | set(cluster.eventIds), key=lambda i: (when[i], i)
        )
        out[-1] = ModelCluster(
            id=keep.id,
            eventIds=events,
            name=keep.name,
            reason=keep.reason,
            change=keep.change,
        )
        absorbed.append((lose, out[-1]))
    return out, absorbed


@dataclass
class Screened:
    """One answer read against the checks: the periods that pass, each period
    that fails with why, and each period merged into another."""

    kept: list[ModelCluster]
    faults: list[ClusterError]
    absorbed: list[tuple[ModelCluster, ModelCluster]]


def _screen(
    response: ClusterListResponse | None,
    free: list[Event],
    stored: dict[str, dict],
) -> Screened:
    if response is None:
        raise ClusterError("No grouping came back.", ClusterCheck.Missing)
    known = {e.id for e in free}
    when = {e.id: parse_date(e.dateTime) for e in free}
    faults: list[ClusterError] = []
    usable: list[ModelCluster] = []
    claimed: set[str] = set()
    for cluster in response.clusters:
        fault = _fault(cluster, known, stored, claimed)
        if fault:
            faults.append(ClusterError(*fault, said=_said_of(cluster, when)))
            continue
        if not cluster.eventIds:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} holds no events.",
                    ClusterCheck.TooSmall,
                    _said_of(cluster, when),
                )
            )
            continue
        if cluster.id is not None:
            claimed.add(cluster.id)
        usable.append(cluster)
    merged, absorbed = _merged(usable, when)
    kept = []
    for cluster in merged:
        said = _said_of(cluster, when)
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} holds {len(cluster.eventIds)} events; "
                    f"anything under {MIN_CLUSTER_EVENTS} is never a period.",
                    ClusterCheck.TooSmall,
                    said,
                )
            )
        elif too_long([when[i] for i in cluster.eventIds]):
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} runs from {said['start'][:4]} to "
                    f"{said['end'][:4]}: more than {MAX_SPAN_YEARS} years is this "
                    "family's ordinary level, not a period. Return the periods "
                    "inside it.",
                    ClusterCheck.TooLong,
                    said,
                )
            )
        else:
            kept.append(cluster)
    return Screened(kept=kept, faults=faults, absorbed=absorbed)


def _stored(data: DiagramData) -> list[dict]:
    return [
        cluster
        for cluster in data.clusters
        if isinstance(cluster, dict) and cluster.get("id") is not None
    ]


def _judged(
    data: DiagramData,
) -> tuple[dict[str, dict], list[tuple[dict, ClusterCheck, str]]]:
    """The stored clusters handed back to the model, by id, and each stored
    model cluster that fails the ten-year backstop with a sentence naming its
    years. The person's own are always handed back, as hypotheses the model
    may reshape [Oracle: R-0843]."""
    when = {e.id: parse_date(e.dateTime) for e in _dated(data)}
    kept, failing = {}, []
    for cluster in _stored(data):
        dates = [when[i] for i in cluster.get("eventIds") or [] if i in when]
        if not _regroupable(cluster) or not too_long(dates):
            kept[str(cluster["id"])] = cluster
            continue
        name = _said(_title(cluster), span_of(dates))
        failing.append(
            (
                cluster,
                ClusterCheck.TooLong,
                f"Stored grouping {cluster['id']} {name} fails the "
                f"{MAX_SPAN_YEARS}-year check",
            )
        )
    return kept, failing


def mine(data: DiagramData) -> dict[str, dict]:
    """The stored clusters handed to the model as existing. A model cluster
    over ten years is left out, its events back to the hint, and the diagram
    regroups on this run [Oracle: R-0838]."""
    kept, failing = _judged(data)
    for _, _, why in failing:
        _log.info(f"{why} and is not handed back")
    return kept


def broken(data: DiagramData) -> list[tuple[dict, ClusterCheck, str]]:
    """The stored model clusters that fail the backstop, each with the check
    and a sentence naming its years."""
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
    refused answer, dropped cluster and merged cluster with its attempt number
    and the answer it came in.

    A first answer with any fault is asked for once more with the reasons. On
    the second, a cluster that still fails is dropped and the rest kept; an
    answer that cannot be read, or keeps nothing out of what it returned,
    raises [Oracle: R-0846, R-0844]."""
    cache_key = compute_cache_key(_dated(data))
    cands = candidates(data)
    if not cands:
        return ClusterResult(clusters=[], cacheKey=cache_key)

    free = joinable(data)
    taken = {str(cluster["id"]) for cluster in _stored(data)}
    existing = mine(data)
    prompt = _prompt(cands, free, existing)
    schema = answer_schema(existing)
    limit = THINKING_ROOM + PER_EVENT * len(free)
    _log.info(
        f"Grouping {len(free)} events: {len(existing)} groups already there, "
        f"{len(cands)} proposed as a hint"
    )

    def heard(attempt: int, error: ClusterError, answer) -> None:
        _log.warning(f"Grouping answer {attempt}: {error}")
        if refused:
            refused(attempt, error, answer)

    def attempt(n: int, words: str) -> Screened:
        answer = None
        try:
            answer = _answered(ask, words, schema, limit)
            screened = _screen(answer, free, existing)
        except ClusterError as failed:
            heard(n, failed, answer)
            raise
        for fault in screened.faults:
            heard(n, fault, answer)
        for lost, into in screened.absorbed:
            heard(
                n,
                ClusterError(
                    f"Period {lost.name!r} shares days with {into.name!r} and is "
                    "merged into it.",
                    ClusterCheck.Merged,
                    _said_of(lost, {e.id: parse_date(e.dateTime) for e in free}),
                ),
                answer,
            )
        if n == 2 and screened.faults and not screened.kept and answer.clusters:
            raise screened.faults[0]
        return screened

    try:
        screened = attempt(1, prompt)
        retry = bool(screened.faults)
        why = " ".join(str(fault) for fault in screened.faults)
    except ClusterError as failed:
        retry, why = True, str(failed)
    if retry:
        screened = attempt(2, prompt + prompts.CLUSTER_REJECTED.format(why=why))

    when = {e.id: e.dateTime for e in free}
    clusters, changes = [], []
    for cluster in screened.kept:
        spanned = sorted(when[event_id] for event_id in cluster.eventIds)
        cluster_id = cluster.id or next_id(taken)
        taken.add(cluster_id)
        was = existing.get(cluster.id) if cluster.id else None
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
                source=(
                    _source(was)
                    if was is not None and not _sculpted(cluster, was)
                    else ClusterSource.Model
                ),
            )
        )
        if cluster.change:
            changes.append(cluster.change)
            _log.info(f"Regrouped {cluster.name!r}: {cluster.change}")
    return ClusterResult(clusters=clusters, cacheKey=cache_key, changes=changes)


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
    """The model's grouping, each cluster under its own id: the model's own
    statement of which stored cluster it is, so what the coach said about it
    last turn still points at something the diagram holds. A grouping under the
    minimum is a bug in whatever produced it and raises."""
    taken = {str(c["id"]) for c in stored}
    kept: dict[str, Cluster] = {}
    for cluster in detected:
        event_ids = [e for e in cluster.eventIds if e in dates]
        if len(event_ids) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Grouping {cluster.eventIds} arrived holding fewer than "
                f"{MIN_CLUSTER_EVENTS} events.",
                ClusterCheck.TooSmall,
            )
        cluster.eventIds = event_ids
        cluster.name = cluster.name or cluster.title
        spanned = sorted(dates[e] for e in event_ids)
        cluster.startDate, cluster.endDate = spanned[0], spanned[-1]
        cluster.id = str(cluster.id) if cluster.id else next_id(taken | set(kept))
        kept[cluster.id] = cluster
    return kept


def _deltas(stored: list[dict], detected: list[Cluster], dates: dict) -> list[dict]:
    """Every stored cluster the answer did not return is removed, the person's
    own included: the model was shown each one and may reshape, merge or drop
    it [Oracle: R-0843]."""
    stored = [c for c in stored if isinstance(c, dict) and c.get("id") is not None]
    held = {str(c["id"]): c for c in stored}
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
    have it still be there next turn. The rules' runs are a hint; the model
    decides the periods, the person's own included, and never invents a member.
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
                **(error.said or {}),
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
        # No usable answer: the clusters that pass stay, a stored model cluster
        # over ten years is removed, its events dots until a regroup passes;
        # nothing is ever named after its years [Oracle: R-0840, R-0844].
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
        _log.warning(f"Turn {turn_id} grouping refused twice: {failed}")
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
