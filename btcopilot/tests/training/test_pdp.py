import logging
import asyncio

import pytest
from mock import patch

from btcopilot.personal import pdp
from btcopilot.personal.pdp import PDP, PDPDeltas
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

    with patch("btcopilot.extensions.llm.submit", return_value={}):
        with patch(
            "btcopilot.personal.pdp.apply_deltas", return_value={"dummy": "data"}
        ):
            returned = asyncio.run(pdp.update(discussion, DiagramData(), "blah blah"))
    assert returned == ({"dummy": "data"}, {})


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
                spouses=[],
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
                spouses=[],
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
