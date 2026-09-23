"""Content matching of two PDPs, and the F1 scores built on it.

- People: fuzzy name match (token_set_ratio >= 0.6) after stripping titles
  ("Aunt Carol" matches "Carol"), gender must agree when both are known,
  parent names break ties.
- Events: kind + date proximity + person links (description not used).
- PairBonds: person_a/person_b match after person id mapping.
- SARF variables: macro-F1 across matched events (exact enum match).
- IDs are ignored: matching is by content only.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser
from rapidfuzz import fuzz

from btcopilot.schema import (
    Person,
    Event,
    EventKind,
    PairBond,
    DateCertainty,
    PersonKind,
)

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
APPROXIMATE_TOLERANCE_DAYS = (
    730  # ±2 years (year-level estimates from vague temporal references)
)


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


def parse_date_flexible(date_str: str | None) -> datetime | None:
    """Parse date string flexibly, handling vague dates gracefully"""
    if not date_str:
        return None
    try:
        return date_parser.parse(date_str, fuzzy=True)
    except (ValueError, TypeError):
        return None


def _year_anchored(dt: datetime | None, certainty: DateCertainty) -> bool:
    """A Jan-1 date marked certain is a year-only fact ("died in 2022") —
    coding tools anchor year-precision dates at Jan 1, so day-level tolerance
    would reject any correct-year date."""
    return (
        certainty == DateCertainty.Certain
        and dt is not None
        and dt.month == 1
        and dt.day == 1
    )


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
    - If either is a Jan-1 date marked Certain (year-only fact): same calendar year matches
    - If either is Approximate: ±730 days (2 years)
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

    if _year_anchored(dt1, c1) or _year_anchored(dt2, c2):
        return dt1.year == dt2.year

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
    - If either is a Jan-1 date marked Certain (year-only fact): same calendar year scores
    - If either is Approximate: use 730-day tolerance (2 years)
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

    if _year_anchored(dt1, c1) or _year_anchored(dt2, c2):
        if dt1.year != dt2.year:
            return 0.0
        delta_days = abs((dt1 - dt2).days)
        return 1.0 if delta_days == 0 else 1.0 - delta_days / 730

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
                    fuzz.token_set_ratio(ai_name_normalized, gt_name_normalized) / 100.0
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
                ai_person,
                gt_person,
                ai_people,
                gt_people,
                ai_bonds,
                gt_bonds,
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
            # Couple events: person/spouse slots are interchangeable — the AI
            # picking the other partner as `person` is still the same event.
            is_couple = ai_event.kind in (
                EventKind.Married,
                EventKind.Divorced,
                EventKind.Separated,
                EventKind.Bonded,
            )
            if is_child_centric:
                links_match = (
                    ai_child == gt_event.child
                    and (gt_event.person is None or ai_person == gt_event.person)
                    and (gt_event.spouse is None or ai_spouse == gt_event.spouse)
                )
            elif is_couple:
                links_match = (
                    {ai_person, ai_spouse} == {gt_event.person, gt_event.spouse}
                    and ai_child == gt_event.child
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
) -> tuple[dict[str, float], dict[str, int]]:
    sarf_vars = ["symptom", "anxiety", "relationship", "functioning"]
    f1_scores = {}
    counts = {}

    for var_name in sarf_vars:
        ai_values = []
        gt_values = []
        n_coded = 0

        for ai_event, gt_event in matched_event_pairs:
            ai_val = getattr(ai_event, var_name)
            gt_val = getattr(gt_event, var_name)

            ai_str = str(ai_val) if ai_val is not None else "none"
            gt_str = str(gt_val) if gt_val is not None else "none"

            ai_values.append(ai_str)
            gt_values.append(gt_str)
            if ai_val is not None or gt_val is not None:
                n_coded += 1

        counts[var_name] = n_coded

        f1_scores[var_name] = macro_f1(gt_values, ai_values) if ai_values else 0.0

    return f1_scores, counts


def macro_f1(truth: list[str], predicted: list[str]) -> float:
    """Unweighted mean of the per-label F1 over every label either side used,
    a label with no true or predicted positives scoring 0."""
    scores = []
    for label in set(truth) | set(predicted):
        tp = sum(t == label and p == label for t, p in zip(truth, predicted))
        fp = sum(t != label and p == label for t, p in zip(truth, predicted))
        fn = sum(t == label and p != label for t, p in zip(truth, predicted))
        scores.append(calculate_f1_from_counts(tp, fp, fn).f1 if tp else 0.0)
    return sum(scores) / len(scores)
