import json
import logging
from dataclasses import dataclass, field

from btcopilot.extensions import db
from btcopilot.llmutil import gemini_structured_sync
from btcopilot.personal import record
from btcopilot.personal.models import Author
from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    Event,
    Cluster,
    ClusterPattern,
    ClusterResult,
    ClusterSource,
    ItemKind,
    asdict,
    from_dict,
    hash_sarf_dicts,
)

_log = logging.getLogger(__name__)

CLUSTER_PROMPT = """You are analyzing a behavioral health case timeline to identify clinically meaningful event clusters.

## SARF Theory Context

Four variables track family system dynamics:
- **S (Symptom)**: Physical/emotional dysfunction (sleep, mood, physical illness) - up=worsening, down=improving
- **A (Anxiety)**: Reactivity levels, "infectious" between people - up=more reactive
- **R (Relationship)**: Patterns like conflict, distance, toward, triangles (inside/outside positions)
- **F (Functioning)**: Differentiation of self - up=toward solid self, down=toward pseudo-self

**Clinical Hypothesis**: "S is modulated by R via A, and F is the clinical independent variable"

## Common SARF Patterns

- **anxiety_cascade**: A↑ → S↑ (anxiety leads to sleep/physical symptoms)
- **triangle_activation**: R: triangle → A↑ (positioning in triangles raises anxiety)
- **conflict_resolution**: R: conflict → processing → R: toward
- **reciprocal_disturbance**: One person's A/S triggers partner's A/S
- **functioning_gain**: Stressor → emotional processing → F↑
- **work_family_spillover**: Work A↑ cascades into family dynamics

## Events (chronological)

{events_json}

## Task

Group these events into clusters. Events belong in the same cluster when they:
1. *Required:* Occur in a relatively clustered time frame within the total timeseries. There is often gaps of weeks, months or years between clusters.
2. Form a narrative arc (trigger → escalation → peak → processing → resolution)
3. Optional: Show SARF interaction patterns (cascades, reciprocal effects)

**Outlier handling**:
- Birth events, childhood events, or other events that occur years/decades before the main timeline should be left unclustered unless they directly connect to a recent narrative arc
- Focus clustering on events that show clear temporal and thematic relationships

**Cluster sizing guidelines**:
- Short (1-6 days): Single incident or brief cascade
- Medium (1-2 weeks): Conflict-resolution arc
- Long (2-3 weeks): Major life event with processing
- Isolated events (1 day) can be their own cluster if significant

**Requirements**:
- **CRITICAL - Do not over-split clusters**: Events spanning a continuous date range (e.g., May 31 to June 4, or July 16 to July 21) MUST be in a single cluster, not split into multiple clusters. A "continuous range" means events where the largest gap between consecutive events is less than ~2 weeks. Err on the side of fewer, larger clusters rather than many small ones.
- Only include events in clusters when they form meaningful narrative arcs
- Events that are isolated outliers (e.g., birth events from decades before the main timeline) should NOT be forced into clusters
- Each event can belong to at most one cluster
- Use abstract titles (NO person names) - e.g., "Work Stress Cascade" not "Patrick's Work Stress"
- Set `pattern` to the primary SARF pattern if one is clearly dominant
- Set `dominantVariable` to "S", "A", "R", or "F" based on which is most prominent

Return a JSON object with a `clusters` array."""


@dataclass
class ClusterListResponse:
    clusters: list[Cluster] = field(default_factory=list)


def _enum_value(val):
    """Extract enum value or return as-is for non-enum types."""
    return val.value if hasattr(val, "value") else val


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
    return hash_sarf_dicts(event_data)


def detect_clusters(events: list[Event]) -> ClusterResult:
    if not events:
        return ClusterResult(clusters=[], cacheKey="empty")

    cache_key = compute_cache_key(events)

    events_for_prompt = []
    for e in events:
        event_dict = {
            "id": e.id,
            "date": e.dateTime,
            "description": e.description or "",
        }
        if e.symptom:
            event_dict["symptom"] = _enum_value(e.symptom)
        if e.anxiety:
            event_dict["anxiety"] = _enum_value(e.anxiety)
        if e.relationship:
            event_dict["relationship"] = _enum_value(e.relationship)
        if e.functioning:
            event_dict["functioning"] = _enum_value(e.functioning)
        if e.notes:
            event_dict["notes"] = e.notes
        events_for_prompt.append(event_dict)

    events_json = json.dumps(events_for_prompt, indent=2)
    prompt = CLUSTER_PROMPT.format(events_json=events_json)

    _log.info(f"Detecting clusters for {len(events)} events")

    response = gemini_structured_sync(prompt, ClusterListResponse)

    clusters = response.clusters if response else []

    for c in clusters:
        event_dates = [e.dateTime for e in events if e.id in c.eventIds and e.dateTime]
        if event_dates:
            c.startDate = min(event_dates)
            c.endDate = max(event_dates)

    _log.info(f"Detected {len(clusters)} clusters")

    return ClusterResult(clusters=clusters, cacheKey=cache_key)


STORED_FIELDS = (
    "title",
    "name",
    "summary",
    "eventIds",
    "startDate",
    "endDate",
    "pattern",
    "dominantVariable",
    "source",
)


def next_id(taken: set[str]) -> str:
    n = len(taken) + 1
    while f"c{n}" in taken:
        n += 1
    return f"c{n}"


def _source(cluster: dict) -> ClusterSource:
    return ClusterSource(cluster.get("source") or ClusterSource.Model.value)


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
    """The model's grouping, with every event a user cluster owns held out and
    each group carrying the id of the stored grouping it continues."""
    mine = [c for c in stored if _source(c) is ClusterSource.Model]
    theirs = {
        event_id
        for c in stored
        if _source(c) is ClusterSource.User
        for event_id in c.get("eventIds") or []
    }
    taken = {str(c["id"]) for c in stored}
    kept: dict[str, Cluster] = {}
    for cluster in detected:
        event_ids = [e for e in cluster.eventIds if e in dates and e not in theirs]
        if not event_ids:
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
    mine = {str(c["id"]): c for c in stored if _source(c) is ClusterSource.Model}
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
                "field": field,
                "after": now[field],
            }
            for field in STORED_FIELDS
            if now[field] != was.get(field)
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
    have it still be there next turn. The model groups and names; it never
    invents a member, and it never touches a cluster the user made — those
    events are held out of the detection and a model grouping that overlaps one
    yields the overlap to it.
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
    deltas = _deltas(data.clusters, detect_clusters(events).clusters, dates)
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
