"""How the coach's own pass scored against the agreed record (R-0242).

The coach is never a voter and its reading is never gold: it is scored against
what the room ratified, the same way the harness scores any pass (R-0249).
"""

from btcopilot.review import adapter, export, snapshot
from btcopilot.training.f1_metrics import (
    calculate_f1_from_counts,
    calculate_sarf_macro_f1,
    match_events,
    match_people,
)


def score(cut) -> dict | None:
    """Nothing to say when the coach did not code this cut."""
    coding = snapshot.coach_coding(cut)
    if coding is None:
        return None
    mine = adapter.pdp_of(adapter.diagram_of(coding.diagram_id))
    agreed = adapter.pdp_from(export.ratified_record(cut))

    people, id_map = match_people(
        mine.people, agreed.people, mine.pair_bonds, agreed.pair_bonds
    )
    events = match_events(mine.events, agreed.events, id_map)
    variables, counts = calculate_sarf_macro_f1(events.matched_pairs)
    coded = [name for name, n in counts.items() if n]
    return {
        "agent": coding.agent,
        "people": _f1(people),
        "events": _f1(events),
        "variables": (
            round(sum(variables[name] for name in coded) / len(coded), 2)
            if coded
            else None
        ),
        "by_variable": {name: round(variables[name], 2) for name in coded},
    }


def _f1(result) -> float:
    metrics = calculate_f1_from_counts(
        len(result.matched_pairs), len(result.ai_unmatched), len(result.gt_unmatched)
    )
    return round(metrics.f1, 2)
