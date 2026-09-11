"""What every coder saw, paired up.

When the vote opens, each finished coding's record is matched against the
first one with the same matcher the F1 harness uses, and one row per item is
written with the take each coding had. The snapshot is never maintained after
that: the rows are the event clock (R-0275).

Agreement is recomputed from the rows whenever a coding finishes and again
after ratification (R-0242).
"""

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


def done_codings(cut) -> list[Coding]:
    found = [c for c in cut.codings if c.done_at is not None]
    return sorted(found, key=lambda c: (c.done_at, c.id))


def build(cut) -> list[Item]:
    """One row per item of the cut, with every coding's take on it."""
    Item.query.filter_by(cut_id=cut.id).delete()
    codings = done_codings(cut)
    if not codings:
        return []

    records = {c.id: adapter.pdp_of(_diagram(c)) for c in codings}
    reference = codings[0]
    rows = []
    for kind in KINDS:
        for takes in _groups(kind, reference, codings, records):
            rows.append(
                Item(
                    cut_id=cut.id,
                    item_kind=kind,
                    takes=takes,
                    status=_status(takes, len(codings)),
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


def _status(takes: list[dict], coders: int) -> ReviewStatus:
    """Agreed when every coder has this item and wrote it the same way."""
    if len(takes) < coders:
        return ReviewStatus.Disputed
    first = _comparable(takes[0]["item"])
    if all(_comparable(t["item"]) == first for t in takes[1:]):
        return ReviewStatus.Agreed
    return ReviewStatus.Disputed


def _comparable(item: dict) -> dict:
    """Ids differ between codings of the same moment and say nothing about
    whether the coders read it the same way."""
    return {k: v for k, v in item.items() if k not in ("id", "notes")}


def agreement(cut) -> dict:
    """The figures the cut carries: how many items every coder read the same
    way, out of how many, over how many finished codings."""
    rows = Item.query.filter_by(cut_id=cut.id).all()
    counts = {status.value: 0 for status in ReviewStatus}
    for row in rows:
        counts[row.status.value] += 1
    total = len(rows)
    agreed = counts[ReviewStatus.Agreed.value] + counts[ReviewStatus.Settled.value]
    return {
        "codings": len(done_codings(cut)),
        "items": total,
        "by_status": counts,
        "percent": round(100.0 * agreed / total, 1) if total else None,
    }


def recompute(cut) -> dict:
    cut.agreement = agreement(cut)
    db.session.flush()
    return cut.agreement
