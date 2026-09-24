"""What every coder saw, paired up.

When the vote opens, each finished coding's record is matched against the
first one with the same matcher the F1 harness uses, and one row per item is
written with the opinion each coding had. The snapshot is never maintained after
that: the rows are the event clock (R-0275).

Agreement is recomputed from the rows whenever a coding finishes and again
after ratification (R-0242). Both figures are kept, because the result screen
shows the first pass and the ratified record side by side.

The coach's replay is snapshotted like any other coding so the result screen
can say where it differed from the room, but it is never a voter: it does not
make an item disputed and it is not counted in the agreement figures (R-0242).
"""

import enum

from rapidfuzz import fuzz

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Coding, Item, ReviewStatus
from btcopilot.schema import ItemKind, PersonKind, asdict
from btcopilot.matching import (
    NAME_SIMILARITY_THRESHOLD,
    match_events,
    match_pair_bonds,
    match_people,
    normalize_name_for_matching,
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
    """One row per item of the cut, with every coding's opinion on it."""
    Item.query.filter_by(cut_id=cut.id).delete()
    people = voters(cut)
    if not people:
        return []
    # The coach is matched in last so its opinion is on the row without ever
    # standing as the reference the others are paired against.
    codings = people + [c for c in done_codings(cut) if c.agent is not None]
    voter_ids = {c.id for c in people}

    records = {c.id: adapter.pdp_of(_diagram(c)) for c in codings}
    reference = people[0]
    rows = []
    for kind in KINDS:
        for opinions, ambiguous in _groups(kind, reference, codings, records):
            rows.append(
                Item(
                    cut_id=cut.id,
                    item_kind=kind,
                    opinions=opinions,
                    ambiguous=ambiguous,
                    # Who is who is the room's to settle, so an item the matcher
                    # could not place is never agreed on its own (R-0326).
                    status=(
                        ReviewStatus.Disputed
                        if ambiguous
                        else _status(opinions, voter_ids)
                    ),
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


def _groups(kind, reference, codings, records) -> list[tuple[list[dict], bool]]:
    """The reference coding's items, each with whatever the other codings
    paired to it; anything a later coding had on its own is a group of one.
    Each group says whether the matcher was sure who it was looking at."""
    ref_items = _items(records[reference.id], kind)
    groups = {id(item): [_take(reference.id, item)] for item in ref_items}
    unsure: set[int] = set()
    loose = []

    for coding in codings[1:]:
        pdp = records[coding.id]
        matched, unmatched, ambiguous = _match(kind, pdp, records[reference.id])
        for mine, theirs in matched:
            groups.setdefault(id(theirs), []).append(_take(coding.id, mine))
            if id(mine) in ambiguous:
                unsure.add(id(theirs))
        loose += [[_take(coding.id, item)] for item in unmatched]

    paired = [(opinions, key in unsure) for key, opinions in groups.items()]
    return paired + [(one, False) for one in loose]


def _match(kind, pdp, reference):
    people, id_map = match_people(
        pdp.people, reference.people, pdp.pair_bonds, reference.pair_bonds
    )
    if kind is ItemKind.Person:
        return by_place(pdp, reference, people, id_map)
    if kind is ItemKind.Event:
        result = match_events(pdp.events, reference.events, id_map)
    else:
        result = match_pair_bonds(pdp.pair_bonds, reference.pair_bonds, id_map)
    return result.matched_pairs, result.ai_unmatched, []


class Place(enum.StrEnum):
    """How one person is tied to another in the record."""

    Partner = "partner"
    Child = "child"


def places(pdp) -> dict[int, set[tuple]]:
    """Where each person stands in the family: who they are bonded to, and who
    is born to that bond. Two codings that named the same man differently —
    "father", "Corinne's father", "Marcus" — still put him in the same place."""
    found: dict[int, set[tuple]] = {p.id: set() for p in pdp.people}
    for bond in pdp.pair_bonds:
        sides = [bond.person_a, bond.person_b]
        kids = [p.id for p in pdp.people if p.parents == bond.id]
        for side in sides:
            if side not in found:
                continue
            for other in sides:
                if other is not None and other != side:
                    found[side].add((Place.Partner.value, other))
            for kid in kids:
                found[side].add((Place.Child.value, kid))
        for kid in kids:
            for side in sides:
                if side is not None and kid in found:
                    found[kid].add((Place.Partner.value, side))
    return found


def _seen(place: set[tuple], id_map: dict[int, int]) -> set[tuple]:
    """One person's place said in the reference coding's own ids, dropping the
    ties to people the matcher has not paired up yet."""
    return {(role, id_map[other]) for role, other in place if other in id_map}


def _fits(mine, theirs) -> bool:
    """Gender the way the F1 matcher reads it: unknown could be anyone."""
    if mine.gender is None or theirs.gender is None:
        return True
    if PersonKind.Unknown in (mine.gender, theirs.gender):
        return True
    return mine.gender == theirs.gender


def _alike(mine, theirs) -> float:
    return (
        fuzz.token_set_ratio(
            normalize_name_for_matching(mine.name),
            normalize_name_for_matching(theirs.name),
        )
        / 100.0
    )


def _rivals(mine, theirs, reference) -> bool:
    """Somebody else in the reference coding this person reads as well as the
    one they were paired with, with nothing in the family to tell them apart."""
    score = _alike(mine, theirs)
    return any(
        other.id != theirs.id
        and _fits(mine, other)
        and _alike(mine, other) >= max(score, NAME_SIMILARITY_THRESHOLD)
        for other in reference.people
    )


def by_place(pdp, reference, result, id_map: dict[int, int]):
    """The people of one coding paired with the reference coding's, corrected by
    where each person stands in the family rather than by their name alone.

    A pairing the two families contradict is undone, a person nobody named is
    paired by the bond they hang on, and a person who could be two people is
    handed to the room as one item with both versions on it (R-0326).
    """
    mine_place = places(pdp)
    their_place = places(reference)
    pairs = list(result.matched_pairs)
    ambiguous: set[int] = set()

    kept = []
    for mine, theirs in pairs:
        here = _seen(mine_place.get(mine.id, set()), id_map)
        there = their_place.get(theirs.id, set())
        if here and there and not (here & there):
            id_map.pop(mine.id, None)
            continue
        if not (here & there) and _rivals(mine, theirs, reference):
            ambiguous.add(id(mine))
        kept.append((mine, theirs))

    taken = {theirs.id for _, theirs in kept}
    for mine in pdp.people:
        if any(mine is one for one, _ in kept):
            continue
        here = _seen(mine_place.get(mine.id, set()), id_map)
        if not here:
            continue
        candidates = [
            theirs
            for theirs in reference.people
            if theirs.id not in taken
            and _fits(mine, theirs)
            and here & their_place.get(theirs.id, set())
        ]
        if len(candidates) == 1:
            kept.append((mine, candidates[0]))
            taken.add(candidates[0].id)
            id_map[mine.id] = candidates[0].id
        elif candidates:
            kept.append((mine, candidates[0]))
            taken.add(candidates[0].id)
            id_map[mine.id] = candidates[0].id
            ambiguous.add(id(mine))

    unmatched = [
        p for p in pdp.people if not any(p is one for one, _ in kept)
    ]
    return kept, unmatched, ambiguous


def _status(opinions: list[dict], voter_ids: set[int]) -> ReviewStatus:
    """Agreed when every coder has this item and wrote it the same way. What
    the coach wrote is on the row but never decides it (R-0254)."""
    theirs = [t for t in opinions if t["coding_id"] in voter_ids]
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
    agreed = counts[ReviewStatus.Agreed.value] + counts[ReviewStatus.Decided.value]
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
