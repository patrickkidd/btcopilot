"""Grouping the record's events into clusters: rules first, model second.

The candidates are computed from the record with no model call at all. The
model only names each one, says in a sentence what its events have in common,
and may merge, split, or reach for a further event when it states why. Spec and
ruling ids: doc/chat-first/CLUSTERS.md.
"""

import datetime
import json
import logging
from dataclasses import dataclass, field

from btcopilot.extensions import db
from btcopilot.llmutil import gemini_structured_sync
from btcopilot.personal import record
from btcopilot.personal.intake import NODAL_KINDS, SHIFT_FIELDS, _parse_iso_date
from btcopilot.personal.models import Author
from btcopilot.personal.prompts import CLUSTER_PROMPT, CLUSTER_REJECTED
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    MIN_CLUSTER_EVENTS,
    Cluster,
    ClusterResult,
    ClusterSource,
    DiagramData,
    Event,
    ItemKind,
    PairBond,
    asdict,
    from_dict,
    hash_sarf_dicts,
)

_log = logging.getLogger(__name__)

# Bumped whenever the candidate rules or the naming prompt change, so a record
# grouped by the older rules re-groups on its next event-changing turn.
DETECTION_VERSION = 4

# How far either side of a nodal event or shift a related event may sit and
# still be part of the same cluster.
SPAN_DAYS = 548

# A stretch this long with no nodal event or shift in it ends a cluster.
CALM_GAP_DAYS = 730

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


class ClusterError(Exception):
    """The model's grouping is not a legal reworking of the candidates."""


def _enum_value(val):
    """Extract enum value or return as-is for non-enum types."""
    return val.value if hasattr(val, "value") else val


def is_nodal_or_shift(event: Event) -> bool:
    """The kinds the intake engine counts as nodal, or any recorded shift."""
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
        and _parse_iso_date(event.dateTime) < opens
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


def _dated(data: DiagramData) -> list[Event]:
    events = [
        from_dict(Event, chunk)
        for chunk in data.events
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]
    dated = [e for e in events if _parse_iso_date(e.dateTime)]
    return sorted(dated, key=lambda e: (_parse_iso_date(e.dateTime), e.id))


def joinable(data: DiagramData) -> list[Event]:
    """Every dated event a cluster may hold: the scaffolding is held out."""
    events = _dated(data)
    marked = [e for e in events if is_nodal_or_shift(e)]
    if not marked:
        return []
    opens = _parse_iso_date(marked[0].dateTime)
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
    when = {e.id: _parse_iso_date(e.dateTime) for e in free}

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
        overlapping = [group for group in groups if group & near]
        for group in overlapping:
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
        if len(ids) >= MIN_CLUSTER_EVENTS and any(event_id in marked_ids for event_id in ids)
    ]
    return sorted(kept, key=lambda c: (c.startDate, c.eventIds[0]))


@dataclass
class ModelCluster:
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


def _prompt(cands: list[Candidate], free: list[Event]) -> str:
    by_id = {e.id: e for e in free}
    blocks = [
        {
            "candidate": n + 1,
            "nodalOrShiftIds": candidate.nodalOrShiftIds,
            "events": [_event_json(by_id[i]) for i in candidate.eventIds],
        }
        for n, candidate in enumerate(cands)
    ]
    grouped = {i for candidate in cands for i in candidate.eventIds}
    return CLUSTER_PROMPT.format(
        candidates=json.dumps(blocks, indent=2),
        unclustered=json.dumps(
            [_event_json(e) for e in free if e.id not in grouped], indent=2
        ),
    )


def _check(
    response: ClusterListResponse | None,
    cands: list[Candidate],
    free: list[Event],
) -> list[ModelCluster]:
    if response is None:
        raise ClusterError("No grouping came back.")

    known = {e.id for e in free}
    shapes = {frozenset(candidate.eventIds) for candidate in cands}
    marked = {i for candidate in cands for i in candidate.nodalOrShiftIds}
    seen: set[int] = set()
    for cluster in response.clusters:
        unknown = [event_id for event_id in cluster.eventIds if event_id not in known]
        if unknown:
            raise ClusterError(
                f"Events {unknown} are not among the events you were given."
            )
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Group {cluster.eventIds} holds fewer than {MIN_CLUSTER_EVENTS} events; "
                "anything smaller is never a cluster."
            )
        repeated = seen & set(cluster.eventIds)
        if repeated:
            raise ClusterError(f"Events {sorted(repeated)} are in two clusters.")
        seen.update(cluster.eventIds)
        if not cluster.name.strip():
            raise ClusterError("Every cluster needs a name.")
        if not cluster.reason.strip():
            raise ClusterError("Every cluster needs a reason.")
        if (
            frozenset(cluster.eventIds) not in shapes
            and not (cluster.change or "").strip()
        ):
            raise ClusterError(
                f"Cluster {cluster.name!r} is not one of the candidates as given "
                "and says no reason for the change."
            )
        spoken = " ".join([cluster.name, cluster.reason, cluster.change or ""]).lower()
        outside = [word for word in OUTSIDE_WORDS if word in spoken]
        if outside:
            raise ClusterError(
                f"Cluster {cluster.name!r} uses {outside}, which the definitions "
                "you were given do not contain."
            )
    dropped = marked - seen
    if dropped:
        raise ClusterError(f"Events {sorted(dropped)} were left out.")
    return response.clusters


def detect_clusters(data: DiagramData) -> ClusterResult:
    cache_key = compute_cache_key(_dated(data))
    cands = candidates(data)
    if not cands:
        return ClusterResult(clusters=[], cacheKey=cache_key)

    free = joinable(data)
    prompt = _prompt(cands, free)
    _log.info(f"Naming {len(cands)} candidate clusters over {len(free)} events")
    try:
        named = _check(gemini_structured_sync(prompt, ClusterListResponse), cands, free)
    except ClusterError as rejected:
        _log.warning(f"Grouping sent back: {rejected}")
        named = _check(
            gemini_structured_sync(
                prompt + CLUSTER_REJECTED.format(why=rejected), ClusterListResponse
            ),
            cands,
            free,
        )

    when = {e.id: e.dateTime for e in free}
    clusters = []
    for n, cluster in enumerate(named):
        spanned = sorted(when[event_id] for event_id in cluster.eventIds)
        clusters.append(
            Cluster(
                id=f"detected{n}",
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
            _log.info(f"Regrouped {cluster.name!r}: {cluster.change}")
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
    n = len(taken) + 1
    while f"c{n}" in taken:
        n += 1
    return f"c{n}"


def _source(cluster: dict) -> ClusterSource | None:
    source = cluster.get("source")
    return ClusterSource(source) if source else None


def _regroupable(cluster: dict) -> bool:
    """Only a grouping the model is known to have made may be regrouped.
    A cluster of unknown provenance is treated as the user's, because the coach
    does not overwrite what the user asked for and the cost is asymmetric:
    guessing wrong about the model loses a name the user chose."""
    return _source(cluster) is ClusterSource.Model


def _reuse(mine: list[dict], event_ids: list[int], used: set[str]) -> str | None:
    """The stored grouping this detection continues: the one sharing the most
    events. Keeping its id keeps what the coach already said about it pointing
    at something the record still holds."""
    best, shared = None, 0
    for cluster in mine:
        cluster_id = str(cluster["id"])
        if cluster_id in used:
            continue
        overlap = len(set(cluster.get("eventIds") or []) & set(event_ids))
        if overlap > shared:
            best, shared = cluster_id, overlap
    return best


def _detected(stored: list[dict], detected: list[Cluster], dates: dict) -> dict:
    """The model's grouping, with every event a grouping it may not touch owns
    held out, and each group carrying the id of the stored grouping it
    continues. A grouping that arrives under the minimum is a bug in whatever
    produced it and raises; one that only falls under it once the held-out
    events are taken out stays dots on the line."""
    mine = [c for c in stored if _regroupable(c)]
    theirs = {
        event_id
        for c in stored
        if not _regroupable(c)
        for event_id in c.get("eventIds") or []
    }
    taken = {str(c["id"]) for c in stored}
    kept: dict[str, Cluster] = {}
    for cluster in detected:
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Grouping {cluster.eventIds} arrived holding fewer than "
                f"{MIN_CLUSTER_EVENTS} events."
            )
        event_ids = [e for e in cluster.eventIds if e in dates and e not in theirs]
        if len(event_ids) < MIN_CLUSTER_EVENTS:
            continue
        cluster.eventIds = event_ids
        cluster.source = ClusterSource.Model
        cluster.name = cluster.name or cluster.title
        spanned = sorted(dates[e] for e in event_ids)
        cluster.startDate, cluster.endDate = spanned[0], spanned[-1]
        cluster.id = _reuse(mine, event_ids, set(kept)) or next_id(taken | set(kept))
        kept[cluster.id] = cluster
    return kept


def _deltas(stored: list[dict], detected: list[Cluster], dates: dict) -> list[dict]:
    stored = [c for c in stored if isinstance(c, dict) and c.get("id") is not None]
    mine = {str(c["id"]): c for c in stored if _regroupable(c)}
    kept = _detected(stored, detected, dates)

    deltas = [
        {
            "item_kind": ItemKind.Cluster.value,
            "item_id": cluster_id,
            "field": None,
            "after": None,
        }
        for cluster_id in mine
        if cluster_id not in kept
    ]
    for cluster_id, cluster in kept.items():
        was = mine.get(cluster_id, {})
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


def sync(
    diagram_id: int,
    *,
    turn_id: str,
    user_id: int | None = None,
    session_id: str | None = None,
):
    """Re-group the record's events and store the grouping.

    Clusters are stored, not derived on read, so the coach can point at one and
    have it still be there next turn. The rules make the groups; the model names
    them and says why. It never invents a member, and it never touches a cluster
    the user made — those events are held out of the detection and a model
    grouping that overlaps one yields the overlap to it.
    """
    diagram = db.session.get(Diagram, diagram_id)
    data = diagram.get_diagram_data()
    events = [
        from_dict(Event, chunk)
        for chunk in data.events
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]
    cache_key = compute_cache_key(events)
    if cache_key == data.clusterCacheKey:
        return None

    dates = {e.id: e.dateTime for e in events if e.dateTime}
    deltas = _deltas(data.clusters, detect_clusters(data).clusters, dates)
    deltas.append(
        {
            "item_kind": ItemKind.Diagram.value,
            "item_id": None,
            "field": "clusterCacheKey",
            "after": cache_key,
        }
    )
    return record.apply(
        diagram_id,
        deltas,
        author=Author.Coach,
        turn_id=turn_id,
        user_id=user_id,
        session_id=session_id,
    )
