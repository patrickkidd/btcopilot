"""
Analysis utilities for ground truth evaluation.

Extends f1_metrics.py to expose per-entity match details for UI rendering.
Used by the ground truth analysis views to show statement-level match breakdowns.
"""

import json
import logging
import pickle
from dataclasses import dataclass, field, asdict
from typing import Any

from flask import current_app, has_app_context

from btcopilot.schema import Person, Event, PDPDeltas, from_dict

# Cache configuration
CACHE_ENABLED = False  # Set to True to enable Redis caching
CACHE_TTL = 3600  # 1 hour TTL

_redis_client = None
_redis_checked = False


def _get_redis():
    """Lazy-load Redis client from Celery broker URL"""
    global _redis_client, _redis_checked
    if not _redis_checked:
        _redis_checked = True
        try:
            import redis

            broker_url = "redis://localhost:6379/0"
            if has_app_context():
                broker_url = current_app.config.get("CELERY_BROKER_URL", broker_url)
            client = redis.from_url(broker_url)
            client.ping()
            _redis_client = client
        except Exception as e:
            _log.warning(f"Redis unavailable for caching: {e}")
            _redis_client = None
    return _redis_client


def _cache_key(statement_id: int) -> str:
    """Generate cache key for statement breakdown"""
    return f"analysis:breakdown:v1:{statement_id}"


def _get_cached_breakdown(statement_id: int):
    """Get cached breakdown from Redis, returns None if not found or cache disabled"""
    if not CACHE_ENABLED:
        return None
    client = _get_redis()
    if not client:
        return None
    try:
        data = client.get(_cache_key(statement_id))
        if data:
            return pickle.loads(data)
    except Exception as e:
        _log.warning(f"Cache read error for statement {statement_id}: {e}")
    return None


def _set_cached_breakdown(statement_id: int, breakdown):
    """Store breakdown in Redis cache"""
    if not CACHE_ENABLED:
        return
    client = _get_redis()
    if not client:
        return
    try:
        client.setex(_cache_key(statement_id), CACHE_TTL, pickle.dumps(breakdown))
    except Exception as e:
        _log.warning(f"Cache write error for statement {statement_id}: {e}")


def invalidate_breakdown_cache(statement_id: int):
    """Invalidate cached breakdown for a statement (call when feedback changes)"""
    client = _get_redis()
    if client:
        try:
            client.delete(_cache_key(statement_id))
        except Exception as e:
            _log.warning(f"Cache invalidate error for statement {statement_id}: {e}")


def invalidate_discussion_cache(discussion_id: int):
    """Invalidate all cached breakdowns for a discussion"""
    from btcopilot.personal.models import Statement

    client = _get_redis()
    if not client:
        return
    try:
        statement_ids = [
            s.id for s in Statement.query.filter_by(discussion_id=discussion_id).all()
        ]
        keys = [_cache_key(sid) for sid in statement_ids]
        if keys:
            client.delete(*keys)
    except Exception as e:
        _log.warning(f"Cache invalidate error for discussion {discussion_id}: {e}")


from btcopilot.training.f1_metrics import (
    match_people,
    match_events,
    match_pair_bonds,
    calculate_statement_f1,
    StatementF1Metrics,
    resolve_person_id,
    resolve_person_list,
)

_log = logging.getLogger(__name__)


@dataclass
class EntityMatchDetail:
    """Detailed match info for single entity (person/event/pair_bond)"""

    entity_type: str
    match_type: str
    ai_entity: dict | None
    gt_entity: dict | None
    match_score: float = 0.0
    mismatch_reasons: list[str] = field(default_factory=list)


@dataclass
class SARFMatchDetail:
    """Per-SARF-variable hierarchical match breakdown"""

    variable_name: str
    person_id: int
    person_name: str
    detection_match: str
    value_match: str | None = None
    people_match: str | None = None
    ai_value: str | None = None
    gt_value: str | None = None
    ai_people: list[str] = field(default_factory=list)
    gt_people: list[str] = field(default_factory=list)


@dataclass
class StatementMatchBreakdown:
    """Complete match breakdown for single statement"""

    statement_id: int
    people_matches: list[EntityMatchDetail]
    event_matches: list[EntityMatchDetail]
    pair_bond_matches: list[EntityMatchDetail]
    sarf_matches: list[SARFMatchDetail]
    f1_metrics: StatementF1Metrics


def _entity_to_dict(entity: Any) -> dict:
    if entity is None:
        return None
    return asdict(entity)


def _get_person_name_by_id(person_id: int, people: list[Person]) -> str:
    for person in people:
        if person.id == person_id:
            name = person.name or ""
            if person.last_name:
                name += f" {person.last_name}"
            return name.strip() or f"Person {person_id}"
    return f"Person {person_id}"


def _extract_sarf_matches(
    ai_events: list[Event],
    gt_events: list[Event],
    id_map: dict[int, int],
    ai_people: list[Person],
    gt_people: list[Person],
) -> list[SARFMatchDetail]:
    """
    Extract SARF-level matches for UI display.

    Returns list of SARFMatchDetail showing per-person, per-variable detection/value/people matches.
    """
    sarf_vars = ["symptom", "anxiety", "relationship", "functioning"]
    sarf_matches = []

    for var_name in sarf_vars:
        ai_person_var_data = {}
        gt_person_var_data = {}

        for ai_event in ai_events:
            var_value = getattr(ai_event, var_name)
            if var_value is None:
                continue

            person_id = resolve_person_id(ai_event.person, id_map)
            # Use sentinel 0 for events without person assignment
            if person_id is None:
                person_id = 0

            if person_id not in ai_person_var_data:
                ai_person_var_data[person_id] = {"values": set(), "people": set()}

            ai_person_var_data[person_id]["values"].add(str(var_value))

            if var_name == "relationship":
                targets = resolve_person_list(
                    ai_event.relationshipTargets or [], id_map
                )
                triangles = resolve_person_list(
                    ai_event.relationshipTriangles or [], id_map
                )
                target_names = [
                    _get_person_name_by_id(pid, gt_people) for pid in targets
                ]
                triangle_names = [
                    _get_person_name_by_id(pid, gt_people) for pid in triangles
                ]
                ai_person_var_data[person_id]["people"].add(
                    (tuple(sorted(target_names)), tuple(sorted(triangle_names)))
                )

        for gt_event in gt_events:
            var_value = getattr(gt_event, var_name)
            if var_value is None:
                continue

            person_id = gt_event.person
            # Use sentinel 0 for events without person assignment
            if person_id is None:
                person_id = 0

            if person_id not in gt_person_var_data:
                gt_person_var_data[person_id] = {"values": set(), "people": set()}

            gt_person_var_data[person_id]["values"].add(str(var_value))

            if var_name == "relationship":
                targets = gt_event.relationshipTargets or []
                triangles = gt_event.relationshipTriangles or []
                target_names = [
                    _get_person_name_by_id(pid, gt_people) for pid in targets
                ]
                triangle_names = [
                    _get_person_name_by_id(pid, gt_people) for pid in triangles
                ]
                gt_person_var_data[person_id]["people"].add(
                    (tuple(sorted(target_names)), tuple(sorted(triangle_names)))
                )

        all_person_ids = set(ai_person_var_data.keys()) | set(gt_person_var_data.keys())

        for person_id in all_person_ids:
            ai_data = ai_person_var_data.get(
                person_id, {"values": set(), "people": set()}
            )
            gt_data = gt_person_var_data.get(
                person_id, {"values": set(), "people": set()}
            )

            has_ai = bool(ai_data["values"])
            has_gt = bool(gt_data["values"])

            if has_ai and has_gt:
                detection_match = "TP"
            elif has_ai and not has_gt:
                detection_match = "FP"
            elif not has_ai and has_gt:
                detection_match = "FN"
            else:
                detection_match = "TN"

            value_match = None
            if has_ai and has_gt:
                if ai_data["values"] & gt_data["values"]:
                    value_match = "match"
                else:
                    value_match = "mismatch"

            people_match = None
            if var_name == "relationship" and has_ai and has_gt:
                if ai_data["people"] & gt_data["people"]:
                    people_match = "match"
                else:
                    people_match = "mismatch"

            if person_id == 0:
                person_name = "(Unassigned)"
            else:
                person_name = _get_person_name_by_id(person_id, gt_people)
            ai_value = (
                ", ".join(sorted(ai_data["values"])) if ai_data["values"] else None
            )
            gt_value = (
                ", ".join(sorted(gt_data["values"])) if gt_data["values"] else None
            )

            ai_people_list = []
            gt_people_list = []
            if var_name == "relationship":
                for targets, triangles in ai_data["people"]:
                    ai_people_list.extend(targets)
                    ai_people_list.extend(triangles)
                for targets, triangles in gt_data["people"]:
                    gt_people_list.extend(targets)
                    gt_people_list.extend(triangles)

            sarf_matches.append(
                SARFMatchDetail(
                    variable_name=var_name,
                    person_id=person_id,
                    person_name=person_name,
                    detection_match=detection_match,
                    value_match=value_match,
                    people_match=people_match,
                    ai_value=ai_value,
                    gt_value=gt_value,
                    ai_people=sorted(set(ai_people_list)),
                    gt_people=sorted(set(gt_people_list)),
                )
            )

    return sarf_matches


def calculate_statement_match_breakdown(
    statement_id: int,
) -> StatementMatchBreakdown | None:
    """
    Calculate detailed match breakdown for single statement.

    Returns None if:
    - Statement has no feedback with edited_extraction (no ground truth)
    - Statement.pdp_deltas is None

    Results are cached in Redis (if CACHE_ENABLED=True) to avoid recomputation.
    Cache is invalidated when feedback changes via invalidate_breakdown_cache().
    """
    # Check Redis cache first
    cached = _get_cached_breakdown(statement_id)
    if cached is not None:
        return cached

    from btcopilot.training.models import Feedback
    from btcopilot.personal.models import Statement, Discussion
    from btcopilot.pdp import cumulative

    statement = Statement.query.get(statement_id)
    if not statement or not statement.pdp_deltas:
        return None

    feedback = Feedback.query.filter(
        Feedback.statement_id == statement_id,
        Feedback.feedback_type == "extraction",
        Feedback.approved == True,
    ).first()

    if not feedback or not feedback.edited_extraction:
        return None

    ai_pdp = from_dict(PDPDeltas, statement.pdp_deltas)
    gt_pdp = from_dict(PDPDeltas, feedback.edited_extraction)

    # Get cumulative PDPDeltas up to THIS statement for AI name resolution
    discussion = Discussion.query.get(statement.discussion_id)
    cumulative_pdp = cumulative(discussion, statement)

    # Build cumulative GT people list from all feedback entries in order
    # Fetch all feedbacks for this discussion in one query (avoid N+1)
    all_statements = (
        Statement.query.filter_by(discussion_id=statement.discussion_id)
        .order_by(Statement.order)
        .all()
    )
    statement_ids = [s.id for s in all_statements]
    feedbacks_by_stmt = {
        f.statement_id: f
        for f in Feedback.query.filter(
            Feedback.statement_id.in_(statement_ids),
            Feedback.feedback_type == "extraction",
        ).all()
    }

    gt_cumulative_people = []
    for stmt in all_statements:
        stmt_feedback = feedbacks_by_stmt.get(stmt.id)
        if stmt_feedback and stmt_feedback.edited_extraction:
            stmt_gt_pdp = from_dict(PDPDeltas, stmt_feedback.edited_extraction)
            for person in stmt_gt_pdp.people:
                existing_person = next(
                    (p for p in gt_cumulative_people if p.id == person.id), None
                )
                if existing_person:
                    gt_cumulative_people[
                        gt_cumulative_people.index(existing_person)
                    ] = person
                else:
                    gt_cumulative_people.append(person)
        # Stop after current statement to get names as-of this point
        if stmt.id == statement_id:
            break

    f1_metrics = calculate_statement_f1(
        statement.pdp_deltas, feedback.edited_extraction
    )
    f1_metrics.statement_id = statement_id

    people_result, id_map = match_people(ai_pdp.people, gt_pdp.people)
    events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
    bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

    people_matches = []
    for ai_person, gt_person in people_result.matched_pairs:
        people_matches.append(
            EntityMatchDetail(
                entity_type="person",
                match_type="TP",
                ai_entity=_entity_to_dict(ai_person),
                gt_entity=_entity_to_dict(gt_person),
                match_score=1.0,
                mismatch_reasons=[],
            )
        )

    for ai_person in people_result.ai_unmatched:
        people_matches.append(
            EntityMatchDetail(
                entity_type="person",
                match_type="FP",
                ai_entity=_entity_to_dict(ai_person),
                gt_entity=None,
                match_score=0.0,
                mismatch_reasons=["AI hallucinated person not in ground truth"],
            )
        )

    for gt_person in people_result.gt_unmatched:
        people_matches.append(
            EntityMatchDetail(
                entity_type="person",
                match_type="FN",
                ai_entity=None,
                gt_entity=_entity_to_dict(gt_person),
                match_score=0.0,
                mismatch_reasons=["AI missed person present in ground truth"],
            )
        )

    event_matches = []
    for ai_event, gt_event in events_result.matched_pairs:
        event_matches.append(
            EntityMatchDetail(
                entity_type="event",
                match_type="TP",
                ai_entity=_entity_to_dict(ai_event),
                gt_entity=_entity_to_dict(gt_event),
                match_score=1.0,
                mismatch_reasons=[],
            )
        )

    for ai_event in events_result.ai_unmatched:
        event_matches.append(
            EntityMatchDetail(
                entity_type="event",
                match_type="FP",
                ai_entity=_entity_to_dict(ai_event),
                gt_entity=None,
                match_score=0.0,
                mismatch_reasons=["AI hallucinated event not in ground truth"],
            )
        )

    for gt_event in events_result.gt_unmatched:
        event_matches.append(
            EntityMatchDetail(
                entity_type="event",
                match_type="FN",
                ai_entity=None,
                gt_entity=_entity_to_dict(gt_event),
                match_score=0.0,
                mismatch_reasons=["AI missed event present in ground truth"],
            )
        )

    pair_bond_matches = []
    for ai_bond, gt_bond in bonds_result.matched_pairs:
        pair_bond_matches.append(
            EntityMatchDetail(
                entity_type="pair_bond",
                match_type="TP",
                ai_entity=_entity_to_dict(ai_bond),
                gt_entity=_entity_to_dict(gt_bond),
                match_score=1.0,
                mismatch_reasons=[],
            )
        )

    for ai_bond in bonds_result.ai_unmatched:
        pair_bond_matches.append(
            EntityMatchDetail(
                entity_type="pair_bond",
                match_type="FP",
                ai_entity=_entity_to_dict(ai_bond),
                gt_entity=None,
                match_score=0.0,
                mismatch_reasons=["AI hallucinated pair bond not in ground truth"],
            )
        )

    for gt_bond in bonds_result.gt_unmatched:
        pair_bond_matches.append(
            EntityMatchDetail(
                entity_type="pair_bond",
                match_type="FN",
                ai_entity=None,
                gt_entity=_entity_to_dict(gt_bond),
                match_score=0.0,
                mismatch_reasons=["AI missed pair bond present in ground truth"],
            )
        )

    sarf_matches = _extract_sarf_matches(
        ai_pdp.events, gt_pdp.events, id_map, ai_pdp.people, gt_cumulative_people
    )

    breakdown = StatementMatchBreakdown(
        statement_id=statement_id,
        people_matches=people_matches,
        event_matches=event_matches,
        pair_bond_matches=pair_bond_matches,
        sarf_matches=sarf_matches,
        f1_metrics=f1_metrics,
    )

    # Store people lists for display preprocessing
    # AI side uses cumulative AI people, GT side uses cumulative GT people from feedback
    breakdown.ai_people = cumulative_pdp.people
    breakdown.gt_people = gt_cumulative_people

    # Cache in Redis
    _set_cached_breakdown(statement_id, breakdown)

    return breakdown
