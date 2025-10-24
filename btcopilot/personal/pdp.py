import copy
import logging

from rich.pretty import pretty_repr

from btcopilot.extensions import llm, LLMFunction, ai_log
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
)
from btcopilot.personal.prompts import PDP_ROLE_AND_INSTRUCTIONS, PDP_EXAMPLES
from datetime import datetime


_log = logging.getLogger(__name__)


def cumulative(discussion: Discussion, up_to_statement: Statement) -> PDP:
    cumulative_pdp = PDP()

    sorted_statements = sorted(
        discussion.statements, key=lambda s: (s.order or 0, s.id)
    )

    for stmt in sorted_statements:
        if stmt.id < up_to_statement.id and stmt.pdp_deltas:
            # Add people from this statement's deltas
            if "people" in stmt.pdp_deltas:
                for person_data in stmt.pdp_deltas["people"]:
                    person = (
                        Person(**person_data)
                        if isinstance(person_data, dict)
                        else person_data
                    )
                    cumulative_pdp.people.append(person)

            # Add events from this statement's deltas
            if "events" in stmt.pdp_deltas:
                for event_data in stmt.pdp_deltas["events"]:
                    event = (
                        Event(**event_data)
                        if isinstance(event_data, dict)
                        else event_data
                    )
                    cumulative_pdp.events.append(event)

    return cumulative_pdp


async def update(
    thread: Discussion, diagram_data: DiagramData, user_message: str
) -> tuple[PDP, PDPDeltas]:
    """
    Compiles prompts, runs llm, and returns both updated PDP and the deltas that were applied.
    """

    SYSTEM_PROMPT = f"""

    Current Date & Time: {datetime.now().isoformat()}

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

    {diagram_data.model_dump()}

    **Conversation History (for context only):**

    {thread.conversation_history()}

    **NEW USER STATEMENT TO ANALYZE FOR DELTAS:**

    {user_message}
    
    **REMINDER:** Return only NEW people, NEW events, or UPDATES to existing
    entries. Do not include existing data that hasn't changed.

    """

    pdp_deltas = await llm.submit(
        LLMFunction.JSON,
        prompt=SYSTEM_PROMPT,
        response_format=PDPDeltas,
    )

    ai_log.info(f"DELTAS:\n\n{pretty_repr(pdp_deltas)}")

    new_pdp = apply_deltas(diagram_data.pdp, pdp_deltas)
    ai_log.info(f"New PDP: {pretty_repr(new_pdp)}")
    return new_pdp, pdp_deltas


def apply_deltas(pdp: PDP, deltas: PDPDeltas) -> PDP:
    """
    Return a copy of the pdp with the deltas applied.
    """

    _log.debug(f"Pre-PDP:\n\n{pretty_repr(pdp)}")

    _log.debug(f"Applying deltas:\n\n{pretty_repr(deltas)}")

    pdp = copy.deepcopy(pdp)

    # Handle upserts
    # Keep people and events separate to avoid ID collisions between different types

    people_by_id = {item.id: item for item in pdp.people}
    events_by_id = {item.id: item for item in pdp.events}

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

    # Combine updates for processing
    to_update_all = people_to_update + events_to_update
    to_add_people = people_to_add
    to_add_events = events_to_add
    upserts_applied = []

    for item, existing in to_update_all:
        _log.debug(f"Updating item {item.__class__.__name__}[{item.id}] in PDP: {item}")
        for field in getattr(item, "model_fields_set", set()):
            value = getattr(item, field)
            if hasattr(existing, field):
                setattr(existing, field, value)
            else:
                type_name = "Person" if item.id in people_by_id else "Event"
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

    combined_upserts = deltas.people + deltas.events
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

    _log.debug(f"Post-PDP:\n\n{pretty_repr(pdp)}")
    return pdp
