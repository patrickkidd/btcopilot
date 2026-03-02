import logging
import asyncio

import pytest
from mock import patch

from btcopilot import pdp
from btcopilot.schema import PDP, PDPDeltas, PairBond
from btcopilot.schema import (
    DiagramData,
    VariableShift,
    RelationshipKind,
    EventKind,
    Person,
    Event,
)
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType

_log = logging.getLogger(__name__)


def test_update(test_user):

    discussion = Discussion(
        user=test_user,
        statements=[
            Statement(
                text="Hello, how are you?", speaker=Speaker(type=SpeakerType.Subject)
            ),
            Statement(
                text="I'm fine, thank you!", speaker=Speaker(type=SpeakerType.Expert)
            ),
        ],
    )

    deltas = PDPDeltas()
    with patch("btcopilot.pdp.gemini_structured", return_value=deltas):
        with patch("btcopilot.pdp.apply_deltas", return_value={"dummy": "data"}):
            returned = asyncio.run(pdp.update(discussion, DiagramData(), "blah blah"))
    assert returned == ({"dummy": "data"}, deltas)


# Test case 1: Update existing person and add events with anxiety and conflict
TEST_ADD_PERSON_AND_CONFLICT = {
    "pre_pdp": PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        events=[
            Event(
                id=-3,
                kind=EventKind.Shift,
                person=-1,
                description="Conversation between Alice and Bob",
                dateTime="2023-08-01T12:00:00Z",
            ),
        ],
    ),
    "deltas": PDPDeltas(
        people=[
            Person(id=-4, name="Mother"),
        ],
        events=[
            Event(
                id=-5,
                kind=EventKind.Shift,
                person=-1,
                description="Felt anxious after being yelled at by mother",
                dateTime="the other day",
                anxiety=VariableShift.Up,
            ),
            Event(
                id=-6,
                kind=EventKind.Shift,
                person=-1,
                description="I fought with my husband yesterday",
                dateTime="today",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-2],
            ),
        ],
    ),
    "expected_pdp": PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
            Person(id=-4, name="Mother"),
        ],
        events=[
            Event(
                id=-3,
                person=-1,
                kind=EventKind.Shift,
                description="Conversation between Alice and Bob",
                dateTime="2023-08-01T12:00:00Z",
            ),
            Event(
                id=-5,
                person=-1,
                kind=EventKind.Shift,
                description="Felt anxious after being yelled at by mother",
                dateTime="the other day",
                anxiety=VariableShift.Up,
            ),
            Event(
                id=-6,
                kind=EventKind.Shift,
                person=-1,
                description="I fought with my husband yesterday",
                dateTime="today",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-2],
            ),
        ],
    ),
}

TEST_ADD_PERSON_AND_EVENT_WITH_CONFLICT = {
    "pre_pdp": PDP(
        people=[
            Person(id=-1, name="Alice"),
        ],
        events=[
            Event(
                kind=EventKind.Shift,
                id=-2,
                description="Conversation between Alice and Bob",
                dateTime="2023-08-01T12:00:00Z",
            )
        ],
    ),
    "deltas": PDPDeltas(
        people=[
            Person(
                id=-3,
                name="Brother-in-law",
                confidence=0.6,
            ),
        ],
        events=[
            Event(
                id=-4,
                kind=EventKind.Shift,
                dateTime="2025-03-01",
                person=-3,
                description="Had a run-in over spring break",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-3],
            ),
        ],
    ),
    "expected_pdp": PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-3, name="Brother-in-law", confidence=0.6),
        ],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                description="Conversation between Alice and Bob",
                dateTime="2023-08-01T12:00:00Z",
            ),
            Event(
                id=-4,
                kind=EventKind.Shift,
                description="Had a run-in over spring break",
                person=-3,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-3],
                dateTime="2025-03-01",
            ),
        ],
    ),
}

TEST_ADD_PERSON_AND_CONFLICT_2 = {
    "pre_pdp": PDP(),
    "deltas": PDPDeltas(
        people=[
            Person(
                id=-2,
                name="Mother",
                confidence=0.99,
            )
        ],
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                description="Had a run-in with mother last christmas.",
                dateTime="2022-12-25",
                person=-2,
                symptom=None,
                anxiety=None,
                functioning=None,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-2],
                confidence=0.85,
            )
        ],
        delete=[],
    ),
    "expected_pdp": PDP(
        people=[
            Person(
                id=-2,
                name="Mother",
                confidence=0.99,
            ),
        ],
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                description="Had a run-in with mother last christmas.",
                dateTime="2022-12-25",
                person=-2,
                symptom=None,
                anxiety=None,
                functioning=None,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-2],
                confidence=0.85,
            )
        ],
    ),
}


@pytest.mark.parametrize(
    "data",
    [
        TEST_ADD_PERSON_AND_CONFLICT,
        TEST_ADD_PERSON_AND_CONFLICT_2,
        TEST_ADD_PERSON_AND_EVENT_WITH_CONFLICT,
    ],
    ids=[
        "add_person_and_conflict",
        "add_person_and_conflict_2",
        "add_person_and_event_with_conflict",
    ],
)
def test_apply_deltas(data):
    assert NotImplementedError
    returned = pdp.apply_deltas(data["pre_pdp"], data["deltas"])
    assert returned == data["expected_pdp"]


def test_cleanup_pair_bonds_removes_invalid_refs():
    input_pdp = PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        pair_bonds=[
            PairBond(id=-10, person_a=-1, person_b=-2),  # valid
            PairBond(id=-11, person_a=-1, person_b=-99),  # invalid: -99 doesn't exist
            PairBond(id=-12, person_a=-98, person_b=-2),  # invalid: -98 doesn't exist
        ],
    )

    result = pdp.cleanup_pair_bonds(input_pdp)

    assert len(result.pair_bonds) == 1
    assert result.pair_bonds[0].id == -10


def test_cleanup_pair_bonds_removes_duplicates():
    input_pdp = PDP(
        people=[
            Person(id=-1, name="Alice", parents=-10),
            Person(id=-2, name="Bob"),
            Person(id=-3, name="Child", parents=-11),
        ],
        pair_bonds=[
            PairBond(id=-10, person_a=-1, person_b=-2),  # first bond
            PairBond(id=-11, person_a=-2, person_b=-1),  # duplicate (reversed order)
        ],
    )

    result = pdp.cleanup_pair_bonds(input_pdp)

    assert len(result.pair_bonds) == 1
    assert result.pair_bonds[0].id == -10  # keeps first encountered


def test_cleanup_pair_bonds_keeps_unreferenced():
    input_pdp = PDP(
        people=[
            Person(id=-1, name="Alice"),
            Person(id=-2, name="Bob"),
        ],
        pair_bonds=[
            PairBond(id=-10, person_a=-1, person_b=-2),
        ],
    )

    result = pdp.cleanup_pair_bonds(input_pdp)

    assert len(result.pair_bonds) == 1
    assert result.pair_bonds[0].id == -10


def test_cleanup_pair_bonds_preserves_valid():
    input_pdp = PDP(
        people=[
            Person(id=-1, name="Father"),
            Person(id=-2, name="Mother"),
            Person(id=-3, name="Child", parents=-10),
            Person(id=-4, name="GrandFather"),
            Person(id=-5, name="GrandMother"),
        ],
        pair_bonds=[
            PairBond(id=-10, person_a=-1, person_b=-2),  # parents of child
        ],
    )
    # Add grandparent bond
    input_pdp.people[0].parents = -11
    input_pdp.pair_bonds.append(PairBond(id=-11, person_a=-4, person_b=-5))

    result = pdp.cleanup_pair_bonds(input_pdp)

    assert len(result.pair_bonds) == 2
    pair_bond_ids = {pb.id for pb in result.pair_bonds}
    assert pair_bond_ids == {-10, -11}
