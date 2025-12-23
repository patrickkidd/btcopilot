"""
F1 Metrics Calculation for AI Data Extraction vs Ground Truth

This module calculates F1 scores comparing AI-generated codes (Statement.pdp_deltas)
to human ground truth codes (Feedback.edited_extraction).

Matching Logic:
- People: Fuzzy name matching (token_set_ratio >= 0.6) after stripping titles
          (Aunt, Uncle, Dr., etc.) AND parents match (ignore if null) AND
          gender match (ignore if either is None/Unknown).
          "Aunt Carol" matches "Carol", "Dr. Smith" matches "Smith".
- Events: kind exact + description similarity > 0.5 (80% weight) + date proximity (20% weight, None matches any) + links match
- PairBonds: person_a/person_b match resolved IDs
- SARF variables: Macro-F1 across matched events (exact enum match)
- IDs ignored: Match purely by content, not IDs

F1 Metrics:
1. Aggregate Micro-F1: Pool all entities (People + Events + PairBonds)
2. Per-Type Micro-F1: Separate F1 for People, Events, PairBonds
3. Enum Macro-F1: For each SARF variable across matched events
4. Exact Match Rate: Binary (1 if entire PDP exact JSON match after ID normalization)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser
import re

from rapidfuzz import fuzz
from sklearn.metrics import f1_score

from btcopilot.schema import (
    Person,
    Event,
    PairBond,
    PDPDeltas,
    DateCertainty,
    PersonKind,
    from_dict,
)

_log = logging.getLogger(__name__)

_f1_cache = {}
_f1_cache_time = {}

NAME_SIMILARITY_THRESHOLD = 0.60

TITLE_PREFIXES = frozenset(
    [
        "aunt",
        "uncle",
        "dr",
        "dr.",
        "mr",
        "mr.",
        "mrs",
        "mrs.",
        "ms",
        "ms.",
        "miss",
        "sir",
        "madam",
        "grandma",
        "grandpa",
        "grandmother",
        "grandfather",
        "granny",
        "grammy",
        "grandad",
        "granddad",
        "nana",
        "papa",
        "pop",
        "mom",
        "dad",
        "mother",
        "father",
        "brother",
        "sister",
        "cousin",
        "nephew",
        "niece",
    ]
)


def normalize_name_for_matching(name: str | None) -> str:
    """
    Normalize a person's name for fuzzy matching.

    Strips titles like "Aunt", "Uncle", "Dr.", etc. and normalizes whitespace.
    """
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    words = name.split()
    while words and words[0] in TITLE_PREFIXES:
        words.pop(0)
    return " ".join(words)


DESCRIPTION_SIMILARITY_THRESHOLD = 0.4
DATE_TOLERANCE_DAYS = 7
APPROXIMATE_TOLERANCE_DAYS = 270  # ±9 months
DESCRIPTION_WEIGHT = 0.8
DATE_WEIGHT = 0.2


@dataclass
class EntityMatchResult:
    matched_pairs: list[tuple[Any, Any]] = field(default_factory=list)
    ai_unmatched: list[Any] = field(default_factory=list)
    gt_unmatched: list[Any] = field(default_factory=list)


@dataclass
class F1Metrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class SARFVariableF1:
    detection_f1: float = 0.0
    value_match_f1: float = 0.0
    people_match_f1: float = 0.0


@dataclass
class StatementF1Metrics:
    statement_id: int
    aggregate_micro_f1: float = 0.0
    people_f1: float = 0.0
    events_f1: float = 0.0
    pair_bonds_f1: float = 0.0
    symptom_macro_f1: float = 0.0
    anxiety_macro_f1: float = 0.0
    relationship_macro_f1: float = 0.0
    functioning_macro_f1: float = 0.0
    symptom_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    anxiety_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    relationship_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    functioning_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    exact_match: bool = False
    aggregate_tp: int = 0
    aggregate_fp: int = 0
    aggregate_fn: int = 0
    people_metrics: F1Metrics = field(default_factory=F1Metrics)
    events_metrics: F1Metrics = field(default_factory=F1Metrics)
    pair_bonds_metrics: F1Metrics = field(default_factory=F1Metrics)


@dataclass
class SystemF1Metrics:
    aggregate_micro_f1: float = 0.0
    people_f1: float = 0.0
    events_f1: float = 0.0
    pair_bonds_f1: float = 0.0
    symptom_macro_f1: float = 0.0
    anxiety_macro_f1: float = 0.0
    relationship_macro_f1: float = 0.0
    functioning_macro_f1: float = 0.0
    symptom_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    anxiety_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    relationship_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    functioning_hierarchical: SARFVariableF1 = field(default_factory=SARFVariableF1)
    exact_match_rate: float = 0.0
    total_statements: int = 0
    total_discussions: int = 0


def parse_date_flexible(date_str: str | None) -> datetime | None:
    """Parse date string flexibly, handling vague dates gracefully"""
    if not date_str:
        return None
    try:
        return date_parser.parse(date_str, fuzzy=True)
    except (ValueError, TypeError):
        return None


def dates_within_tolerance(
    date1: str | datetime | None,
    date2: str | datetime | None,
    certainty1: DateCertainty | None = None,
    certainty2: DateCertainty | None = None,
) -> bool:
    """
    Check if two dates are within tolerance based on certainty levels.

    Tolerance is determined by the LEAST certain date:
    - If either is Unknown: always matches
    - If either is Approximate: ±365 days
    - Both Certain or None: ±7 days (current behavior)
    """
    c1 = certainty1 or DateCertainty.Certain
    c2 = certainty2 or DateCertainty.Certain

    if c1 == DateCertainty.Unknown or c2 == DateCertainty.Unknown:
        return True

    dt1 = date1 if isinstance(date1, datetime) else parse_date_flexible(date1)
    dt2 = date2 if isinstance(date2, datetime) else parse_date_flexible(date2)

    if dt1 is None or dt2 is None:
        return True

    if c1 == DateCertainty.Approximate or c2 == DateCertainty.Approximate:
        tolerance = APPROXIMATE_TOLERANCE_DAYS
    else:
        tolerance = DATE_TOLERANCE_DAYS

    delta = abs((dt1 - dt2).days)
    return delta <= tolerance


def calculate_date_similarity(
    date1: str | datetime | None,
    date2: str | datetime | None,
    certainty1: DateCertainty | None = None,
    certainty2: DateCertainty | None = None,
) -> float:
    """
    Calculate date similarity score (0.0 to 1.0) considering certainty.

    Tolerance is determined by the LEAST certain date:
    - If either is Unknown: returns 1.0
    - If either is Approximate: use 365-day tolerance
    - Both Certain or None: use 7-day tolerance
    """
    c1 = certainty1 or DateCertainty.Certain
    c2 = certainty2 or DateCertainty.Certain

    if c1 == DateCertainty.Unknown or c2 == DateCertainty.Unknown:
        return 1.0

    dt1 = date1 if isinstance(date1, datetime) else parse_date_flexible(date1)
    dt2 = date2 if isinstance(date2, datetime) else parse_date_flexible(date2)

    if dt1 is None or dt2 is None:
        return 1.0

    if c1 == DateCertainty.Approximate or c2 == DateCertainty.Approximate:
        tolerance = APPROXIMATE_TOLERANCE_DAYS
    else:
        tolerance = DATE_TOLERANCE_DAYS

    delta_days = abs((dt1 - dt2).days)
    if delta_days == 0:
        return 1.0
    elif delta_days <= tolerance:
        return 1.0 - (delta_days / (tolerance * 2))
    else:
        return 0.0


def match_people(
    ai_people: list[Person], gt_people: list[Person]
) -> tuple[EntityMatchResult, dict[int, int]]:
    """
    Match people by name similarity, parent matching, and gender matching.

    Returns:
        EntityMatchResult: matched pairs, unmatched AI, unmatched GT
        dict[int, int]: ID mapping from AI person IDs to GT person IDs
    """
    result = EntityMatchResult()
    id_map = {}

    gt_remaining = list(gt_people)
    ai_processed = set()

    for ai_person in ai_people:
        best_match = None
        best_score = 0.0

        for gt_person in gt_remaining:
            ai_name_normalized = normalize_name_for_matching(ai_person.name)
            gt_name_normalized = normalize_name_for_matching(gt_person.name)

            name_sim = (
                fuzz.token_set_ratio(ai_name_normalized, gt_name_normalized) / 100.0
            )

            if name_sim < NAME_SIMILARITY_THRESHOLD:
                continue

            parents_match = True
            if ai_person.parents is not None and gt_person.parents is not None:
                resolved_ai_parents = [id_map.get(p, p) for p in ai_person.parents]
                if set(resolved_ai_parents) != set(gt_person.parents):
                    parents_match = False

            # Gender must match if both are set (ignore if either is None/Unknown)
            gender_match = True
            if ai_person.gender is not None and gt_person.gender is not None:
                if (
                    ai_person.gender != PersonKind.Unknown
                    and gt_person.gender != PersonKind.Unknown
                ):
                    gender_match = ai_person.gender == gt_person.gender

            if parents_match and gender_match and name_sim > best_score:
                best_score = name_sim
                best_match = gt_person

        if best_match:
            result.matched_pairs.append((ai_person, best_match))
            id_map[ai_person.id] = best_match.id
            gt_remaining.remove(best_match)
            ai_processed.add(ai_person.id)

    result.ai_unmatched = [p for p in ai_people if p.id not in ai_processed]
    result.gt_unmatched = gt_remaining

    return result, id_map


def resolve_person_id(person_id: int | None, id_map: dict[int, int]) -> int | None:
    if person_id is None:
        return None
    return id_map.get(person_id, person_id)


def resolve_person_list(person_ids: list[int], id_map: dict[int, int]) -> list[int]:
    return [resolve_person_id(pid, id_map) for pid in person_ids if pid is not None]


def match_events(
    ai_events: list[Event], gt_events: list[Event], id_map: dict[int, int]
) -> EntityMatchResult:
    """
    Match events by kind, description similarity (80% weight), date proximity (20% weight), and link matching.

    Matching criteria:
    - kind must match exactly
    - description similarity >= 0.5 threshold
    - date within tolerance (None matches any date)
    - links must match after ID resolution
    - Overall score = 0.8 * desc_sim + 0.2 * date_sim

    Args:
        id_map: Mapping from AI person IDs to GT person IDs
    """
    result = EntityMatchResult()

    gt_remaining = list(gt_events)
    ai_processed = set()

    for ai_event in ai_events:
        best_match = None
        best_score = 0.0

        for gt_event in gt_remaining:
            if ai_event.kind != gt_event.kind:
                continue

            desc_sim = (
                fuzz.ratio(
                    (ai_event.description or "").lower(),
                    (gt_event.description or "").lower(),
                )
                / 100.0
            )

            if desc_sim < DESCRIPTION_SIMILARITY_THRESHOLD:
                continue

            if not dates_within_tolerance(
                ai_event.dateTime,
                gt_event.dateTime,
                ai_event.dateCertainty,
                gt_event.dateCertainty,
            ):
                continue

            ai_person = resolve_person_id(ai_event.person, id_map)
            ai_spouse = resolve_person_id(ai_event.spouse, id_map)
            ai_child = resolve_person_id(ai_event.child, id_map)
            ai_targets = resolve_person_list(ai_event.relationshipTargets, id_map)
            ai_triangles = resolve_person_list(ai_event.relationshipTriangles, id_map)

            links_match = (
                ai_person == gt_event.person
                and ai_spouse == gt_event.spouse
                and ai_child == gt_event.child
                and set(ai_targets) == set(gt_event.relationshipTargets or [])
                and set(ai_triangles) == set(gt_event.relationshipTriangles or [])
            )

            if links_match:
                date_sim = calculate_date_similarity(
                    ai_event.dateTime,
                    gt_event.dateTime,
                    ai_event.dateCertainty,
                    gt_event.dateCertainty,
                )
                weighted_score = (DESCRIPTION_WEIGHT * desc_sim) + (
                    DATE_WEIGHT * date_sim
                )

                if weighted_score > best_score:
                    best_score = weighted_score
                    best_match = gt_event

        if best_match:
            result.matched_pairs.append((ai_event, best_match))
            gt_remaining.remove(best_match)
            ai_processed.add(ai_event.id)

    result.ai_unmatched = [e for e in ai_events if e.id not in ai_processed]
    result.gt_unmatched = gt_remaining

    return result


def match_pair_bonds(
    ai_bonds: list[PairBond], gt_bonds: list[PairBond], id_map: dict[int, int]
) -> EntityMatchResult:
    result = EntityMatchResult()

    gt_remaining = list(gt_bonds)
    ai_processed = set()

    for ai_bond in ai_bonds:
        ai_person_a = resolve_person_id(ai_bond.person_a, id_map)
        ai_person_b = resolve_person_id(ai_bond.person_b, id_map)

        for gt_bond in gt_remaining:
            if (
                ai_person_a == gt_bond.person_a and ai_person_b == gt_bond.person_b
            ) or (ai_person_a == gt_bond.person_b and ai_person_b == gt_bond.person_a):
                result.matched_pairs.append((ai_bond, gt_bond))
                gt_remaining.remove(gt_bond)
                ai_processed.add(id(ai_bond))
                break

    result.ai_unmatched = [b for b in ai_bonds if id(b) not in ai_processed]
    result.gt_unmatched = gt_remaining

    return result


def calculate_f1_from_counts(tp: int, fp: int, fn: int) -> F1Metrics:
    metrics = F1Metrics(tp=tp, fp=fp, fn=fn)

    if tp == 0 and fp == 0 and fn == 0:
        metrics.precision = 1.0
        metrics.recall = 1.0
        metrics.f1 = 1.0
        return metrics

    if tp + fp > 0:
        metrics.precision = tp / (tp + fp)
    else:
        metrics.precision = 0.0

    if tp + fn > 0:
        metrics.recall = tp / (tp + fn)
    else:
        metrics.recall = 0.0

    if metrics.precision + metrics.recall > 0:
        metrics.f1 = (
            2
            * (metrics.precision * metrics.recall)
            / (metrics.precision + metrics.recall)
        )
    else:
        metrics.f1 = 0.0

    return metrics


def calculate_sarf_macro_f1(
    matched_event_pairs: list[tuple[Event, Event]],
) -> dict[str, float]:
    """
    Calculate macro-F1 for SARF variables across matched events.

    For each SARF variable, calculate F1 and then average (macro-average).
    """
    sarf_vars = ["symptom", "anxiety", "relationship", "functioning"]
    f1_scores = {}

    for var_name in sarf_vars:
        ai_values = []
        gt_values = []

        for ai_event, gt_event in matched_event_pairs:
            ai_val = getattr(ai_event, var_name)
            gt_val = getattr(gt_event, var_name)

            ai_str = str(ai_val) if ai_val is not None else "none"
            gt_str = str(gt_val) if gt_val is not None else "none"

            ai_values.append(ai_str)
            gt_values.append(gt_str)

        if not ai_values:
            f1_scores[var_name] = 0.0
            continue

        try:
            f1 = f1_score(gt_values, ai_values, average="macro", zero_division=0.0)
            f1_scores[var_name] = float(f1)
        except (ValueError, ZeroDivisionError):
            f1_scores[var_name] = 0.0

    return f1_scores


def calculate_hierarchical_sarf_f1(
    ai_events: list[Event], gt_events: list[Event], id_map: dict[int, int]
) -> dict[str, SARFVariableF1]:
    """
    Calculate hierarchical F1 metrics for SARF variables.

    For each variable, calculates:
    A) Detection F1: Was any event detected for (person, variable)?
    B) Value Match F1: For detected events, was the exact value correct?
    C) People Match F1 (R only): For relationship events, were the right people detected?

    Args:
        ai_events: AI-detected events
        gt_events: Ground truth events
        id_map: Person ID mapping from AI to GT

    Returns:
        dict mapping variable names to SARFVariableF1 metrics
    """
    sarf_vars = ["symptom", "anxiety", "relationship", "functioning"]
    hierarchical_metrics = {}

    for var_name in sarf_vars:
        ai_person_var_pairs = set()
        gt_person_var_pairs = set()
        ai_person_var_values = {}
        gt_person_var_values = {}
        ai_person_var_people = {}
        gt_person_var_people = {}

        for ai_event in ai_events:
            var_value = getattr(ai_event, var_name)
            if var_value is None:
                continue

            person_id = resolve_person_id(ai_event.person, id_map)
            if person_id is None:
                continue

            pair = (person_id, var_name)
            ai_person_var_pairs.add(pair)

            if pair not in ai_person_var_values:
                ai_person_var_values[pair] = set()
            ai_person_var_values[pair].add(str(var_value))

            if var_name == "relationship":
                targets = resolve_person_list(
                    ai_event.relationshipTargets or [], id_map
                )
                triangles = resolve_person_list(
                    ai_event.relationshipTriangles or [], id_map
                )
                if pair not in ai_person_var_people:
                    ai_person_var_people[pair] = set()
                ai_person_var_people[pair].add(
                    (frozenset(targets), frozenset(triangles))
                )

        for gt_event in gt_events:
            var_value = getattr(gt_event, var_name)
            if var_value is None:
                continue

            person_id = gt_event.person
            if person_id is None:
                continue

            pair = (person_id, var_name)
            gt_person_var_pairs.add(pair)

            if pair not in gt_person_var_values:
                gt_person_var_values[pair] = set()
            gt_person_var_values[pair].add(str(var_value))

            if var_name == "relationship":
                targets = set(gt_event.relationshipTargets or [])
                triangles = set(gt_event.relationshipTriangles or [])
                if pair not in gt_person_var_people:
                    gt_person_var_people[pair] = set()
                gt_person_var_people[pair].add(
                    (frozenset(targets), frozenset(triangles))
                )

        detection_tp = len(ai_person_var_pairs & gt_person_var_pairs)
        detection_fp = len(ai_person_var_pairs - gt_person_var_pairs)
        detection_fn = len(gt_person_var_pairs - ai_person_var_pairs)

        detection_metrics = calculate_f1_from_counts(
            detection_tp, detection_fp, detection_fn
        )

        detected_pairs = ai_person_var_pairs & gt_person_var_pairs
        value_tp = sum(
            1
            for pair in detected_pairs
            if ai_person_var_values.get(pair, set())
            & gt_person_var_values.get(pair, set())
        )
        value_fp = len(detected_pairs) - value_tp
        value_fn = 0

        value_metrics = calculate_f1_from_counts(value_tp, value_fp, value_fn)

        people_metrics = F1Metrics(precision=1.0, recall=1.0, f1=1.0)
        if var_name == "relationship" and detected_pairs:
            people_tp = sum(
                1
                for pair in detected_pairs
                if ai_person_var_people.get(pair, set())
                & gt_person_var_people.get(pair, set())
            )
            people_fp = len(detected_pairs) - people_tp
            people_fn = 0
            people_metrics = calculate_f1_from_counts(people_tp, people_fp, people_fn)

        hierarchical_metrics[var_name] = SARFVariableF1(
            detection_f1=detection_metrics.f1,
            value_match_f1=value_metrics.f1,
            people_match_f1=people_metrics.f1,
        )

    return hierarchical_metrics


def normalize_pdp_for_comparison(pdp_dict: dict | PDPDeltas) -> dict:
    """
    Normalize PDP dict for exact match comparison.

    - Sort entities by kind/name
    - Renumber IDs sequentially
    - Remove confidence fields
    - Handle both "parents" and "parent_a"/"parent_b" formats
    """
    # Convert PDPDeltas to dict if needed
    if isinstance(pdp_dict, PDPDeltas):
        pdp_dict = asdict(pdp_dict)

    normalized = {
        "people": [],
        "events": [],
        "pair_bonds": [],
        "delete": sorted(pdp_dict.get("delete", [])),
    }

    people = pdp_dict.get("people", [])
    people_sorted = sorted(
        people, key=lambda p: (p.get("name") or "", p.get("last_name") or "")
    )

    id_map = {}
    for i, person in enumerate(people_sorted):
        new_id = i + 1
        old_id = person.get("id")
        if old_id is not None:
            id_map[old_id] = new_id

    for i, person in enumerate(people_sorted):
        new_id = i + 1

        if "parents" in person and isinstance(person.get("parents"), list):
            parents = person.get("parents", [])
            parent_a = parents[0] if len(parents) > 0 else None
            parent_b = parents[1] if len(parents) > 1 else None
        else:
            parent_a = person.get("parent_a")
            parent_b = person.get("parent_b")

        parent_ids = [id_map.get(p, p) for p in [parent_a, parent_b] if p is not None]
        gender = person.get("gender")
        if gender is not None:
            gender = str(gender)
        normalized["people"].append(
            {
                "id": new_id,
                "name": person.get("name"),
                "last_name": person.get("last_name"),
                "gender": gender,
                "parents": [p for p in parent_ids if p is not None],
            }
        )

    events = pdp_dict.get("events", [])

    def event_sort_key(e):
        dt = e.get("dateTime")
        if isinstance(dt, datetime):
            dt = dt.isoformat()
        elif dt is None:
            dt = ""
        return (str(e.get("kind")), e.get("description") or "", dt)

    events_sorted = sorted(events, key=event_sort_key)

    for i, event in enumerate(events_sorted):
        new_id = i + 1
        person_id = event.get("person")
        spouse_id = event.get("spouse")
        child_id = event.get("child")

        dateTime = event.get("dateTime")
        if isinstance(dateTime, datetime):
            dateTime = dateTime.isoformat()

        endDateTime = event.get("endDateTime")
        if isinstance(endDateTime, datetime):
            endDateTime = endDateTime.isoformat()

        normalized["events"].append(
            {
                "id": new_id,
                "kind": str(event.get("kind")),
                "person": id_map.get(person_id) if person_id is not None else None,
                "spouse": id_map.get(spouse_id) if spouse_id is not None else None,
                "child": id_map.get(child_id) if child_id is not None else None,
                "description": event.get("description"),
                "dateTime": dateTime,
                "endDateTime": endDateTime,
                "symptom": str(event.get("symptom")) if event.get("symptom") else None,
                "anxiety": str(event.get("anxiety")) if event.get("anxiety") else None,
                "relationship": (
                    str(event.get("relationship"))
                    if event.get("relationship")
                    else None
                ),
                "relationshipTargets": sorted(
                    [
                        id_map.get(pid, pid)
                        for pid in event.get("relationshipTargets", [])
                        if pid is not None
                    ]
                ),
                "relationshipTriangles": sorted(
                    [
                        id_map.get(pid, pid)
                        for pid in event.get("relationshipTriangles", [])
                        if pid is not None
                    ]
                ),
                "functioning": (
                    str(event.get("functioning")) if event.get("functioning") else None
                ),
            }
        )

    bonds = pdp_dict.get("pair_bonds", [])
    bonds_sorted = sorted(
        bonds, key=lambda b: (b.get("person_a") or 0, b.get("person_b") or 0)
    )

    for i, bond in enumerate(bonds_sorted):
        person_a_id = bond.get("person_a")
        person_b_id = bond.get("person_b")
        normalized["pair_bonds"].append(
            {
                "person_a": (
                    id_map.get(person_a_id) if person_a_id is not None else None
                ),
                "person_b": (
                    id_map.get(person_b_id) if person_b_id is not None else None
                ),
            }
        )

    return normalized


def calculate_statement_f1(
    ai_deltas: dict | PDPDeltas, gt_deltas: dict | PDPDeltas
) -> StatementF1Metrics:
    """
    Calculate F1 metrics comparing AI extraction to ground truth for a single statement.

    Args:
        ai_deltas: AI-generated PDPDeltas (from Statement.pdp_deltas)
        gt_deltas: Ground truth PDPDeltas (from Feedback.edited_extraction)

    Returns:
        StatementF1Metrics with all calculated metrics
    """
    if isinstance(ai_deltas, dict):
        ai_pdp = from_dict(PDPDeltas, ai_deltas)
    else:
        ai_pdp = ai_deltas

    if isinstance(gt_deltas, dict):
        gt_pdp = from_dict(PDPDeltas, gt_deltas)
    else:
        gt_pdp = gt_deltas

    metrics = StatementF1Metrics(statement_id=0)

    people_result, id_map = match_people(ai_pdp.people, gt_pdp.people)
    events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
    bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

    people_tp = len(people_result.matched_pairs)
    people_fp = len(people_result.ai_unmatched)
    people_fn = len(people_result.gt_unmatched)

    events_tp = len(events_result.matched_pairs)
    events_fp = len(events_result.ai_unmatched)
    events_fn = len(events_result.gt_unmatched)

    bonds_tp = len(bonds_result.matched_pairs)
    bonds_fp = len(bonds_result.ai_unmatched)
    bonds_fn = len(bonds_result.gt_unmatched)

    metrics.people_metrics = calculate_f1_from_counts(people_tp, people_fp, people_fn)
    metrics.events_metrics = calculate_f1_from_counts(events_tp, events_fp, events_fn)
    metrics.pair_bonds_metrics = calculate_f1_from_counts(bonds_tp, bonds_fp, bonds_fn)

    metrics.people_f1 = metrics.people_metrics.f1
    metrics.events_f1 = metrics.events_metrics.f1
    metrics.pair_bonds_f1 = metrics.pair_bonds_metrics.f1

    aggregate_tp = people_tp + events_tp + bonds_tp
    aggregate_fp = people_fp + events_fp + bonds_fp
    aggregate_fn = people_fn + events_fn + bonds_fn

    aggregate_metrics = calculate_f1_from_counts(
        aggregate_tp, aggregate_fp, aggregate_fn
    )
    metrics.aggregate_micro_f1 = aggregate_metrics.f1
    metrics.aggregate_tp = aggregate_tp
    metrics.aggregate_fp = aggregate_fp
    metrics.aggregate_fn = aggregate_fn

    if events_result.matched_pairs:
        sarf_f1s = calculate_sarf_macro_f1(events_result.matched_pairs)
        metrics.symptom_macro_f1 = sarf_f1s.get("symptom", 0.0)
        metrics.anxiety_macro_f1 = sarf_f1s.get("anxiety", 0.0)
        metrics.relationship_macro_f1 = sarf_f1s.get("relationship", 0.0)
        metrics.functioning_macro_f1 = sarf_f1s.get("functioning", 0.0)

    hierarchical_f1s = calculate_hierarchical_sarf_f1(
        ai_pdp.events, gt_pdp.events, id_map
    )
    metrics.symptom_hierarchical = hierarchical_f1s.get("symptom", SARFVariableF1())
    metrics.anxiety_hierarchical = hierarchical_f1s.get("anxiety", SARFVariableF1())
    metrics.relationship_hierarchical = hierarchical_f1s.get(
        "relationship", SARFVariableF1()
    )
    metrics.functioning_hierarchical = hierarchical_f1s.get(
        "functioning", SARFVariableF1()
    )

    ai_normalized = normalize_pdp_for_comparison(ai_deltas)
    gt_normalized = normalize_pdp_for_comparison(gt_deltas)
    metrics.exact_match = json.dumps(ai_normalized, sort_keys=True) == json.dumps(
        gt_normalized, sort_keys=True
    )

    return metrics


def calculate_system_f1(include_synthetic: bool = True) -> SystemF1Metrics:
    """
    Calculate system-wide F1 metrics across all approved ground truth statements.

    Queries database for all approved feedbacks and calculates aggregate metrics.

    Args:
        include_synthetic: If True, include synthetic discussions in metrics.
                          If False, exclude discussions where Discussion.synthetic=True.
    """
    from btcopilot.training.models import Feedback
    from btcopilot.personal.models import Statement, Discussion

    metrics = SystemF1Metrics()

    query = Feedback.query.filter(Feedback.approved == True).filter(
        Feedback.feedback_type == "extraction"
    )

    if not include_synthetic:
        query = (
            query.join(Statement, Feedback.statement_id == Statement.id)
            .join(Discussion, Statement.discussion_id == Discussion.id)
            .filter(Discussion.synthetic == False)
        )

    approved_feedbacks = query.all()

    if not approved_feedbacks:
        return metrics

    statement_metrics_list = []
    discussion_ids = set()

    for feedback in approved_feedbacks:
        statement = Statement.query.get(feedback.statement_id)
        if not statement or not statement.pdp_deltas:
            continue

        discussion_ids.add(statement.discussion_id)

        try:
            stmt_metrics = calculate_statement_f1(
                statement.pdp_deltas, feedback.edited_extraction
            )
            stmt_metrics.statement_id = statement.id
            statement_metrics_list.append(stmt_metrics)
        except Exception as e:
            _log.error(
                f"Error calculating F1 for statement {statement.id}: {e}", exc_info=True
            )
            continue

    if not statement_metrics_list:
        return metrics

    metrics.total_statements = len(statement_metrics_list)
    metrics.total_discussions = len(discussion_ids)

    metrics.aggregate_micro_f1 = sum(
        m.aggregate_micro_f1 for m in statement_metrics_list
    ) / len(statement_metrics_list)
    metrics.people_f1 = sum(m.people_f1 for m in statement_metrics_list) / len(
        statement_metrics_list
    )
    metrics.events_f1 = sum(m.events_f1 for m in statement_metrics_list) / len(
        statement_metrics_list
    )
    metrics.pair_bonds_f1 = sum(m.pair_bonds_f1 for m in statement_metrics_list) / len(
        statement_metrics_list
    )

    metrics.symptom_macro_f1 = sum(
        m.symptom_macro_f1 for m in statement_metrics_list
    ) / len(statement_metrics_list)
    metrics.anxiety_macro_f1 = sum(
        m.anxiety_macro_f1 for m in statement_metrics_list
    ) / len(statement_metrics_list)
    metrics.relationship_macro_f1 = sum(
        m.relationship_macro_f1 for m in statement_metrics_list
    ) / len(statement_metrics_list)
    metrics.functioning_macro_f1 = sum(
        m.functioning_macro_f1 for m in statement_metrics_list
    ) / len(statement_metrics_list)

    metrics.symptom_hierarchical = SARFVariableF1(
        detection_f1=sum(
            m.symptom_hierarchical.detection_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        value_match_f1=sum(
            m.symptom_hierarchical.value_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        people_match_f1=sum(
            m.symptom_hierarchical.people_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
    )
    metrics.anxiety_hierarchical = SARFVariableF1(
        detection_f1=sum(
            m.anxiety_hierarchical.detection_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        value_match_f1=sum(
            m.anxiety_hierarchical.value_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        people_match_f1=sum(
            m.anxiety_hierarchical.people_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
    )
    metrics.relationship_hierarchical = SARFVariableF1(
        detection_f1=sum(
            m.relationship_hierarchical.detection_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        value_match_f1=sum(
            m.relationship_hierarchical.value_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        people_match_f1=sum(
            m.relationship_hierarchical.people_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
    )
    metrics.functioning_hierarchical = SARFVariableF1(
        detection_f1=sum(
            m.functioning_hierarchical.detection_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        value_match_f1=sum(
            m.functioning_hierarchical.value_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
        people_match_f1=sum(
            m.functioning_hierarchical.people_match_f1 for m in statement_metrics_list
        )
        / len(statement_metrics_list),
    )

    metrics.exact_match_rate = sum(m.exact_match for m in statement_metrics_list) / len(
        statement_metrics_list
    )

    return metrics


def invalidate_f1_cache(statement_id: int | None = None):
    """
    Invalidate F1 cache when feedback is approved/unapproved or edited.

    Args:
        statement_id: If provided, only invalidate cache for this statement.
                     If None, invalidate all cache.
    """
    if statement_id is None:
        _f1_cache.clear()
        _f1_cache_time.clear()
    else:
        keys_to_remove = [k for k in _f1_cache if f"stmt_{statement_id}_" in k]
        for k in keys_to_remove:
            _f1_cache.pop(k, None)
            _f1_cache_time.pop(k, None)
