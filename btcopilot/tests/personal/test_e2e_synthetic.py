"""
E2E test for Goal 1: Chat → Extract Full → Accept → View.

Uses cached/mock data — no AI calls.
"""

import base64
import pickle

import pytest
from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    DateCertainty,
    asdict,
    from_dict,
)
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Speaker, SpeakerType


CACHED_PDP = PDP(
    people=[
        Person(id=-1, name="Maria", last_name="Garcia"),
        Person(id=-2, name="Carlos", last_name="Garcia"),
    ],
    events=[
        Event(
            id=-3,
            kind=EventKind.Shift,
            person=-1,
            description="Lost job at factory",
            dateTime="2024-06-15",
            dateCertainty=DateCertainty.Approximate,
            symptom="up",
            anxiety="up",
            functioning="down",
        ),
        Event(
            id=-4,
            kind=EventKind.Married,
            person=-1,
            description="Married Carlos",
            dateTime="2018-03-20",
            dateCertainty=DateCertainty.Certain,
        ),
    ],
    pair_bonds=[
        PairBond(id=-5, person_a=-1, person_b=-2),
    ],
)

CACHED_DELTAS = PDPDeltas(
    people=CACHED_PDP.people[:],
    events=CACHED_PDP.events[:],
    pair_bonds=CACHED_PDP.pair_bonds[:],
)


@pytest.fixture
def diagram_with_discussion(test_user):
    diagram = test_user.free_diagram
    diagram_data = diagram.get_diagram_data()
    diagram_data.ensure_chat_defaults()
    diagram.set_diagram_data(diagram_data)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=diagram.id,
        summary="E2E Test Discussion",
    )
    db.session.add(discussion)
    db.session.flush()

    user_speaker = Speaker(
        discussion_id=discussion.id,
        name="Maria",
        type=SpeakerType.Subject,
        person_id=1,
    )
    ai_speaker = Speaker(
        discussion_id=discussion.id,
        name="Coach",
        type=SpeakerType.Expert,
    )
    db.session.add_all([user_speaker, ai_speaker])
    db.session.flush()

    discussion.chat_user_speaker_id = user_speaker.id
    discussion.chat_ai_speaker_id = ai_speaker.id
    db.session.commit()

    return diagram, discussion


@pytest.mark.chat_flow(
    response="That sounds like a difficult time. Tell me more about what happened.",
)
def test_e2e_chat_then_extract(test_user, diagram_with_discussion):
    """
    Full Goal 1 chain:
    1. Chat (no extraction)
    2. extract_full() to populate PDP
    3. Accept all deltas
    4. Verify committed items
    """
    diagram, discussion = diagram_with_discussion

    # Step 1: Chat — no extraction, just conversation
    response = ask(discussion, "I lost my job last June and it's been hard on my marriage.")
    db.session.commit()
    assert response.statement is not None

    # Step 2: extract_full() populates PDP
    with patch(
        "btcopilot.pdp._extract_and_validate",
        AsyncMock(return_value=(CACHED_PDP, CACHED_DELTAS)),
    ):
        from btcopilot.pdp import extract_full
        from btcopilot.async_utils import one_result

        diagram_data = diagram.get_diagram_data()
        new_pdp, _ = one_result(extract_full(discussion, diagram_data))
        diagram_data.pdp = new_pdp
        diagram.set_diagram_data(diagram_data)
        db.session.commit()

    db.session.refresh(diagram)
    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 2
    assert len(diagram_data.pdp.events) == 2
    assert len(diagram_data.pdp.pair_bonds) == 1
    assert diagram_data.pdp.people[0].name == "Maria"

    # Step 3: Accept all deltas
    pdp_ids = (
        [p.id for p in diagram_data.pdp.people]
        + [e.id for e in diagram_data.pdp.events]
        + [pb.id for pb in diagram_data.pdp.pair_bonds]
    )
    id_mapping = diagram_data.commit_pdp_items(pdp_ids)
    assert len(id_mapping) == 5

    # Step 4: Verify committed items
    committed_names = [p["name"] for p in diagram_data.people]
    assert "Maria" in committed_names
    assert "Carlos" in committed_names

    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.pdp.events) == 0
    assert len(diagram_data.pdp.pair_bonds) == 0


@pytest.mark.chat_flow(response="Tell me more about your family.")
def test_e2e_extract_endpoint(subscriber, diagram_with_discussion):
    """Verify POST /discussions/<id>/extract populates PDP."""
    diagram, discussion = diagram_with_discussion

    # Chat first
    ask(discussion, "My marriage has been struggling.")
    db.session.commit()

    # Extract via endpoint
    with patch(
        "btcopilot.pdp.extract_full",
        AsyncMock(return_value=(CACHED_PDP, CACHED_DELTAS)),
    ):
        response = subscriber.post(
            f"/personal/discussions/{discussion.id}/extract",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["people_count"] == 2
    assert data["events_count"] == 2

    # Verify PDP in diagram
    db.session.refresh(diagram)
    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 2
    assert diagram_data.pdp.people[0].name == "Maria"
