"""What every coder saw, paired up.

When the vote opens, each finished coding's record is matched against the
first one with the same matcher the F1 harness uses, and one row per item is
written with the take each coding had. The snapshot is never maintained after
that: the rows are the event clock (R-0275).

Agreement is recomputed from the rows whenever a coding finishes and again
after ratification (R-0242). Both figures are kept, because the result screen
shows the first pass and the ratified record side by side.

The coach's replay is snapshotted like any other coding so the result screen
can say where it differed from the room, but it is never a voter: it does not
make an item disputed and it is not counted in the agreement figures (R-0242).
"""

import enum

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Coding, Item, ReviewStatus
from btcopilot.schema import ItemKind, asdict
from btcopilot.training.f1_metrics import (
    match_events,
    match_pair_bonds,
    match_people,
)

KINDS = (ItemKind.Person, ItemKind.Event, ItemKind.PairBond)
COLLECTION = {
    ItemKind.Person: "people",
    ItemKind.Event: "events",
    ItemKind.PairBond: "pair_bonds",
}


class AgreementPhase(enum.StrEnum):
    FirstPass = "first_pass"
    Ratified = "ratified"


def done_codings(cut) -> list[Coding]:
    found = [c for c in cut.codings if c.done_at is not None]
    return sorted(found, key=lambda c: (c.done_at, c.id))


def voters(cut) -> list[Coding]:
    """The people who coded: the coach's replay is a coding but never a voter."""
    return [c for c in done_codings(cut) if c.agent is None]


def coach_coding(cut) -> Coding | None:
    return next((c for c in done_codings(cut) if c.agent is not None), None)


def build(cut) -> list[Item]:
    """One row per item of the cut, with every coding's take on it."""
    Item.query.filter_by(cut_id=cut.id).delete()
    people = voters(cut)
    if not people:
        return []
    # The coach is matched in last so its take is on the row without ever
    # standing as the reference the others are paired against.
    codings = people + [c for c in done_codings(cut) if c.agent is not None]
    voter_ids = {c.id for c in people}

    records = {c.id: adapter.pdp_of(_diagram(c)) for c in codings}
    reference = people[0]
    rows = []
    for kind in KINDS:
        for takes in _groups(kind, reference, codings, records):
            rows.append(
                Item(
                    cut_id=cut.id,
                    item_kind=kind,
                    takes=takes,
                    status=_status(takes, voter_ids),
                )
            )
    db.session.add_all(rows)
    db.session.flush()
    return rows


def _diagram(coding: Coding):
    return db.session.get(adapter.Diagram, coding.diagram_id)


def _items(pdp, kind):
    return getattr(pdp, COLLECTION[kind])


def _take(coding_id: int, item) -> dict:
    data = asdict(item)
    return {"coding_id": coding_id, "item_id": data.get("id"), "item": data}


def _groups(kind, reference, codings, records) -> list[list[dict]]:
    """The reference coding's items, each with whatever the other codings
    paired to it; anything a later coding had on its own is a group of one."""
    ref_items = _items(records[reference.id], kind)
    groups = {id(item): [_take(reference.id, item)] for item in ref_items}
    loose = []

    for coding in codings[1:]:
        pdp = records[coding.id]
        matched, unmatched = _match(kind, pdp, records[reference.id])
        for mine, theirs in matched:
            groups.setdefault(id(theirs), []).append(_take(coding.id, mine))
        loose += [[_take(coding.id, item)] for item in unmatched]

    return list(groups.values()) + loose


def _match(kind, pdp, reference):
    people, id_map = match_people(
        pdp.people, reference.people, pdp.pair_bonds, reference.pair_bonds
    )
    if kind is ItemKind.Person:
        result = people
    elif kind is ItemKind.Event:
        result = match_events(pdp.events, reference.events, id_map)
    else:
        result = match_pair_bonds(pdp.pair_bonds, reference.pair_bonds, id_map)
    return result.matched_pairs, result.ai_unmatched


def _status(takes: list[dict], voter_ids: set[int]) -> ReviewStatus:
    """Agreed when every coder has this item and wrote it the same way. What
    the coach wrote is on the row but never decides it (R-0254)."""
    theirs = [t for t in takes if t["coding_id"] in voter_ids]
    if len(theirs) < len(voter_ids) or not theirs:
        return ReviewStatus.Disputed
    first = _comparable(theirs[0]["item"])
    if all(_comparable(t["item"]) == first for t in theirs[1:]):
        return ReviewStatus.Agreed
    return ReviewStatus.Disputed


def _comparable(item: dict) -> dict:
    """Ids differ between codings of the same moment and say nothing about
    whether the coders read it the same way."""
    return {k: v for k, v in item.items() if k not in ("id", "notes")}


def agreement(cut) -> dict:
    """The figures the cut carries: how many items every coder read the same
    way, out of how many, over how many people coded it."""
    rows = Item.query.filter_by(cut_id=cut.id).all()
    counts = {status.value: 0 for status in ReviewStatus}
    for row in rows:
        counts[row.status.value] += 1
    total = len(rows)
    agreed = counts[ReviewStatus.Agreed.value] + counts[ReviewStatus.Settled.value]
    return {
        "codings": len(voters(cut)),
        "items": total,
        "by_status": counts,
        "percent": round(100.0 * agreed / total, 1) if total else None,
    }


def recompute(cut, phase: AgreementPhase = AgreementPhase.FirstPass) -> dict:
    """Both figures are kept: the first pass is what the coders reached on
    their own, the ratified one is what the room reached together."""
    figures = dict(cut.agreement or {})
    figures[phase.value] = agreement(cut)
    cut.agreement = figures
    db.session.flush()
    return figures
