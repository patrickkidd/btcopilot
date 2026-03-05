from enum import Enum
from dataclasses import dataclass, field

from btcopilot.schema import Event, PDP, Person
from btcopilot.training.f1_metrics import (
    EntityMatchResult,
    match_people,
    match_events,
    resolve_person_id,
    _augment_duplicate_person_id_map,
)

SARF_FIELDS = ("symptom", "anxiety", "relationship", "functioning")


class Impact(Enum):
    High = "high"
    Medium = "medium"
    Low = "low"


_IMPACT_ORDER = {Impact.High: 0, Impact.Medium: 1, Impact.Low: 2}


@dataclass
class FieldDisagreement:
    field: str
    values: dict[str, str | None]  # coder_id -> value
    impact: Impact


@dataclass
class EventDisagreement:
    event_a: Event | None
    event_b: Event | None
    coder_a: str
    coder_b: str
    field_disagreements: list[FieldDisagreement] = field(default_factory=list)
    description: str = ""
    person_name: str = ""
    max_impact: Impact = Impact.Low


@dataclass
class CumulativeComparison:
    coder_a: str
    coder_b: str
    people_result: EntityMatchResult | None = None
    events_result: EntityMatchResult | None = None
    disagreements: list[EventDisagreement] = field(default_factory=list)


def _sarf_val(event: Event, field_name: str) -> str | None:
    val = getattr(event, field_name, None)
    if val is None:
        return None
    return val.value if hasattr(val, "value") else str(val)


def _classify_impact(field_name: str, val_a: str | None, val_b: str | None) -> Impact:
    if val_a is None or val_b is None:
        return Impact.Medium
    if field_name in ("symptom", "anxiety", "functioning"):
        opposites = {("up", "down"), ("down", "up")}
        if (val_a, val_b) in opposites:
            return Impact.High
    if field_name == "relationship":
        if val_a != val_b:
            return Impact.High
    return Impact.Low


def _person_name(person_id: int | None, people: list[Person]) -> str:
    if person_id is None:
        return "unknown"
    for p in people:
        if p.id == person_id:
            return p.name or "unnamed"
    return f"person:{person_id}"


def compare_cumulative_pdps(
    pdp_a: PDP, pdp_b: PDP, coder_a: str, coder_b: str
) -> CumulativeComparison:
    result = CumulativeComparison(coder_a=coder_a, coder_b=coder_b)

    people_result, id_map = match_people(pdp_a.people, pdp_b.people)
    _augment_duplicate_person_id_map(id_map, pdp_a.people, pdp_b.people)
    result.people_result = people_result

    events_result = match_events(pdp_a.events, pdp_b.events, id_map)
    result.events_result = events_result

    # Matched events: compare SARF fields
    for event_a, event_b in events_result.matched_pairs:
        field_disagreements = []
        for f in SARF_FIELDS:
            val_a = _sarf_val(event_a, f)
            val_b = _sarf_val(event_b, f)
            if val_a == val_b:
                continue
            impact = _classify_impact(f, val_a, val_b)
            field_disagreements.append(FieldDisagreement(
                field=f,
                values={coder_a: val_a, coder_b: val_b},
                impact=impact,
            ))
        if field_disagreements:
            max_impact = min(field_disagreements, key=lambda fd: _IMPACT_ORDER[fd.impact]).impact
            person_id = resolve_person_id(event_a.person, id_map)
            result.disagreements.append(EventDisagreement(
                event_a=event_a,
                event_b=event_b,
                coder_a=coder_a,
                coder_b=coder_b,
                field_disagreements=field_disagreements,
                description=event_a.description or event_b.description or "",
                person_name=_person_name(person_id, pdp_b.people),
                max_impact=max_impact,
            ))

    # Unmatched events (one coder has it, the other doesn't)
    def _add_unmatched(events, present_coder, missing_coder, people, is_a_side):
        for event in events:
            coded_fields = [f for f in SARF_FIELDS if _sarf_val(event, f)]
            if not coded_fields:
                continue
            values_fn = (lambda f: {coder_a: _sarf_val(event, f), coder_b: None}) if is_a_side \
                else (lambda f: {coder_a: None, coder_b: _sarf_val(event, f)})
            field_disagreements = [
                FieldDisagreement(field=f, values=values_fn(f), impact=Impact.Medium)
                for f in coded_fields
            ]
            result.disagreements.append(EventDisagreement(
                event_a=event if is_a_side else None,
                event_b=None if is_a_side else event,
                coder_a=coder_a,
                coder_b=coder_b,
                field_disagreements=field_disagreements,
                description=event.description or "",
                person_name=_person_name(event.person, people),
                max_impact=Impact.Medium,
            ))

    _add_unmatched(events_result.ai_unmatched, coder_a, coder_b, pdp_a.people, True)
    _add_unmatched(events_result.gt_unmatched, coder_b, coder_a, pdp_b.people, False)

    return result


def prioritize_disagreements(
    comparison: CumulativeComparison,
) -> list[EventDisagreement]:
    return sorted(comparison.disagreements, key=lambda d: _IMPACT_ORDER[d.max_impact])


@dataclass
class StatementEvidence:
    statement_id: int
    statement_text: str
    coder_id: str
    event_data: dict


def trace_to_statements(
    disagreement: EventDisagreement,
    coder_feedbacks: dict[str, list[dict]],
) -> list[StatementEvidence]:
    """Find which statements introduced each side of a disagreement.

    coder_feedbacks: {coder_id: [{statement_id, statement_text, events: [...]}]}
    """
    evidence = []
    desc = disagreement.description.lower().strip() if disagreement.description else ""

    for coder_id, stmts in coder_feedbacks.items():
        if coder_id not in (disagreement.coder_a, disagreement.coder_b):
            continue
        for stmt_data in stmts:
            for event in stmt_data.get("events", []):
                event_desc = (event.get("description") or "").lower().strip()
                if desc and event_desc == desc:
                    evidence.append(StatementEvidence(
                        statement_id=stmt_data["statement_id"],
                        statement_text=stmt_data.get("statement_text", ""),
                        coder_id=coder_id,
                        event_data=event,
                    ))
    return evidence
