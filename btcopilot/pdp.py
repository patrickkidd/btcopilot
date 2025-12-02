import copy
import logging
import os
from datetime import datetime

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    PDPValidationError,
    Person,
    Event,
    PairBond,
    asdict,
)

_log = logging.getLogger(__name__)


def _pretty_repr(obj):
    try:
        from rich.pretty import pretty_repr

        return pretty_repr(obj)
    except ImportError:
        return repr(obj)


def get_all_pdp_item_ids(pdp: PDP) -> set[int]:
    """Get all item IDs from PDP (people, events, and pair_bonds share ID space)."""
    ids = {p.id for p in pdp.people if p.id is not None}
    ids.update(e.id for e in pdp.events)
    ids.update(pb.id for pb in pdp.pair_bonds if pb.id is not None)
    return ids


def validate_pdp_deltas(pdp: PDP, deltas: PDPDeltas) -> None:
    """
    Validate that deltas can be safely applied to PDP.
    Raises PDPValidationError if validation fails.

    Note: btcopilot only manages PDP. All PDP items must have negative IDs.
    References to positive IDs (FD committed items) are assumed valid.
    """
    errors = []

    existing_pdp_ids = get_all_pdp_item_ids(pdp)
    new_item_ids = {p.id for p in deltas.people if p.id is not None}
    new_item_ids.update(e.id for e in deltas.events)
    new_item_ids.update(pb.id for pb in deltas.pair_bonds if pb.id is not None)

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

    all_pdp_item_ids = existing_pdp_ids | new_item_ids

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

    for pair_bond in deltas.pair_bonds:
        if pair_bond.id is not None and pair_bond.id >= 0:
            errors.append(f"PDP pair_bond must have negative ID, got {pair_bond.id}")

    for event in deltas.events:
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
        raise PDPValidationError(errors)


def cumulative(discussion, up_to_statement) -> PDP:
    cumulative_pdp = PDP()

    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id)
    )

    for stmt in sorted_statements:
        if stmt.id < up_to_statement.id and stmt.pdp_deltas:
            if "people" in stmt.pdp_deltas:
                for person_data in stmt.pdp_deltas["people"]:
                    cumulative_pdp.people.append(Person(**person_data))

            if "events" in stmt.pdp_deltas:
                for event_data in stmt.pdp_deltas["events"]:
                    cumulative_pdp.events.append(Event(**event_data))

            if "pair_bonds" in stmt.pdp_deltas:
                for pair_bond_data in stmt.pdp_deltas["pair_bonds"]:
                    cumulative_pdp.pair_bonds.append(PairBond(**pair_bond_data))

    return cumulative_pdp


async def update(
    discussion, diagram_data: DiagramData, user_message: str
) -> tuple[PDP, PDPDeltas]:
    """
    Compiles prompts, runs llm, and returns both updated PDP and the deltas that were applied.
    """
    from btcopilot.personal.prompts import PDP_ROLE_AND_INSTRUCTIONS, PDP_EXAMPLES

    reference_date = (
        discussion.discussion_date
        if discussion.discussion_date
        else datetime.now().date()
    )

    SYSTEM_PROMPT = f"""

    Current Date: {reference_date.isoformat()}

    {PDP_ROLE_AND_INSTRUCTIONS}

    **Examples:**

    {PDP_EXAMPLES}
    
    **IMPORTANT - CONTEXT FOR DELTA EXTRACTION:**
    
    You are analyzing ONLY the new user statement below for NEW information that
    should be added to or updated in the existing diagram_data. The conversation
    history is provided as context to help you understand references and
    relationships mentioned in the new statement, but do NOT re-extract
    information from previous messages that is already captured in the diagram_data.
    
    **Existing Diagram State (DO NOT RE-EXTRACT THIS DATA):**

    {asdict(diagram_data)}

    **Conversation History (for context only):**

    {discussion.conversation_history()}

    **NEW USER STATEMENT TO ANALYZE FOR DELTAS:**

    {user_message}
    
    **REMINDER:** Return only NEW people, NEW events, or UPDATES to existing
    entries. Do not include existing data that hasn't changed.

    """
    from btcopilot.extensions import llm, LLMFunction, ai_log

    pdp_deltas = await llm.submit(
        LLMFunction.JSON,
        prompt=SYSTEM_PROMPT,
        response_format=PDPDeltas,
    )

    if os.getenv("FLASK_CONFIG") == "development":
        ai_log.info(f"DELTAS:\n\n{_pretty_repr(pdp_deltas)}")

    new_pdp = apply_deltas(diagram_data.pdp, pdp_deltas)
    if os.getenv("FLASK_CONFIG") == "development":
        ai_log.info(f"New PDP: {_pretty_repr(new_pdp)}")
    return new_pdp, pdp_deltas


def apply_deltas(pdp: PDP, deltas: PDPDeltas) -> PDP:
    """
    Return a copy of the pdp with the deltas applied.
    """

    if os.getenv("FLASK_CONFIG") == "development":
        _log.debug(f"Pre-PDP:\n\n{_pretty_repr(pdp)}")

    if os.getenv("FLASK_CONFIG") == "development":
        _log.debug(f"Applying deltas:\n\n{_pretty_repr(deltas)}")

    pdp = copy.deepcopy(pdp)

    # Handle upserts
    # Keep people, events, and pair_bonds separate to avoid ID collisions between different types

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

    # Handle deletes

    to_delete_ids = deltas.delete
    # Edit pdp in place to remove items with ids in to_delete_ids
    for idx in reversed(range(len(pdp.people))):
        if pdp.people[idx].id in to_delete_ids:
            del pdp.people[idx]

    for idx in reversed(range(len(pdp.events))):
        if pdp.events[idx].id in to_delete_ids:
            del pdp.events[idx]

    for idx in reversed(range(len(pdp.pair_bonds))):
        if pdp.pair_bonds[idx].id in to_delete_ids:
            del pdp.pair_bonds[idx]

    if os.getenv("FLASK_CONFIG") == "development":
        _log.debug(f"Post-PDP:\n\n{_pretty_repr(pdp)}")
    return pdp
