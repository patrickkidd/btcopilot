"""
E2E test for Goal 1: Generate → Extract PDP → Accept → View.

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


# Cached extraction data — represents what LLM would return
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
    """Create a diagram + discussion with speakers, ready for chat."""
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
    pdp=asdict(CACHED_PDP),
    response="That sounds like a difficult time. Tell me more about what happened.",
)
def test_e2e_generate_extract_accept_view(test_user, diagram_with_discussion):
    """
    Full Goal 1 chain:
    1. Chat with mocked extraction (simulates synthetic generation)
    2. Verify PDP lands in diagram pickle
    3. Accept all deltas
    4. Verify committed items in diagram
    """
    diagram, discussion = diagram_with_discussion

    # Step 1: Chat — triggers extraction, saves PDP to diagram
    response = ask(discussion, "I lost my job last June and it's been hard on my marriage.")
    db.session.commit()

    assert response.pdp is not None
    assert len(response.pdp.people) == 2
    assert len(response.pdp.events) == 2
    assert len(response.pdp.pair_bonds) == 1

    # Step 2: Verify PDP persisted in diagram pickle
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
    assert len(id_mapping) == 5  # 2 people + 2 events + 1 pair bond
    for old_id, new_id in id_mapping.items():
        assert old_id < 0
        assert new_id > 0

    # Step 4: Verify committed items
    committed_names = [p["name"] for p in diagram_data.people]
    assert "Maria" in committed_names
    assert "Carlos" in committed_names

    committed_descriptions = [e["description"] for e in diagram_data.events]
    assert "Lost job at factory" in committed_descriptions
    assert "Married Carlos" in committed_descriptions

    assert len(diagram_data.pair_bonds) >= 1

    # PDP should be empty after acceptance
    assert len(diagram_data.pdp.people) == 0
    assert len(diagram_data.pdp.events) == 0
    assert len(diagram_data.pdp.pair_bonds) == 0


@pytest.mark.chat_flow(
    pdp=asdict(CACHED_PDP),
    response="Tell me more about your family.",
)
def test_e2e_diagram_load_includes_pdp(subscriber, diagram_with_discussion):
    """Verify GET /diagrams/{id} returns PDP data from pickle."""
    diagram, discussion = diagram_with_discussion

    # Chat to populate PDP in diagram
    ask(discussion, "My marriage has been struggling.")
    db.session.commit()

    # Load diagram via HTTP (simulates Personal app loading)
    response = subscriber.get(f"/personal/diagrams/{diagram.id}")
    assert response.status_code == 200

    data = response.get_json()
    raw = base64.b64decode(data["data"])
    loaded = pickle.loads(raw)

    # Reconstruct PDP same way Diagram.get_diagram_data() does
    pdp_dict = loaded.get("pdp", {})
    pdp = from_dict(PDP, pdp_dict) if pdp_dict else PDP()

    assert len(pdp.people) == 2
    assert len(pdp.events) == 2
    assert pdp.people[0].name == "Maria"


@pytest.mark.chat_flow(
    pdp=asdict(CACHED_PDP),
    response="I understand.",
)
def test_e2e_multi_turn_accumulates_pdp(test_user, diagram_with_discussion):
    """Multiple chat turns accumulate PDP data in diagram."""
    diagram, discussion = diagram_with_discussion

    # Turn 1
    ask(discussion, "I lost my job.")
    db.session.commit()

    db.session.refresh(diagram)
    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 2

    # The chat_flow marker returns the same PDP each time, so
    # turn 2 should still show the same cached PDP (the mock replaces
    # the entire PDP, not appends). This verifies the pipeline doesn't
    # lose data between turns.
    ask(discussion, "My wife is struggling too.")
    db.session.commit()

    db.session.refresh(diagram)
    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.pdp.people) == 2
    assert len(diagram_data.pdp.events) == 2
