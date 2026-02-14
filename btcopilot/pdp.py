import copy
import logging
import os
from datetime import date, datetime

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
)

_log = logging.getLogger(__name__)


def _pretty_repr(obj):
    try:
        from rich.pretty import pretty_repr

        return pretty_repr(obj)
    except ImportError:
        return repr(obj)


def get_all_pdp_item_ids(pdp: PDP) -> set[int]:
    ids = {p.id for p in pdp.people if p.id is not None}
    ids.update(e.id for e in pdp.events)
    ids.update(pb.id for pb in pdp.pair_bonds if pb.id is not None)
    return ids


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

    _log.warning(
        "reassign_delta_ids: LLM produced ID collisions, "
        f"reassigned {len(person_id_map)} people, {len(event_id_map)} events, {len(pair_bond_id_map)} pair_bonds"
    )


def validate_pdp_deltas(
    pdp: PDP,
    deltas: PDPDeltas,
    diagram_data: DiagramData | None = None,
    source: str | None = None,
) -> None:
    """
    Validate that deltas can be safely applied to PDP. Raises PDPValidationError
    if validation fails. Likely remove it in production, we'll see.

    If diagram_data and source are provided, exports debug info before raising.

    Note: btcopilot only manages PDP. All PDP items must have negative IDs.
    References to positive IDs (FD committed items) are assumed valid.
    """
    errors = []

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
        if person.id is not None and person.id >= 0:
            errors.append(f"PDP person must have negative ID, got {person.id}")

    for event in deltas.events:
        if event.id >= 0:
            errors.append(f"PDP event must have negative ID, got {event.id}")
        if not event.description:
            _log.warning(
                f"Event {event.id} (kind={event.kind}) has no description - "
                f"Learn view will show empty text"
            )

    for pair_bond in deltas.pair_bonds:
        if pair_bond.id is not None and pair_bond.id >= 0:
            errors.append(f"PDP pair_bond must have negative ID, got {pair_bond.id}")

    for event in deltas.events:
        # Offspring and moved events may lack spouse at extraction time; commit logic infers it
        spouse_exempt = event.kind.isOffspring() or event.kind == EventKind.Moved
        if event.kind.isPairBond() and not spouse_exempt and event.spouse is None:
            errors.append(
                f"PairBond event {event.id} (kind={event.kind.value}) requires spouse"
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

    for pair_bond in deltas.pair_bonds:
        if (
            pair_bond.person_a is not None
            and pair_bond.person_a < 0
            and pair_bond.person_a not in all_pdp_person_ids
        ):
            errors.append(
                f"PairBond {pair_bond.id} references non-existent PDP person_a {pair_bond.person_a}"
            )

        if (
            pair_bond.person_b is not None
            and pair_bond.person_b < 0
            and pair_bond.person_b not in all_pdp_person_ids
        ):
            errors.append(
                f"PairBond {pair_bond.id} references non-existent PDP person_b {pair_bond.person_b}"
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
    import json
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
    """
    Clean up pair bonds by removing invalid, duplicate, and orphaned entries.

    Removes:
    - Pair bonds referencing non-existent people
    - Duplicate pair bonds (same person pair, keeps first encountered)
    - Orphaned pair bonds (not referenced by any person's parents field)

    Returns:
        New PDP with cleaned pair bonds
    """
    pdp = copy.deepcopy(pdp)

    person_ids = {p.id for p in pdp.people if p.id is not None}
    referenced_pair_bond_ids = {p.parents for p in pdp.people if p.parents is not None}

    seen_person_pairs: set[tuple[int, int]] = set()
    cleaned_pair_bonds = []

    for pb in pdp.pair_bonds:
        if pb.id is None:
            continue

        # Skip if either person doesn't exist in PDP
        # Positive IDs reference committed diagram people (assumed valid)
        person_a_valid = pb.person_a > 0 or pb.person_a in person_ids
        person_b_valid = pb.person_b > 0 or pb.person_b in person_ids
        if not person_a_valid or not person_b_valid:
            _log.debug(
                f"Removing pair bond {pb.id}: references non-existent person "
                f"(person_a={pb.person_a}, person_b={pb.person_b}, valid={person_ids})"
            )
            continue

        # Skip if this person pair already has a bond (dedup)
        person_pair = tuple(sorted([pb.person_a, pb.person_b]))
        if person_pair in seen_person_pairs:
            _log.debug(
                f"Removing duplicate pair bond {pb.id}: "
                f"pair {person_pair} already has a bond"
            )
            continue

        # Skip if no one references this pair bond as parents
        if pb.id not in referenced_pair_bond_ids:
            _log.debug(
                f"Removing orphaned pair bond {pb.id}: "
                f"not referenced by any person's parents field"
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
    from btcopilot.personal.models import SpeakerType

    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id or 0)
    )

    people_by_id = {}
    events_by_id = {}
    pair_bonds_by_id = {}

    # Get auditor feedback if requested
    feedback_by_stmt = {}
    if auditor_id and auditor_id != "AI":
        from btcopilot.training.models import Feedback

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
) -> tuple[PDP, PDPDeltas]:
    """Submit extraction prompt to LLM, validate, retry up to MAX_EXTRACTION_RETRIES on failure."""
    import json
    from btcopilot.personal.prompts import DATA_EXTRACTION_CORRECTION
    from btcopilot.extensions import llm, LLMFunction, ai_log

    is_dev = os.getenv("FLASK_CONFIG") == "development"
    pdp = diagram_data.pdp
    current_prompt = prompt
    error_history: list[tuple[int, list[str]]] = []

    for attempt in range(1 + MAX_EXTRACTION_RETRIES):
        pdp_deltas = await llm.submit(
            LLMFunction.JSON,
            prompt=current_prompt,
            response_format=PDPDeltas,
            large=large,
        )

        if is_dev:
            label = "DELTAS" if attempt == 0 else f"RETRY {attempt} DELTAS"
            ai_log.info(f"{label}:\n\n{_pretty_repr(pdp_deltas)}")

        reassign_delta_ids(pdp, pdp_deltas)
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
                raise
            history_lines = []
            for attempt_num, errors in error_history:
                history_lines.append(f"Attempt {attempt_num}:")
                history_lines.extend(f"  - {err}" for err in errors)
            current_prompt = prompt + DATA_EXTRACTION_CORRECTION.format(
                failed_deltas=json.dumps(asdict(pdp_deltas), indent=2, default=str),
                error_history="\n".join(history_lines),
            )

    new_pdp = apply_deltas(pdp, pdp_deltas)
    if is_dev:
        ai_log.info(f"New PDP: {_pretty_repr(new_pdp)}")
    return new_pdp, pdp_deltas


async def import_text(
    diagram_data: DiagramData,
    text: str,
    reference_date: date | None = None,
) -> tuple[PDP, PDPDeltas]:
    from btcopilot.personal.prompts import (
        DATA_EXTRACTION_PROMPT,
        DATA_EXTRACTION_EXAMPLES,
        DATA_IMPORT_CONTEXT,
    )

    if reference_date is None:
        reference_date = datetime.now().date()

    _log.info(
        f"PDP IMPORT_TEXT INPUTS:\n"
        f"  text length: {len(text)}\n"
        f"  diagram_data.pdp.people: {[p.name for p in diagram_data.pdp.people]}\n"
        f"  diagram_data.pdp.events count: {len(diagram_data.pdp.events)}\n"
        f"  diagram_data.people count: {len(diagram_data.people)}\n"
    )

    prompt = (
        DATA_EXTRACTION_PROMPT.format(current_date=reference_date.isoformat())
        + DATA_EXTRACTION_EXAMPLES
        + DATA_IMPORT_CONTEXT.format(
            diagram_data=asdict(diagram_data),
            text_chunk=text,
            chunk_num=1,
            total_chunks=1,
        )
    )
    return await _extract_and_validate(prompt, diagram_data, "import_text", large=True)


async def update(
    discussion,
    diagram_data: DiagramData,
    user_message: str,
    up_to_order: int | None = None,
) -> tuple[PDP, PDPDeltas]:
    """
    Extract PDP deltas from a user message.

    Args:
        discussion: The Discussion object
        diagram_data: Current diagram data with PDP context
        user_message: The statement text to extract from
        up_to_order: If provided, only include conversation history up to this order.
                    Used during batch extraction to avoid seeing future statements.
    """
    from btcopilot.personal.prompts import (
        DATA_EXTRACTION_PROMPT,
        DATA_EXTRACTION_EXAMPLES,
        DATA_EXTRACTION_CONTEXT,
    )

    reference_date = (
        discussion.discussion_date
        if discussion.discussion_date
        else datetime.now().date()
    )

    conversation_history = discussion.conversation_history(up_to_order)

    _log.info(
        f"PDP UPDATE INPUTS:\n"
        f"  up_to_order: {up_to_order}\n"
        f"  user_message length: {len(user_message)}\n"
        f"  conversation_history length: {len(conversation_history)}\n"
        f"  diagram_data.pdp.people: {[p.name for p in diagram_data.pdp.people]}\n"
        f"  diagram_data.pdp.events count: {len(diagram_data.pdp.events)}\n"
        f"  diagram_data.people count: {len(diagram_data.people)}\n"
    )

    prompt = (
        DATA_EXTRACTION_PROMPT.format(current_date=reference_date.isoformat())
        + DATA_EXTRACTION_EXAMPLES
        + DATA_EXTRACTION_CONTEXT.format(
            diagram_data=asdict(diagram_data),
            conversation_history=conversation_history,
            user_message=user_message,
        )
    )
    return await _extract_and_validate(prompt, diagram_data, "update")


def apply_deltas(pdp: PDP, deltas: PDPDeltas) -> PDP:
    is_dev = os.getenv("FLASK_CONFIG") == "development"
    if is_dev:
        _log.debug(f"Pre-PDP:\n\n{_pretty_repr(pdp)}")
        _log.debug(f"Applying deltas:\n\n{_pretty_repr(deltas)}")

    pdp = copy.deepcopy(pdp)

    people_by_id = {item.id: item for item in pdp.people}
    events_by_id = {item.id: item for item in pdp.events}
    pair_bonds_by_id = {item.id: item for item in pdp.pair_bonds}

    # Process people deltas
    people_to_update = [
        (item, people_by_id[item.id])
        for item in deltas.people
        if item.id in people_by_id
    ]
    people_to_add = [item for item in deltas.people if item.id not in people_by_id]

    # Process event deltas
    events_to_update = [
        (item, events_by_id[item.id])
        for item in deltas.events
        if item.id in events_by_id
    ]
    events_to_add = [item for item in deltas.events if item.id not in events_by_id]

    # Process pair_bond deltas
    pair_bonds_to_update = [
        (item, pair_bonds_by_id[item.id])
        for item in deltas.pair_bonds
        if item.id in pair_bonds_by_id
    ]
    pair_bonds_to_add = [
        item for item in deltas.pair_bonds if item.id not in pair_bonds_by_id
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

    combined_upserts = deltas.people + deltas.events + deltas.pair_bonds
    assert len(upserts_applied) == len(
        combined_upserts
    ), f"Failed to apply all upserts ({len(upserts_applied)} applied, {len(combined_upserts)} expected)"

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

    if is_dev:
        _log.debug(f"Post-PDP:\n\n{_pretty_repr(pdp)}")
    return pdp
