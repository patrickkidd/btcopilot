import copy
import logging
import os
import secrets
from datetime import date, datetime

import json

from btcopilot.extensions import ai_log
from btcopilot.llmutil import gemini_structured
from btcopilot.personal.models import SpeakerType
from btcopilot.training.f1_metrics import match_people
from btcopilot.personal.prompts import (
    DATA_EXTRACTION_CORRECTION,
    DATA_EXTRACTION_PASS1_PROMPT,
    DATA_EXTRACTION_PASS1_CONTEXT,
    DATA_EXTRACTION_PASS2_PROMPT,
    DATA_EXTRACTION_PASS2_CONTEXT,
    SARF_REVIEW_PROMPT,
    CURSOR_MARKER_TEMPLATE,
    CURSOR_EXTRACTION_RULE_TEMPLATE,
)
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    PDPValidationError,
    Person,
    Event,
    EventKind,
    PairBond,
    asdict,
    from_dict,
    get_all_pdp_item_ids,
)

_log = logging.getLogger(__name__)


def _pretty_repr(obj):
    try:
        from rich.pretty import pretty_repr

        return pretty_repr(obj)
    except ImportError:
        return repr(obj)


def reassign_delta_ids(pdp: PDP, deltas: PDPDeltas) -> None:
    """
    Reassign IDs in deltas to ensure no collisions across entity types.

    LLMs often reuse IDs across people/events/pair_bonds. This function
    assigns new unique IDs and updates all references in-place.
    """
    existing_ids = get_all_pdp_item_ids(pdp)

    # Collect all IDs from delta
    delta_person_ids = [p.id for p in deltas.people if p.id is not None]
    delta_event_ids = [e.id for e in deltas.events]
    delta_pair_bond_ids = [pb.id for pb in deltas.pair_bonds if pb.id is not None]

    # Check if reassignment needed
    all_delta_ids = (
        set(delta_person_ids) | set(delta_event_ids) | set(delta_pair_bond_ids)
    )
    has_collision = len(all_delta_ids) < len(delta_person_ids) + len(
        delta_event_ids
    ) + len(delta_pair_bond_ids) or bool(all_delta_ids & existing_ids)
    if not has_collision:
        return

    # Find lowest available ID
    all_ids = existing_ids | all_delta_ids
    next_id = min(all_ids) - 1 if all_ids else -1

    # Phase 1: Build separate mappings for each entity type
    # People get assigned first (they are referenced by events)
    person_id_map: dict[int, int] = {}
    for person in deltas.people:
        if person.id is not None and person.id < 0:
            person_id_map[person.id] = next_id
            next_id -= 1

    # Pair bonds second (referenced by person.parents)
    pair_bond_id_map: dict[int, int] = {}
    for pair_bond in deltas.pair_bonds:
        if pair_bond.id is not None and pair_bond.id < 0:
            pair_bond_id_map[pair_bond.id] = next_id
            next_id -= 1

    # Events last
    event_id_map: dict[int, int] = {}
    for event in deltas.events:
        if event.id < 0:
            event_id_map[event.id] = next_id
            next_id -= 1

    # Phase 2: Apply mappings
    for person in deltas.people:
        if person.id is not None and person.id in person_id_map:
            person.id = person_id_map[person.id]
        if person.parents is not None and person.parents in pair_bond_id_map:
            person.parents = pair_bond_id_map[person.parents]

    for pair_bond in deltas.pair_bonds:
        if pair_bond.id is not None and pair_bond.id in pair_bond_id_map:
            pair_bond.id = pair_bond_id_map[pair_bond.id]
        if pair_bond.person_a is not None and pair_bond.person_a in person_id_map:
            pair_bond.person_a = person_id_map[pair_bond.person_a]
        if pair_bond.person_b is not None and pair_bond.person_b in person_id_map:
            pair_bond.person_b = person_id_map[pair_bond.person_b]

    for event in deltas.events:
        if event.id in event_id_map:
            event.id = event_id_map[event.id]
        if event.person is not None and event.person in person_id_map:
            event.person = person_id_map[event.person]
        if event.spouse is not None and event.spouse in person_id_map:
            event.spouse = person_id_map[event.spouse]
        if event.child is not None and event.child in person_id_map:
            event.child = person_id_map[event.child]
        event.relationshipTargets = [
            person_id_map.get(t, t) for t in event.relationshipTargets
        ]
        event.relationshipTriangles = [
            person_id_map.get(t, t) for t in event.relationshipTriangles
        ]

    all_id_map = {**person_id_map, **pair_bond_id_map, **event_id_map}
    deltas.delete = [all_id_map.get(d, d) for d in deltas.delete]

    _log.warning(
        "reassign_delta_ids: LLM produced ID collisions, "
        f"reassigned {len(person_id_map)} people, {len(event_id_map)} events, {len(pair_bond_id_map)} pair_bonds"
    )


def dedup_pair_bonds(deltas: PDPDeltas) -> None:
    """Remove duplicate PairBonds for the same dyad, keeping the first.
    Remaps Person.parents references from removed IDs to kept IDs."""
    seen: dict[tuple[int, int], int] = {}  # dyad -> kept PairBond ID
    unique = []
    remap: dict[int, int] = {}  # removed ID -> kept ID

    for pb in deltas.pair_bonds:
        if pb.person_a is not None and pb.person_b is not None:
            dyad = tuple(sorted([pb.person_a, pb.person_b]))
            if dyad in seen:
                remap[pb.id] = seen[dyad]
                continue
            seen[dyad] = pb.id
        unique.append(pb)

    if remap:
        _log.warning(f"dedup_pair_bonds: removed {len(remap)} duplicate pair bonds")
        deltas.pair_bonds = unique
        for person in deltas.people:
            if person.parents in remap:
                person.parents = remap[person.parents]


def fix_birth_event_self_references(deltas: PDPDeltas) -> None:
    """Fix birth/adopted events where person == child (self-reference bug).

    The LLM sometimes sets person=child on birth events, meaning "person births
    themselves." The correct semantics are: child = who was born, person = parent.
    When person == child, clear person to None so _create_inferred_birth_items
    can create proper parent references during commit.
    """
    for event in deltas.events:
        if event.kind not in (EventKind.Birth, EventKind.Adopted):
            continue
        if (
            event.person is not None
            and event.child is not None
            and event.person == event.child
        ):
            _log.warning(
                f"fix_birth_event_self_references: Event {event.id} has "
                f"person==child=={event.person}, clearing person to None"
            )
            event.person = None


def fix_unresolved_person_refs(
    deltas: PDPDeltas,
    pdp: PDP,
    diagram_data: DiagramData | None = None,
) -> None:
    """Deterministically drop events/pair_bonds whose person references do not
    resolve. The LLM sometimes emits a positive person id that is not a
    committed person (hallucinated "committed" ref) or a negative id with no
    matching delta/PDP person. Per PDP_DATA_FLOW.md positive ids must reference
    committed people and negatives must reference delta/PDP people; an
    unresolvable ref makes the item un-anchorable and, uncaught, fabricates
    orphaned structure at commit (FD-319, diagram 1928). Mutates in place."""
    committed = (
        {p["id"] for p in diagram_data.people if "id" in p}
        if diagram_data
        else set()
    )
    valid_neg = {p.id for p in pdp.people if p.id is not None}
    valid_neg |= {p.id for p in deltas.people if p.id is not None}

    def unresolved(ref) -> bool:
        if ref is None:
            return False
        if ref > 0:
            return ref not in committed
        return ref not in valid_neg

    kept_events = []
    for e in deltas.events:
        bad = next(
            (
                r
                for r in ("person", "spouse", "child")
                if unresolved(getattr(e, r))
            ),
            None,
        )
        if bad is not None:
            _log.warning(
                f"fix_unresolved_person_refs: dropping event {e.id} "
                f"(kind={e.kind.value}); {bad}={getattr(e, bad)} does not "
                f"resolve to a committed or delta person"
            )
            continue
        kept_events.append(e)
    deltas.events = kept_events

    kept_bonds = []
    dropped_bond_ids = set()
    for b in deltas.pair_bonds:
        if unresolved(b.person_a) or unresolved(b.person_b):
            _log.warning(
                f"fix_unresolved_person_refs: dropping pair_bond {b.id} "
                f"(person_a={b.person_a}, person_b={b.person_b}): endpoint "
                f"does not resolve to a committed or delta person"
            )
            dropped_bond_ids.add(b.id)
            continue
        kept_bonds.append(b)
    deltas.pair_bonds = kept_bonds

    # Dropping a bond must not orphan Person.parents pointing at it, else the
    # validator fails "Person references non-existent pair_bond" and the retry
    # loop never converges.
    for p in deltas.people:
        if p.parents is not None and p.parents in dropped_bond_ids:
            _log.warning(
                f"fix_unresolved_person_refs: clearing person {p.id} parents "
                f"-> dropped pair_bond {p.parents}"
            )
            p.parents = None


def _self_parent_dyad(
    person: Person,
    deltas: PDPDeltas,
    diagram_data: DiagramData | None,
) -> tuple[int | None, int | None] | None:
    """If person.parents resolves to a PairBond that contains person.id, return
    that bond's (person_a, person_b). Otherwise return None. Looks up first in
    deltas.pair_bonds, then in committed diagram_data.pair_bonds."""
    if person.id is None or person.parents is None:
        return None
    for pb in deltas.pair_bonds:
        if pb.id == person.parents:
            if person.id in (pb.person_a, pb.person_b):
                return pb.person_a, pb.person_b
            return None
    if diagram_data:
        for cpb in diagram_data.pair_bonds:
            if cpb.get("id") == person.parents:
                a, b = cpb.get("person_a"), cpb.get("person_b")
                if person.id in (a, b):
                    return a, b
                return None
    return None


def fix_self_parent_references(
    deltas: PDPDeltas, diagram_data: DiagramData | None = None
) -> None:
    """Clear Person.parents when the referenced PairBond contains the person.
    The LLM occasionally outputs self-parent references; this is biologically
    impossible. Drop the bad reference; leave the PairBond intact (it may be
    a legitimate marriage to someone other than the mistaken 'child')."""
    for person in deltas.people:
        dyad = _self_parent_dyad(person, deltas, diagram_data)
        if dyad is None:
            continue
        a, b = dyad
        _log.warning(
            f"fix_self_parent_references: Person {person.id} parents=PairBond "
            f"{person.parents} contains self (person_a={a}, person_b={b}); "
            f"clearing parents to None"
        )
        person.parents = None


def _committed_person_matches(
    deltas: PDPDeltas, diagram_data: DiagramData
) -> dict[int, int]:
    """Return {negative delta person id -> committed positive person id} for
    delta people that duplicate an already-committed person. Reuses
    f1_metrics.match_people (name + gender + parent similarity)."""
    new_people = [p for p in deltas.people if p.id is not None and p.id < 0 and p.name]
    if not new_people:
        return {}

    committed_people = [
        from_dict(Person, p) for p in diagram_data.people if p.get("id") is not None
    ]
    if not committed_people:
        return {}

    committed_bonds = [from_dict(PairBond, pb) for pb in diagram_data.pair_bonds]

    _, id_map = match_people(
        new_people,
        committed_people,
        deltas.pair_bonds,
        committed_bonds,
    )
    return {
        ai_id: gt_id
        for ai_id, gt_id in id_map.items()
        if ai_id is not None and ai_id < 0 and gt_id is not None and gt_id >= 0
    }


def _remap_person_refs(deltas: PDPDeltas, remap: dict[int, int]) -> None:
    """Rewrite every delta reference to a remapped person id and drop the
    duplicate delta Person rows."""
    deltas.people = [p for p in deltas.people if p.id not in remap]

    for person in deltas.people:
        if person.parents is not None and person.parents in remap:
            person.parents = remap[person.parents]

    for event in deltas.events:
        if event.person is not None and event.person in remap:
            event.person = remap[event.person]
        if event.spouse is not None and event.spouse in remap:
            event.spouse = remap[event.spouse]
        if event.child is not None and event.child in remap:
            event.child = remap[event.child]
        event.relationshipTargets = [remap.get(t, t) for t in event.relationshipTargets]
        event.relationshipTriangles = [
            remap.get(t, t) for t in event.relationshipTriangles
        ]

    for pair_bond in deltas.pair_bonds:
        if pair_bond.person_a is not None and pair_bond.person_a in remap:
            pair_bond.person_a = remap[pair_bond.person_a]
        if pair_bond.person_b is not None and pair_bond.person_b in remap:
            pair_bond.person_b = remap[pair_bond.person_b]

    deltas.delete = [remap.get(d, d) for d in deltas.delete]


def _committed_dyads(diagram_data: DiagramData) -> set[tuple[int, int]]:
    dyads: set[tuple[int, int]] = set()
    for cpb in diagram_data.pair_bonds:
        a, b = cpb.get("person_a"), cpb.get("person_b")
        if a is not None and b is not None:
            dyads.add(tuple(sorted([a, b])))
    return dyads


def _drop_committed_dup_pair_bonds(
    deltas: PDPDeltas, diagram_data: DiagramData
) -> None:
    """Drop delta PairBonds whose dyad already exists in the committed diagram,
    clearing Person.parents references off the removed bond."""
    committed_dyads = _committed_dyads(diagram_data)

    kept = []
    removed_ids: set[int] = set()
    for pb in deltas.pair_bonds:
        if pb.person_a is not None and pb.person_b is not None:
            dyad = tuple(sorted([pb.person_a, pb.person_b]))
            if dyad in committed_dyads:
                if pb.id is not None:
                    removed_ids.add(pb.id)
                continue
        kept.append(pb)
    deltas.pair_bonds = kept

    if removed_ids:
        for person in deltas.people:
            if person.parents in removed_ids:
                person.parents = None


def _committed_event_keys(diagram_data: DiagramData) -> set[tuple]:
    """Identity of a committed event for dedup. PairBond-kind events are
    identified by (kind, committed dyad); Birth/Adopted by committed child;
    others by (kind, committed person). Dates are intentionally excluded —
    the LLM frequently re-infers a different day for the same committed
    structural event (e.g. 'June 1990' -> 1990-06-01 vs committed 1990-06-15)."""
    keys: set[tuple] = set()
    for ce in diagram_data.events:
        kind = ce.get("kind")
        if kind is None:
            continue
        kind = EventKind(kind)
        person, spouse, child = (
            ce.get("person"),
            ce.get("spouse"),
            ce.get("child"),
        )
        if kind.isPairBond() and not kind.isOffspring():
            if person is not None and spouse is not None:
                keys.add((kind, tuple(sorted([person, spouse]))))
        elif kind.isOffspring():
            if child is not None:
                keys.add((kind, child))
        elif person is not None:
            keys.add((kind, person))
    return keys


def _delta_event_key(ev: Event) -> tuple | None:
    if ev.kind.isPairBond() and not ev.kind.isOffspring():
        if ev.person is not None and ev.spouse is not None:
            return (ev.kind, tuple(sorted([ev.person, ev.spouse])))
        return None
    if ev.kind.isOffspring():
        return (ev.kind, ev.child) if ev.child is not None else None
    return (ev.kind, ev.person) if ev.person is not None else None


def _drop_committed_dup_events(deltas: PDPDeltas, diagram_data: DiagramData) -> None:
    """Drop delta events that duplicate a committed structural event (the
    referenced people resolve to committed positive ids)."""
    committed_keys = _committed_event_keys(diagram_data)
    kept = []
    for ev in deltas.events:
        key = _delta_event_key(ev)
        if key is not None and key in committed_keys:
            refs = key[1] if isinstance(key[1], tuple) else (key[1],)
            if all(r is not None and r >= 0 for r in refs):
                continue
        kept.append(ev)
    deltas.events = kept


def fix_committed_person_duplicates(
    deltas: PDPDeltas, diagram_data: DiagramData | None = None
) -> None:
    """Drop delta people that duplicate an already-committed person and remap
    every reference to the committed positive id. Then drop pair_bonds/events
    that fully duplicate a committed one (these survive even when the LLM
    correctly references committed people by positive id but re-emits their
    marriage/birth). Never fabricates data.

    Re-extraction on an existing diagram makes the LLM recreate committed
    people as new negative-id Persons and re-emit their marriages/births.
    Accepting those corrupts the committed diagram (FD-319)."""
    if diagram_data is None:
        return
    # match_people is a global assignment: dropping matched delta people
    # shifts the optimal matching, exposing committed duplicates the first
    # pass could not see. validate_pdp_deltas recomputes the same matcher, so
    # a single pass that leaves residual matches dead-ends extraction. Iterate
    # to a fixed point. Each non-empty pass drops >=1 delta person, so this
    # converges in <= len(deltas.people) iterations; cap defensively.
    all_remapped: dict[int, int] = {}
    for _ in range(len(deltas.people) + 2):
        remap = _committed_person_matches(deltas, diagram_data)
        if not remap:
            break
        all_remapped.update(remap)
        _remap_person_refs(deltas, remap)
    else:
        residual = _committed_person_matches(deltas, diagram_data)
        if residual:
            _log.error(
                "fix_committed_person_duplicates: did not converge; residual "
                f"committed duplicates {sorted(residual.keys())} -> "
                f"{sorted(residual.values())}"
            )
    if all_remapped:
        _log.warning(
            "fix_committed_person_duplicates: delta people "
            f"{sorted(all_remapped.keys())} duplicate committed people "
            f"{sorted(set(all_remapped.values()))}; remapped references"
        )

    n_pb, n_ev = len(deltas.pair_bonds), len(deltas.events)
    _drop_committed_dup_pair_bonds(deltas, diagram_data)
    _drop_committed_dup_events(deltas, diagram_data)
    dropped_pb = n_pb - len(deltas.pair_bonds)
    dropped_ev = n_ev - len(deltas.events)
    if dropped_pb or dropped_ev:
        _log.warning(
            "fix_committed_person_duplicates: dropped "
            f"{dropped_pb} committed-duplicate pair_bonds and "
            f"{dropped_ev} committed-duplicate events"
        )


def _committed_dup_structural_errors(
    deltas: PDPDeltas, diagram_data: DiagramData
) -> list[str]:
    """Errors for delta pair_bonds/events that duplicate a committed one and
    whose people resolve to committed positive ids. Triggers the Ralph retry
    loop so the repair pass runs even when no negative-id person was duped."""
    errors: list[str] = []
    committed_dyads = _committed_dyads(diagram_data)
    for pb in deltas.pair_bonds:
        if (
            pb.person_a is not None
            and pb.person_b is not None
            and pb.person_a >= 0
            and pb.person_b >= 0
            and tuple(sorted([pb.person_a, pb.person_b])) in committed_dyads
        ):
            errors.append(
                f"Delta pair_bond {pb.id} dyad "
                f"({pb.person_a},{pb.person_b}) duplicates a committed pair_bond"
            )
    committed_keys = _committed_event_keys(diagram_data)
    for ev in deltas.events:
        key = _delta_event_key(ev)
        if key is None or key not in committed_keys:
            continue
        refs = key[1] if isinstance(key[1], tuple) else (key[1],)
        if all(r is not None and r >= 0 for r in refs):
            errors.append(
                f"Delta event {ev.id} (kind={ev.kind.value}) duplicates a "
                f"committed event for {refs}"
            )
    return errors


def validate_pdp_deltas(
    pdp: PDP,
    deltas: PDPDeltas,
    diagram_data: DiagramData | None = None,
    source: str | None = None,
) -> None:
    """
    Validate that deltas can be safely applied to PDP. Raises PDPValidationError
    if validation fails.

    Delta entries use negative IDs for new PDP items, or positive IDs to update
    committed diagram items (e.g. setting parents on the speaker). Cross-references
    to positive IDs (committed items) are always valid.
    """
    errors = []

    # Committed diagram item IDs (positive) — valid for delta entries to reference
    committed_person_ids = set()
    committed_event_ids = set()
    committed_pair_bond_ids = set()
    if diagram_data:
        committed_person_ids = {p["id"] for p in diagram_data.people if "id" in p}
        committed_event_ids = {e["id"] for e in diagram_data.events if "id" in e}
        committed_pair_bond_ids = {
            pb["id"] for pb in diagram_data.pair_bonds if "id" in pb
        }

    person_ids_in_delta = {p.id for p in deltas.people if p.id is not None}
    event_ids_in_delta = {e.id for e in deltas.events}
    pair_bond_ids_in_delta = {pb.id for pb in deltas.pair_bonds if pb.id is not None}

    collision = person_ids_in_delta & event_ids_in_delta
    collision |= person_ids_in_delta & pair_bond_ids_in_delta
    collision |= event_ids_in_delta & pair_bond_ids_in_delta
    if collision:
        errors.append(
            f"Person, Event, and PairBond in delta share same ID(s): {collision}"
        )

    existing_pdp_person_ids = {p.id for p in pdp.people if p.id is not None}
    new_person_ids = {p.id for p in deltas.people if p.id is not None}
    all_pdp_person_ids = existing_pdp_person_ids | new_person_ids

    existing_pdp_pair_bond_ids = {pb.id for pb in pdp.pair_bonds if pb.id is not None}
    new_pair_bond_ids = {pb.id for pb in deltas.pair_bonds if pb.id is not None}
    all_pdp_pair_bond_ids = existing_pdp_pair_bond_ids | new_pair_bond_ids

    for person in deltas.people:
        if (
            person.id is not None
            and person.id >= 0
            and person.id not in committed_person_ids
        ):
            errors.append(
                f"Delta person has positive ID {person.id} not in committed diagram"
            )

    if diagram_data:
        for delta_id, committed_id in _committed_person_matches(
            deltas, diagram_data
        ).items():
            p = next((dp for dp in deltas.people if dp.id == delta_id), None)
            errors.append(
                f"Delta person {delta_id} '{p.name if p else ''}' "
                f"duplicates committed person {committed_id}"
            )
        errors.extend(_committed_dup_structural_errors(deltas, diagram_data))

    for event in deltas.events:
        if event.id >= 0 and event.id not in committed_event_ids:
            errors.append(
                f"Delta event has positive ID {event.id} not in committed diagram"
            )
        if not event.description and not event.kind.isSelfDescribing():
            errors.append(
                f"Event {event.id} (kind={event.kind.value}) requires description"
            )
        if not event.dateTime:
            errors.append(
                f"Event {event.id} (kind={event.kind.value}) requires dateTime"
            )

    for pair_bond in deltas.pair_bonds:
        if (
            pair_bond.id is not None
            and pair_bond.id >= 0
            and pair_bond.id not in committed_pair_bond_ids
        ):
            errors.append(
                f"Delta pair_bond has positive ID {pair_bond.id} not in committed diagram"
            )

    for event in deltas.events:
        # Offspring and moved events may lack spouse at extraction time; commit logic infers it
        spouse_exempt = event.kind.isOffspring() or event.kind == EventKind.Moved
        if event.kind.isPairBond() and not spouse_exempt and event.spouse is None:
            errors.append(
                f"PairBond event {event.id} (kind={event.kind.value}) requires spouse"
            )

        if (
            event.kind in (EventKind.Birth, EventKind.Adopted)
            and event.person is not None
            and event.child is not None
            and event.person == event.child
        ):
            errors.append(
                f"Event {event.id} (kind={event.kind.value}) has "
                f"person==child=={event.person} (self-reference)"
            )

        if (
            event.person is not None
            and event.person < 0
            and event.person not in all_pdp_person_ids
        ):
            errors.append(
                f"Event {event.id} references non-existent PDP person {event.person}"
            )

        if (
            event.spouse is not None
            and event.spouse < 0
            and event.spouse not in all_pdp_person_ids
        ):
            errors.append(
                f"Event {event.id} references non-existent PDP spouse {event.spouse}"
            )

        if (
            event.child is not None
            and event.child < 0
            and event.child not in all_pdp_person_ids
        ):
            errors.append(
                f"Event {event.id} references non-existent PDP child {event.child}"
            )

        if diagram_data:
            for role in ("person", "spouse", "child"):
                ref = getattr(event, role)
                if ref is not None and ref > 0 and ref not in committed_person_ids:
                    errors.append(
                        f"Event {event.id} references non-existent committed "
                        f"{role} {ref}"
                    )

        for target in event.relationshipTargets:
            if target < 0 and target not in all_pdp_person_ids:
                errors.append(
                    f"Event {event.id} references non-existent PDP relationship target {target}"
                )

        for person_id in event.relationshipTriangles:
            if person_id < 0 and person_id not in all_pdp_person_ids:
                errors.append(
                    f"Event {event.id} references non-existent PDP person {person_id} in triangle"
                )

    for person in deltas.people:
        if (
            person.parents is not None
            and person.parents < 0
            and person.parents not in all_pdp_pair_bond_ids
        ):
            errors.append(
                f"Person {person.id} references non-existent PDP pair_bond {person.parents}"
            )

        dyad = _self_parent_dyad(person, deltas, diagram_data)
        if dyad is not None:
            a, b = dyad
            errors.append(
                f"Person {person.id} parents=PairBond {person.parents} "
                f"contains self (person_a={a}, person_b={b})"
            )

    for pair_bond in deltas.pair_bonds:
        if pair_bond.person_a is None:
            errors.append(f"PairBond {pair_bond.id} has null person_a")
        elif pair_bond.person_a < 0 and pair_bond.person_a not in all_pdp_person_ids:
            errors.append(
                f"PairBond {pair_bond.id} references non-existent PDP person_a {pair_bond.person_a}"
            )
        elif (
            diagram_data
            and pair_bond.person_a > 0
            and pair_bond.person_a not in committed_person_ids
        ):
            errors.append(
                f"PairBond {pair_bond.id} references non-existent committed person_a {pair_bond.person_a}"
            )

        if pair_bond.person_b is None:
            errors.append(f"PairBond {pair_bond.id} has null person_b")
        elif pair_bond.person_b < 0 and pair_bond.person_b not in all_pdp_person_ids:
            errors.append(
                f"PairBond {pair_bond.id} references non-existent PDP person_b {pair_bond.person_b}"
            )
        elif (
            diagram_data
            and pair_bond.person_b > 0
            and pair_bond.person_b not in committed_person_ids
        ):
            errors.append(
                f"PairBond {pair_bond.id} references non-existent committed person_b {pair_bond.person_b}"
            )

    # Check for duplicate dyads within the delta
    seen_dyads: set[tuple[int, int]] = set()
    for pair_bond in deltas.pair_bonds:
        if pair_bond.person_a is not None and pair_bond.person_b is not None:
            dyad = tuple(sorted([pair_bond.person_a, pair_bond.person_b]))
            if dyad in seen_dyads:
                errors.append(
                    f"Delta contains duplicate PairBond {pair_bond.id} for dyad {dyad}"
                )
            seen_dyads.add(dyad)

    # Check that deletes won't orphan surviving events
    if deltas.delete:
        delete_set = set(deltas.delete)
        existing_pdp_event_ids = {e.id for e in pdp.events}
        event_ids_being_deleted = delete_set & existing_pdp_event_ids
        surviving_events = [
            e for e in pdp.events if e.id not in event_ids_being_deleted
        ]
        for event in surviving_events:
            for ref in [event.person, event.spouse, event.child]:
                if ref is not None and ref in delete_set:
                    errors.append(
                        f"Delete of person {ref} would orphan event {event.id}"
                    )
        existing_pdp_person_ids = {p.id for p in pdp.people if p.id is not None}
        surviving_people = [p for p in pdp.people if p.id not in delete_set]
        for person in surviving_people:
            if person.parents is not None and person.parents in delete_set:
                errors.append(
                    f"Delete of pair_bond {person.parents} would orphan person {person.id}"
                )

    if errors:
        if diagram_data and source:
            _export_validation_failure(diagram_data, deltas, errors, source)
        raise PDPValidationError(errors)


def _export_validation_failure(
    diagram_data: DiagramData,
    deltas: PDPDeltas,
    errors: list[str],
    source: str,
) -> None:
    """Export failed validation data to JSON for debugging."""
    from pathlib import Path

    if os.getenv("FLASK_CONFIG") != "development":
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path(f"/tmp/pdp_validation_{source}_{timestamp}.json")

    export_data = {
        "source": source,
        "errors": errors,
        "diagram_data": {
            "pdp": asdict(diagram_data.pdp),
            "people": diagram_data.people,
            "events": diagram_data.events,
            "pair_bonds": diagram_data.pair_bonds,
        },
        "pdp_deltas": asdict(deltas),
    }

    with open(filename, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    _log.warning(f"Exported validation failure to {filename}")


def cleanup_pair_bonds(pdp: PDP) -> PDP:
    pdp = copy.deepcopy(pdp)

    person_ids = {p.id for p in pdp.people if p.id is not None}

    seen_person_pairs: set[tuple[int, int]] = set()
    cleaned_pair_bonds = []

    for pb in pdp.pair_bonds:
        if pb.id is None:
            continue

        # Positive IDs reference committed diagram people (assumed valid)
        person_a_valid = pb.person_a > 0 or pb.person_a in person_ids
        person_b_valid = pb.person_b > 0 or pb.person_b in person_ids
        if not person_a_valid or not person_b_valid:
            _log.debug(
                f"Removing pair bond {pb.id}: references non-existent person "
                f"(person_a={pb.person_a}, person_b={pb.person_b}, valid={person_ids})"
            )
            continue

        person_pair = tuple(sorted([pb.person_a, pb.person_b]))
        if person_pair in seen_person_pairs:
            _log.debug(
                f"Removing duplicate pair bond {pb.id}: "
                f"pair {person_pair} already has a bond"
            )
            continue

        seen_person_pairs.add(person_pair)
        cleaned_pair_bonds.append(pb)

    pdp.pair_bonds = cleaned_pair_bonds
    return pdp


def cumulative(discussion, up_to_statement, auditor_id: str | None = None) -> PDP:
    """
    Build cumulative PDP from discussion statements up to a given statement.

    Args:
        discussion: Discussion object with statements
        up_to_statement: Include statements up to and including this one
        auditor_id: If provided, use auditor's edited_extraction instead of AI pdp_deltas.
                   Pass "AI" or None to use AI extractions.

    Returns:
        PDP with accumulated people, events, pair_bonds (cleaned of invalid/duplicate/orphaned)
    """
    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
    )

    people_by_id = {}
    events_by_id = {}
    pair_bonds_by_id = {}

    # Get auditor feedback if requested
    feedback_by_stmt = {}
    if auditor_id and auditor_id != "AI":
        from btcopilot.training.models import (
            Feedback,
        )  # circular: training.routes.prompts imports pdp

        feedbacks = Feedback.query.filter(
            Feedback.statement_id.in_([s.id for s in sorted_statements]),
            Feedback.auditor_id == auditor_id,
            Feedback.feedback_type == "extraction",
        ).all()
        for fb in feedbacks:
            feedback_by_stmt[fb.statement_id] = fb

    up_to_order = up_to_statement.order or 0
    for stmt in sorted_statements:
        stmt_order = stmt.order or 0
        if stmt_order > up_to_order:
            break

        # Only process Subject statements (where extraction data is stored)
        if not stmt.speaker or stmt.speaker.type != SpeakerType.Subject:
            continue

        # Get deltas from auditor feedback or AI extraction
        deltas_source = None
        if auditor_id and auditor_id != "AI":
            fb = feedback_by_stmt.get(stmt.id)
            if fb and fb.edited_extraction:
                deltas_source = fb.edited_extraction
        elif stmt.pdp_deltas:
            deltas_source = stmt.pdp_deltas

        if not deltas_source:
            continue

        # Parse and accumulate
        for person_data in deltas_source.get("people", []):
            person = from_dict(Person, person_data)
            if person.id:
                people_by_id[person.id] = person

        for event_data in deltas_source.get("events", []):
            event = from_dict(Event, event_data)
            if event.id:
                events_by_id[event.id] = event

        for pb_data in deltas_source.get("pair_bonds", []):
            pair_bond = from_dict(PairBond, pb_data)
            if pair_bond.id:
                pair_bonds_by_id[pair_bond.id] = pair_bond

        # Handle deletes
        for delete_id in deltas_source.get("delete", []):
            people_by_id.pop(delete_id, None)
            events_by_id.pop(delete_id, None)
            pair_bonds_by_id.pop(delete_id, None)

    pdp = PDP()
    pdp.people = list(people_by_id.values())
    pdp.events = list(events_by_id.values())
    pdp.pair_bonds = list(pair_bonds_by_id.values())

    # Clean up invalid, duplicate, and orphaned pair bonds
    pdp = cleanup_pair_bonds(pdp)

    return pdp


MAX_EXTRACTION_RETRIES = 3


async def _extract_and_validate(
    prompt: str,
    diagram_data: DiagramData,
    source: str,
    large: bool = False,
    base_pdp: PDP | None = None,
) -> tuple[PDP, PDPDeltas]:
    """Submit extraction prompt to LLM, validate, retry up to MAX_EXTRACTION_RETRIES on failure."""
    is_dev = os.getenv("FLASK_CONFIG") == "development"
    pdp = base_pdp if base_pdp is not None else diagram_data.pdp
    current_prompt = prompt
    error_history: list[tuple[int, list[str]]] = []

    for attempt in range(1 + MAX_EXTRACTION_RETRIES):
        pdp_deltas = await gemini_structured(
            current_prompt,
            PDPDeltas,
            large=large,
        )

        if is_dev:
            label = "DELTAS" if attempt == 0 else f"RETRY {attempt} DELTAS"
            ai_log.info(f"{label}:\n\n{_pretty_repr(pdp_deltas)}")

        fix_committed_person_duplicates(pdp_deltas, diagram_data)
        fix_unresolved_person_refs(pdp_deltas, pdp, diagram_data)
        try:
            validate_pdp_deltas(pdp, pdp_deltas, diagram_data, source)
            if attempt > 0:
                _log.info(f"PDP extraction succeeded on retry {attempt} ({source})")
            break
        except PDPValidationError as e:
            error_history.append((attempt + 1, e.errors))
            _log.warning(
                f"PDP validation failed ({source}, attempt {attempt + 1}/{1 + MAX_EXTRACTION_RETRIES}): "
                f"{'; '.join(e.errors)}"
            )
            if attempt == MAX_EXTRACTION_RETRIES:
                _log.warning(
                    f"PDP extraction exhausted retries ({source}); applying repair pass"
                )
                reassign_delta_ids(pdp, pdp_deltas)
                dedup_pair_bonds(pdp_deltas)
                fix_birth_event_self_references(pdp_deltas)
                fix_self_parent_references(pdp_deltas, diagram_data)
                try:
                    validate_pdp_deltas(pdp, pdp_deltas, diagram_data, source)
                    _log.warning(
                        f"PDP repair pass succeeded after retry exhaustion ({source})"
                    )
                    break
                except PDPValidationError:
                    raise
            history_lines = []
            for attempt_num, errors in error_history:
                history_lines.append(f"Attempt {attempt_num}:")
                history_lines.extend(f"  - {err}" for err in errors)
            committed_person_ids = sorted(
                p["id"] for p in diagram_data.people if "id" in p
            )
            current_prompt = prompt + DATA_EXTRACTION_CORRECTION.format(
                failed_deltas=json.dumps(asdict(pdp_deltas), indent=2, default=str),
                error_history="\n".join(history_lines),
                committed_person_ids=committed_person_ids,
            )

    new_pdp = apply_deltas(pdp, pdp_deltas)
    if is_dev:
        ai_log.info(f"New PDP: {_pretty_repr(new_pdp)}")
    return new_pdp, pdp_deltas


def _committed_state_for_prompt(diagram_data: DiagramData) -> dict:
    """Extract only committed items for prompt context, with clean serialization."""

    def _clean_datetimes(items):
        cleaned = []
        for item in items:
            clean = dict(item)
            for key in ("dateTime", "endDateTime"):
                v = clean.get(key)
                if v and hasattr(v, "toString"):
                    clean[key] = v.toString("yyyy-MM-dd")
            cleaned.append(clean)
        return cleaned

    return {
        "people": diagram_data.people,
        "events": _clean_datetimes(diagram_data.events),
        "pair_bonds": diagram_data.pair_bonds,
    }


async def _two_pass_extract(
    diagram_data: DiagramData,
    conversation_history: str,
    current_date: str,
    source: str,
    pass2_prompt: str | None = None,
    sarf_review_prompt: str | None = None,
    cursor_nonce: str | None = None,
) -> tuple[PDP, PDPDeltas]:
    """Two-pass extraction: people+structure first, then shifts+SARF.

    cursor_nonce: when set, conversation_history contains the nonced cursor
    marker; append the matching cursor rule so Pass 1 emits items only for
    content after it."""
    _log.info(
        f"PDP {source.upper()} INPUTS:\n"
        f"  conversation_history length: {len(conversation_history)}\n"
        f"  diagram_data.pdp.people: {[p.name for p in diagram_data.pdp.people]}\n"
        f"  diagram_data.pdp.events count: {len(diagram_data.pdp.events)}\n"
        f"  diagram_data.people count: {len(diagram_data.people)}\n"
    )

    # Pass 1: People + PairBonds + Structural Events
    committed_state = _committed_state_for_prompt(diagram_data)
    prompt1 = DATA_EXTRACTION_PASS1_PROMPT.format(
        current_date=current_date
    ) + DATA_EXTRACTION_PASS1_CONTEXT.format(
        diagram_data=json.dumps(committed_state, indent=2, default=str),
        conversation_history=conversation_history,
    )
    if cursor_nonce:
        prompt1 += CURSOR_EXTRACTION_RULE_TEMPLATE.format(nonce=cursor_nonce)
    pass1_pdp, pass1_deltas = await _extract_and_validate(
        prompt1,
        diagram_data,
        f"{source}_pass1",
        large=True,
    )

    # Pass 2: Shift Events + SARF (given Pass 1 output)
    pass1_data = json.dumps(asdict(pass1_pdp), indent=2, default=str)
    committed_shifts = [e for e in diagram_data.events if e.get("kind") == "shift"]
    committed_shift_json = (
        json.dumps(committed_shifts, indent=2, default=str)
        if committed_shifts
        else "None"
    )
    _pass2_prompt = pass2_prompt or DATA_EXTRACTION_PASS2_PROMPT
    prompt2 = _pass2_prompt.format(
        current_date=current_date
    ) + DATA_EXTRACTION_PASS2_CONTEXT.format(
        pass1_data=pass1_data,
        committed_shift_events=committed_shift_json,
        conversation_history=conversation_history,
    )
    pass2_pdp, pass2_deltas = await _extract_and_validate(
        prompt2,
        diagram_data,
        f"{source}_pass2",
        large=True,
        base_pdp=pass1_pdp,
    )

    # Pass 3: SARF review — re-evaluate all SARF variables against operational definitions
    shift_events = [e for e in pass2_pdp.events if e.kind == EventKind.Shift]
    if shift_events:
        events_json = json.dumps(
            [asdict(e) for e in shift_events], indent=2, default=str
        )
        people_json = json.dumps(
            [asdict(p) for p in pass2_pdp.people], indent=2, default=str
        )
        _sarf_review = sarf_review_prompt or SARF_REVIEW_PROMPT
        review_prompt = _sarf_review.format(
            events_json=events_json,
            people_json=people_json,
            conversation_history=conversation_history,
        )
        review_deltas = await gemini_structured(review_prompt, PDPDeltas, large=True)
        reviewed = {e.id: e for e in review_deltas.events}
        for event in pass2_pdp.events:
            if event.id not in reviewed:
                continue
            rev = reviewed[event.id]
            if rev.symptom is not None:
                event.symptom = rev.symptom
            if rev.anxiety is not None:
                event.anxiety = rev.anxiety
            if rev.functioning is not None:
                event.functioning = rev.functioning
            if rev.relationship is not None:
                event.relationship = rev.relationship
                event.relationshipTargets = rev.relationshipTargets
                event.relationshipTriangles = rev.relationshipTriangles

    merged_deltas = PDPDeltas(
        people=pass1_deltas.people + pass2_deltas.people,
        events=pass1_deltas.events + pass2_deltas.events,
        pair_bonds=pass1_deltas.pair_bonds + pass2_deltas.pair_bonds,
        delete=pass1_deltas.delete + pass2_deltas.delete,
    )
    return pass2_pdp, merged_deltas


def _windowed_conversation(discussion) -> tuple[str, str | None]:
    """Conversation text for extraction, windowed by the re-extraction cursor
    once an extraction has been accepted. Returns (text, cursor_nonce); nonce
    is None when no windowing applies. The marker carries a random per-call
    nonce so user/transcript text cannot forge the boundary."""
    cursor = discussion.extracted_through_order
    if cursor is None:
        return discussion.conversation_history(), None
    prior = discussion.conversation_history(up_to_order=cursor + 1)
    ordered = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id or 0))
    tail_stmts = [s for s in ordered if (s.order or 0) > cursor]
    if not tail_stmts:
        return discussion.conversation_history(), None
    tail = "\n".join(
        f"{s.speaker.name if s.speaker else 'Unknown'}: {s.text}" for s in tail_stmts
    )
    nonce = secrets.token_hex(8)
    marker = CURSOR_MARKER_TEMPLATE.format(nonce=nonce)
    return prior + marker + tail, nonce


async def extract_full(
    discussion,
    diagram_data: DiagramData,
    pass2_prompt: str | None = None,
    sarf_review_prompt: str | None = None,
) -> tuple[PDP, PDPDeltas]:
    diagram_data.pdp = PDP()
    reference_date = (
        discussion.discussion_date
        if discussion.discussion_date
        else datetime.now().date()
    )
    conversation, cursor_nonce = _windowed_conversation(discussion)
    return await _two_pass_extract(
        diagram_data,
        conversation,
        reference_date.isoformat(),
        "extract_full",
        pass2_prompt=pass2_prompt,
        sarf_review_prompt=sarf_review_prompt,
        cursor_nonce=cursor_nonce,
    )


async def import_text(
    diagram_data: DiagramData,
    text: str,
    reference_date: date | None = None,
) -> tuple[PDP, PDPDeltas]:
    diagram_data.pdp = PDP()
    if reference_date is None:
        reference_date = datetime.now().date()
    return await _two_pass_extract(
        diagram_data,
        text,
        reference_date.isoformat(),
        "import_text",
    )


def apply_deltas(pdp: PDP, deltas: PDPDeltas) -> PDP:
    is_dev = os.getenv("FLASK_CONFIG") == "development"
    if is_dev:
        _log.debug(f"Pre-PDP:\n\n{_pretty_repr(pdp)}")
        _log.debug(f"Applying deltas:\n\n{_pretty_repr(deltas)}")

    pdp = copy.deepcopy(pdp)

    people_by_id = {item.id: item for item in pdp.people}
    events_by_id = {item.id: item for item in pdp.events}
    pair_bonds_by_id = {item.id: item for item in pdp.pair_bonds}

    # Positive-ID delta items reference committed diagram items — skip them.
    # Only negative-ID items are new PDP items to add.
    def _is_new_pdp_item(item):
        return item.id is not None and item.id < 0

    # Process people deltas
    people_to_update = [
        (item, people_by_id[item.id])
        for item in deltas.people
        if item.id in people_by_id
    ]
    people_to_add = [
        item
        for item in deltas.people
        if item.id not in people_by_id and _is_new_pdp_item(item)
    ]

    # Process event deltas
    events_to_update = [
        (item, events_by_id[item.id])
        for item in deltas.events
        if item.id in events_by_id
    ]
    events_to_add = [
        item
        for item in deltas.events
        if item.id not in events_by_id and _is_new_pdp_item(item)
    ]

    # Process pair_bond deltas
    pair_bonds_to_update = [
        (item, pair_bonds_by_id[item.id])
        for item in deltas.pair_bonds
        if item.id in pair_bonds_by_id
    ]
    pair_bonds_to_add = [
        item
        for item in deltas.pair_bonds
        if item.id not in pair_bonds_by_id and _is_new_pdp_item(item)
    ]

    # Combine updates for processing
    to_update_all = people_to_update + events_to_update + pair_bonds_to_update
    to_add_people = people_to_add
    to_add_events = events_to_add
    to_add_pair_bonds = pair_bonds_to_add
    upserts_applied = []

    for item, existing in to_update_all:
        _log.debug(f"Updating item {item.__class__.__name__}[{item.id}] in PDP: {item}")
        for field in getattr(item, "model_fields_set", set()):
            value = getattr(item, field)
            if hasattr(existing, field):
                setattr(existing, field, value)
            else:
                if item.id in people_by_id:
                    type_name = "Person"
                elif item.id in events_by_id:
                    type_name = "Event"
                else:
                    type_name = "PairBond"
                _log.warning(
                    f"    {type_name} {item.id} has unknown attribute {field}, skipping update."
                )
        upserts_applied.append(item)

    for item in to_add_people:
        _log.debug(f"Adding new person to PDP: {item}")
        pdp.people.append(item)
        upserts_applied.append(item)

    for item in to_add_events:
        _log.debug(f"Adding new event to PDP: {item}")
        pdp.events.append(item)
        upserts_applied.append(item)

    for item in to_add_pair_bonds:
        _log.debug(f"Adding new pair_bond to PDP: {item}")
        pdp.pair_bonds.append(item)
        upserts_applied.append(item)

    # Count committed-item references that were intentionally skipped
    committed_refs = [
        item
        for item in deltas.people + deltas.events + deltas.pair_bonds
        if not _is_new_pdp_item(item)
        and item.id not in people_by_id
        and item.id not in events_by_id
        and item.id not in pair_bonds_by_id
    ]
    expected = (
        len(deltas.people)
        + len(deltas.events)
        + len(deltas.pair_bonds)
        - len(committed_refs)
    )
    assert len(upserts_applied) == expected, (
        f"Failed to apply all upserts ({len(upserts_applied)} applied, {expected} expected, "
        f"{len(committed_refs)} committed refs skipped)"
    )

    to_delete_ids = deltas.delete
    for idx in reversed(range(len(pdp.people))):
        if pdp.people[idx].id in to_delete_ids:
            del pdp.people[idx]

    for idx in reversed(range(len(pdp.events))):
        if pdp.events[idx].id in to_delete_ids:
            del pdp.events[idx]

    for idx in reversed(range(len(pdp.pair_bonds))):
        if pdp.pair_bonds[idx].id in to_delete_ids:
            del pdp.pair_bonds[idx]

    pdp = cleanup_pair_bonds(pdp)

    if is_dev:
        _log.debug(f"Post-PDP:\n\n{_pretty_repr(pdp)}")
    return pdp
