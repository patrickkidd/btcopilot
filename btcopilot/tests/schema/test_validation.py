from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    get_all_pdp_item_ids,
)
from btcopilot.llmutil import (
    dataclass_to_json_schema,
    PDP_SCHEMA_DESCRIPTIONS,
    PDP_FORCE_REQUIRED,
)


def test_get_all_pdp_item_ids():
    pdp = PDP(
        people=[Person(id=-1, name="Bob"), Person(id=-2, name="David")],
        events=[
            Event(id=-3, kind=EventKind.Shift, person=-1),
            Event(id=-4, kind=EventKind.Shift, person=-2),
        ],
    )
    ids = get_all_pdp_item_ids(pdp)
    assert ids == {-1, -2, -3, -4}


def test_dataclass_to_json_schema_force_required():
    """Verify force_required adds fields to required list even if they have defaults."""
    from btcopilot.llmutil import dataclass_to_json_schema

    # Event has description with default=None, so without force_required it's optional
    schema_no_force = dataclass_to_json_schema(Event, {}, {})
    assert "description" not in schema_no_force.get("required", [])
    assert "dateTime" not in schema_no_force.get("required", [])

    # With force_required, these should be in required list
    force_required = {"Event": ["description", "dateTime", "person", "dateCertainty"]}
    schema_with_force = dataclass_to_json_schema(Event, {}, force_required)
    assert "description" in schema_with_force["required"]
    assert "dateTime" in schema_with_force["required"]
    assert "person" in schema_with_force["required"]
    assert "dateCertainty" in schema_with_force["required"]


def test_pdp_deltas_schema_has_event_required_fields():
    """Verify PDPDeltas schema marks Event required fields via PDP_FORCE_REQUIRED."""
    from btcopilot.llmutil import (
        dataclass_to_json_schema,
        PDP_SCHEMA_DESCRIPTIONS,
        PDP_FORCE_REQUIRED,
    )

    schema = dataclass_to_json_schema(
        PDPDeltas, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )

    # Get nested Event schema from events array items
    events_schema = schema["properties"]["events"]["items"]
    event_required = events_schema.get("required", [])

    # id and kind are required by default (no default value in dataclass)
    assert "id" in event_required
    assert "kind" in event_required

    # These are forced required via PDP_FORCE_REQUIRED
    assert "description" in event_required
    assert "dateTime" in event_required
    assert "person" in event_required
    assert "dateCertainty" in event_required


def test_pdp_deltas_schema_has_pair_bond_required_fields():
    schema = dataclass_to_json_schema(
        PDPDeltas, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )
    pb_schema = schema["properties"]["pair_bonds"]["items"]
    pb_required = pb_schema.get("required", [])
    assert "id" in pb_required
    assert "person_a" in pb_required
    assert "person_b" in pb_required


def test_commit_repairs_dangling_parents():
    diagram_data = DiagramData(
        people=[{"id": 1, "name": "User"}],
        events=[],
        pair_bonds=[],
        lastItemId=5,
        pdp=PDP(
            people=[
                Person(id=-1, name="Mom"),
                Person(id=-2, name="Dad"),
                Person(id=-3, name="Child", parents=-99),
            ],
            events=[
                Event(id=-4, kind=EventKind.Shift, person=-1, description="x"),
            ],
            pair_bonds=[],
        ),
    )
    # -99 is dangling (no pair_bond -99 exists)
    # commit should repair it and succeed
    diagram_data.commit_pdp_items([-1, -2, -3, -4])
    # Child's parents should have been cleared
    committed_child = next(
        p for p in diagram_data.people if p.get("name") == "Child"
    )
    assert committed_child["parents"] is None


def test_commit_with_positive_id_people_in_pdp():
    """Positive-ID people in PDP (committed item updates) should not be committed."""
    diagram_data = DiagramData(
        people=[{"id": 1, "name": "User"}],
        events=[],
        pair_bonds=[],
        lastItemId=5,
        pdp=PDP(
            people=[
                Person(id=1, name="User Updated"),
                Person(id=-1, name="New Person"),
            ],
            events=[
                Event(id=-2, kind=EventKind.Shift, person=-1, description="x"),
            ],
        ),
    )
    # Only commit negative IDs
    mapping = diagram_data.commit_pdp_items([-1, -2])
    assert -1 in mapping
    assert -2 in mapping
    assert 1 not in mapping
