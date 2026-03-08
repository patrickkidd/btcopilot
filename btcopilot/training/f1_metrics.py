"""
F1 Metrics Calculation for AI Data Extraction vs Ground Truth

This module calculates F1 scores comparing AI-generated codes (Statement.pdp_deltas)
to human ground truth codes (Feedback.edited_extraction).

Matching Logic:
- People: Fuzzy name matching (token_set_ratio >= 0.6) after stripping titles
          (Aunt, Uncle, Dr., etc.) AND parents match (ignore if null) AND
          gender match (ignore if either is None/Unknown).
          "Aunt Carol" matches "Carol", "Dr. Smith" matches "Smith".
- Events: kind + date proximity + person links match (description not used for matching)
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
    EventKind,
    PairBond,
    PDP,
    PDPDeltas,
    DateCertainty,
    PersonKind,
    from_dict,
)

_log = logging.getLogger(__name__)

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


DATE_TOLERANCE_DAYS = 7
APPROXIMATE_TOLERANCE_DAYS = 730  # ±2 years (year-level estimates from vague temporal references)


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
class CumulativeF1Metrics:
    discussion_id: int
    discussion_summary: str = ""
    auditor_id: str = ""
    aggregate_micro_f1: float = 0.0
    people_f1: float = 0.0
    events_f1: float = 0.0
    pair_bonds_f1: float = 0.0
    people_metrics: F1Metrics = field(default_factory=F1Metrics)
    events_metrics: F1Metrics = field(default_factory=F1Metrics)
    pair_bonds_metrics: F1Metrics = field(default_factory=F1Metrics)
    symptom_macro_f1: float = 0.0
    anxiety_macro_f1: float = 0.0
    relationship_macro_f1: float = 0.0
    functioning_macro_f1: float = 0.0
    ai_people_count: int = 0
    ai_events_count: int = 0
    gt_people_count: int = 0
    gt_events_count: int = 0


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
    - If either is Approximate: ±270 days (9 months)
    - Both Certain: ±7 days
    - None (missing): treated as Approximate (therapy transcripts rarely have precise dates)
    """
    c1 = certainty1 or DateCertainty.Approximate
    c2 = certainty2 or DateCertainty.Approximate

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
    - If either is Approximate: use 270-day tolerance (9 months)
    - Both Certain: use 7-day tolerance
    - None (missing): treated as Approximate (therapy transcripts rarely have precise dates)
    """
    c1 = certainty1 or DateCertainty.Approximate
    c2 = certainty2 or DateCertainty.Approximate

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


def _resolve_parent_names(
    person: Person,
    people: list[Person],
    pair_bonds: list[PairBond],
) -> set[str]:
    """Get normalized parent names for a person via their parents PairBond."""
    if person.parents is None:
        return set()
    people_by_id = {p.id: p for p in people}
    for bond in pair_bonds:
        if bond.id == person.parents:
            names = set()
            for pid in (bond.person_a, bond.person_b):
                parent = people_by_id.get(pid)
                if parent and parent.name:
                    names.add(normalize_name_for_matching(parent.name))
            return names
    return set()


PARENTS_BOOST = 0.1


def _parents_score(
    ai_person: Person,
    gt_person: Person,
    ai_people: list[Person],
    gt_people: list[Person],
    ai_pair_bonds: list[PairBond],
    gt_pair_bonds: list[PairBond],
) -> float:
    """Score 0.0-1.0 for how well parents match between two person candidates.

    Returns 0.5 (neutral) if either side has no parents data.
    """
    ai_parents = _resolve_parent_names(ai_person, ai_people, ai_pair_bonds)
    gt_parents = _resolve_parent_names(gt_person, gt_people, gt_pair_bonds)
    if not ai_parents or not gt_parents:
        return 0.5
    total = 0.0
    comparisons = 0
    for ai_name in ai_parents:
        for gt_name in gt_parents:
            total += fuzz.token_set_ratio(ai_name, gt_name) / 100.0
            comparisons += 1
    avg = total / comparisons if comparisons else 0.5
    return avg


def match_people(
    ai_people: list[Person],
    gt_people: list[Person],
    ai_pair_bonds: list[PairBond] | None = None,
    gt_pair_bonds: list[PairBond] | None = None,
) -> tuple[EntityMatchResult, dict[int, int]]:
    """Match people by name similarity, gender, and parent names.

    Parent matching acts as a tiebreaker when multiple GT candidates have
    similar name scores. Requires pair_bonds lists to resolve Person.parents
    PairBond IDs to parent person names.
    """
    result = EntityMatchResult()
    id_map = {}
    ai_bonds = ai_pair_bonds or []
    gt_bonds = gt_pair_bonds or []

    gt_remaining = list(gt_people)
    ai_processed = set()

    for ai_person in ai_people:
        best_match = None
        best_score = 0.0

        for gt_person in gt_remaining:
            ai_name_normalized = normalize_name_for_matching(ai_person.name)
            gt_name_normalized = normalize_name_for_matching(gt_person.name)

            # "User" is the SARF editor default client label — match any AI name
            if gt_name_normalized == "user":
                name_sim = 1.0
            else:
                name_sim = (
                    fuzz.token_set_ratio(ai_name_normalized, gt_name_normalized)
                    / 100.0
                )

            if name_sim < NAME_SIMILARITY_THRESHOLD:
                continue

            # Gender must match if both are set (ignore if either is None/Unknown)
            gender_match = True
            if ai_person.gender is not None and gt_person.gender is not None:
                if (
                    ai_person.gender != PersonKind.Unknown
                    and gt_person.gender != PersonKind.Unknown
                ):
                    gender_match = ai_person.gender == gt_person.gender

            if not gender_match:
                continue

            parent_sim = _parents_score(
                ai_person, gt_person,
                ai_people, gt_people,
                ai_bonds, gt_bonds,
            )
            score = name_sim + PARENTS_BOOST * parent_sim

            if score > best_score:
                best_score = score
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
    Match events by kind, date, and person links (description not used).

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

            # Birth/Adopted: child is the primary link (who was born/adopted),
            # person/spouse are optional parent links.
            # Other events: person is the primary link.
            is_child_centric = ai_event.kind in (EventKind.Birth, EventKind.Adopted)
            if is_child_centric:
                links_match = (
                    ai_child == gt_event.child
                    and (gt_event.person is None or ai_person == gt_event.person)
                    and (gt_event.spouse is None or ai_spouse == gt_event.spouse)
                )
            else:
                links_match = (
                    ai_person == gt_event.person
                    and ai_spouse == gt_event.spouse
                    and ai_child == gt_event.child
                )
            # Targets/triangles: require overlap if both non-empty, pass if either is empty
            gt_targets = set(gt_event.relationshipTargets or [])
            gt_triangles = set(gt_event.relationshipTriangles or [])
            if ai_targets and gt_targets:
                links_match = links_match and bool(set(ai_targets) & gt_targets)
            if ai_triangles and gt_triangles:
                links_match = links_match and bool(set(ai_triangles) & gt_triangles)

            if links_match:
                score = calculate_date_similarity(
                    ai_event.dateTime,
                    gt_event.dateTime,
                    ai_event.dateCertainty,
                    gt_event.dateCertainty,
                )
                if score > best_score:
                    best_score = score
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

    people_result, id_map = match_people(
        ai_pdp.people, gt_pdp.people, ai_pdp.pair_bonds, gt_pdp.pair_bonds
    )
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


def _augment_committed_id_map(
    id_map: dict[int, int],
    ai_pdp: PDP,
    gt_pdp: PDP,
    discussion,
) -> None:
    """
    Augment id_map with mappings for committed (positive) person IDs.

    When diagram_data has duplicate entries for the same person (e.g., id=1
    "Sarah" and id=3 "Sarah"), the AI extraction may reference a different
    committed ID than the GT cumulative PDP uses. This causes false negatives
    in event and PairBond matching even when the AI correctly identified the
    right person.

    This function finds committed IDs referenced in AI events/PairBonds that
    don't appear in GT, and maps them to GT committed IDs by name matching
    against diagram_data.
    """
    if not discussion.diagram:
        return

    diagram_data = discussion.diagram.get_diagram_data()
    committed_people = diagram_data.people
    if not committed_people:
        return

    # Collect all positive (committed) IDs referenced in AI events and PairBonds
    ai_committed_ids = set()
    for event in ai_pdp.events:
        for field_name in ("person", "spouse", "child"):
            pid = getattr(event, field_name, None)
            if pid is not None and pid > 0:
                ai_committed_ids.add(pid)
        for field_name in ("relationshipTargets", "relationshipTriangles"):
            for pid in getattr(event, field_name, []) or []:
                if pid > 0:
                    ai_committed_ids.add(pid)
    for bond in ai_pdp.pair_bonds:
        if bond.person_a is not None and bond.person_a > 0:
            ai_committed_ids.add(bond.person_a)
        if bond.person_b is not None and bond.person_b > 0:
            ai_committed_ids.add(bond.person_b)

    # Collect all positive IDs in GT people
    gt_committed_ids = {p.id for p in gt_pdp.people if p.id > 0}

    # Find AI committed IDs that aren't in GT and try to map them
    for ai_id in ai_committed_ids:
        if ai_id in id_map or ai_id in gt_committed_ids:
            continue  # Already mapped or same ID exists in GT

        # Find the name of this committed person in diagram_data
        ai_name = None
        for cp in committed_people:
            cp_id = cp.get("id") if isinstance(cp, dict) else getattr(cp, "id", None)
            if cp_id == ai_id:
                ai_name = (
                    cp.get("name") if isinstance(cp, dict) else getattr(cp, "name", None)
                )
                break

        if not ai_name:
            continue

        # Try to match this name to a GT committed person
        ai_normalized = normalize_name_for_matching(ai_name)
        for gt_person in gt_pdp.people:
            if gt_person.id <= 0 or gt_person.id in id_map.values():
                continue
            gt_normalized = normalize_name_for_matching(gt_person.name)
            sim = fuzz.token_set_ratio(ai_normalized, gt_normalized) / 100.0
            if sim >= NAME_SIMILARITY_THRESHOLD:
                id_map[ai_id] = gt_person.id
                _log.debug(
                    f"Committed ID map: AI {ai_id} -> GT {gt_person.id}"
                )
                break


def _augment_duplicate_person_id_map(
    id_map: dict[int, int],
    ai_people: list[Person],
    gt_people: list[Person],
) -> None:
    """
    Augment id_map with mappings for duplicate AI people.

    When the AI extraction creates multiple people with the same name (e.g.,
    two "Robert" entries with different IDs), match_people only maps one of
    them (1:1 matching). PairBonds referencing the unmapped duplicate will
    fail to match even though they conceptually refer to the correct person.

    This function finds unmatched AI people whose names match already-matched
    GT people, and adds those duplicate mappings to the id_map.
    """
    # Build reverse map: GT person ID -> GT person name
    gt_id_to_name = {p.id: p.name for p in gt_people}

    # Build set of already-matched GT IDs from id_map values
    matched_gt_ids = set(id_map.values())

    # For each AI person NOT in the id_map, try name matching against
    # already-matched GT people
    for ai_person in ai_people:
        if ai_person.id in id_map:
            continue  # Already mapped

        ai_normalized = normalize_name_for_matching(ai_person.name)
        if not ai_normalized:
            continue

        best_gt_id = None
        best_score = 0.0

        for gt_id in matched_gt_ids:
            gt_name = gt_id_to_name.get(gt_id)
            if not gt_name:
                continue
            gt_normalized = normalize_name_for_matching(gt_name)
            sim = fuzz.token_set_ratio(ai_normalized, gt_normalized) / 100.0
            if sim >= NAME_SIMILARITY_THRESHOLD and sim > best_score:
                best_score = sim
                best_gt_id = gt_id

        if best_gt_id is not None:
            id_map[ai_person.id] = best_gt_id
            _log.debug(
                f"Duplicate person map: AI {ai_person.id} -> GT {best_gt_id}"
            )


def calculate_cumulative_f1(discussion_id: int) -> CumulativeF1Metrics:
    from btcopilot.personal.models import Discussion, Statement
    from btcopilot.training.models import Feedback
    from btcopilot.pdp import cumulative

    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        raise ValueError(f"Discussion {discussion_id} not found")

    # Find the approved auditor for this discussion
    approved_feedback = (
        Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
        .filter(Statement.discussion_id == discussion_id)
        .filter(Feedback.approved == True)
        .filter(Feedback.feedback_type == "extraction")
        .first()
    )
    if not approved_feedback:
        raise ValueError(f"No approved GT for discussion {discussion_id}")

    auditor_id = approved_feedback.auditor_id

    # Get last statement
    last_stmt = max(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))

    ai_pdp = cumulative(discussion, last_stmt)
    gt_pdp = cumulative(discussion, last_stmt, auditor_id=auditor_id)

    # Fall back to diagram PDP when no per-statement deltas exist (extract_full path)
    if (
        not ai_pdp.people
        and not ai_pdp.events
        and not ai_pdp.pair_bonds
        and discussion.diagram
    ):
        diagram_data = discussion.diagram.get_diagram_data()
        if diagram_data.pdp.people or diagram_data.pdp.events or diagram_data.pdp.pair_bonds:
            ai_pdp = diagram_data.pdp

    metrics = CumulativeF1Metrics(
        discussion_id=discussion_id,
        discussion_summary=discussion.summary or "",
        auditor_id=auditor_id,
        ai_people_count=len(ai_pdp.people),
        ai_events_count=len(ai_pdp.events),
        gt_people_count=len(gt_pdp.people),
        gt_events_count=len(gt_pdp.events),
    )

    people_result, id_map = match_people(
        ai_pdp.people, gt_pdp.people, ai_pdp.pair_bonds, gt_pdp.pair_bonds
    )

    # Augment id_map: resolve committed ID mismatches from diagram_data
    if discussion.diagram:
        _augment_committed_id_map(id_map, ai_pdp, gt_pdp, discussion)

    # Augment id_map: resolve duplicate AI people (same name, different IDs)
    _augment_duplicate_person_id_map(id_map, ai_pdp.people, gt_pdp.people)

    events_result = match_events(ai_pdp.events, gt_pdp.events, id_map)
    bonds_result = match_pair_bonds(ai_pdp.pair_bonds, gt_pdp.pair_bonds, id_map)

    metrics.people_metrics = calculate_f1_from_counts(
        len(people_result.matched_pairs),
        len(people_result.ai_unmatched),
        len(people_result.gt_unmatched),
    )
    metrics.events_metrics = calculate_f1_from_counts(
        len(events_result.matched_pairs),
        len(events_result.ai_unmatched),
        len(events_result.gt_unmatched),
    )
    metrics.pair_bonds_metrics = calculate_f1_from_counts(
        len(bonds_result.matched_pairs),
        len(bonds_result.ai_unmatched),
        len(bonds_result.gt_unmatched),
    )

    metrics.people_f1 = metrics.people_metrics.f1
    metrics.events_f1 = metrics.events_metrics.f1
    metrics.pair_bonds_f1 = metrics.pair_bonds_metrics.f1

    total_tp = (
        metrics.people_metrics.tp
        + metrics.events_metrics.tp
        + metrics.pair_bonds_metrics.tp
    )
    total_fp = (
        metrics.people_metrics.fp
        + metrics.events_metrics.fp
        + metrics.pair_bonds_metrics.fp
    )
    total_fn = (
        metrics.people_metrics.fn
        + metrics.events_metrics.fn
        + metrics.pair_bonds_metrics.fn
    )
    metrics.aggregate_micro_f1 = calculate_f1_from_counts(
        total_tp, total_fp, total_fn
    ).f1

    if events_result.matched_pairs:
        sarf_f1s = calculate_sarf_macro_f1(events_result.matched_pairs)
        metrics.symptom_macro_f1 = sarf_f1s.get("symptom", 0.0)
        metrics.anxiety_macro_f1 = sarf_f1s.get("anxiety", 0.0)
        metrics.relationship_macro_f1 = sarf_f1s.get("relationship", 0.0)
        metrics.functioning_macro_f1 = sarf_f1s.get("functioning", 0.0)

    return metrics


@dataclass
class SystemCumulativeF1:
    aggregate_micro_f1: float = 0.0
    people_f1: float = 0.0
    events_f1: float = 0.0
    pair_bonds_f1: float = 0.0
    symptom_macro_f1: float = 0.0
    anxiety_macro_f1: float = 0.0
    relationship_macro_f1: float = 0.0
    functioning_macro_f1: float = 0.0
    total_discussions: int = 0
    per_discussion: list = field(default_factory=list)


def calculate_all_cumulative_f1(
    include_synthetic: bool = True,
) -> SystemCumulativeF1:
    from btcopilot.personal.models import Statement, Discussion
    from btcopilot.training.models import Feedback

    query = (
        Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
        .filter(Feedback.approved == True)
        .filter(Feedback.feedback_type == "extraction")
    )
    if not include_synthetic:
        query = query.join(
            Discussion, Statement.discussion_id == Discussion.id
        ).filter(Discussion.synthetic == False)

    discussion_ids = (
        query.with_entities(Statement.discussion_id).distinct().all()
    )

    results = []
    for (disc_id,) in discussion_ids:
        try:
            metrics = calculate_cumulative_f1(disc_id)
            results.append(metrics)
        except ValueError as e:
            _log.warning(f"Skipping discussion {disc_id}: {e}")

    system = SystemCumulativeF1(per_discussion=results)
    if results:
        n = len(results)
        system.total_discussions = n
        system.aggregate_micro_f1 = sum(r.aggregate_micro_f1 for r in results) / n
        system.people_f1 = sum(r.people_f1 for r in results) / n
        system.events_f1 = sum(r.events_f1 for r in results) / n
        system.pair_bonds_f1 = sum(r.pair_bonds_f1 for r in results) / n
        system.symptom_macro_f1 = sum(r.symptom_macro_f1 for r in results) / n
        system.anxiety_macro_f1 = sum(r.anxiety_macro_f1 for r in results) / n
        system.relationship_macro_f1 = sum(r.relationship_macro_f1 for r in results) / n
        system.functioning_macro_f1 = sum(r.functioning_macro_f1 for r in results) / n
    return system
