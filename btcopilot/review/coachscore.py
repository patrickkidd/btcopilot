"""How the coach's own pass scored against the agreed record (R-0242).

The coach is never a voter and its reading is never gold: it is scored against
what the room ratified, the same way the harness scores any pass (R-0249).
"""

from btcopilot.review import adapter, export, snapshot
from btcopilot.matching import (
    calculate_f1_from_counts,
    calculate_sarf_macro_f1,
    match_clusters,
    match_events,
    match_pair_bonds,
    match_people,
)
from btcopilot.schema import Cluster, from_dict


def score(cut) -> dict | None:
    """Nothing to say when the coach did not code this cut."""
    coding = snapshot.coach_coding(cut)
    if coding is None:
        return None
    mine = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    return {"agent": coding.agent, **compare(mine, export.ratified_record(cut))}


def compare(mine_data: dict, agreed_data: dict) -> dict:
    mine, agreed = adapter.pdp_from(mine_data), adapter.pdp_from(agreed_data)
    people, id_map = match_people(
        mine.people, agreed.people, mine.pair_bonds, agreed.pair_bonds
    )
    bonds = match_pair_bonds(mine.pair_bonds, agreed.pair_bonds, id_map)
    events = match_events(mine.events, agreed.events, id_map)
    clusters = match_clusters(
        _clusters(mine_data),
        _clusters(agreed_data),
        {a.id: b.id for a, b in events.matched_pairs},
    )
    variables, counts = calculate_sarf_macro_f1(events.matched_pairs)
    coded = [name for name, n in counts.items() if n]
    return {
        "people": _f1(people),
        "pair_bonds": _f1(bonds),
        "events": _f1(events),
        "clusters": _f1(clusters),
        "variables": (
            round(sum(variables[name] for name in coded) / len(coded), 2)
            if coded
            else None
        ),
        "by_variable": {name: round(variables[name], 2) for name in coded},
    }


def _clusters(data: dict) -> list[Cluster]:
    return [from_dict(Cluster, c) for c in data.get("clusters") or []]


def _f1(result) -> float:
    metrics = calculate_f1_from_counts(
        len(result.matched_pairs), len(result.ai_unmatched), len(result.gt_unmatched)
    )
    return round(metrics.f1, 2)
