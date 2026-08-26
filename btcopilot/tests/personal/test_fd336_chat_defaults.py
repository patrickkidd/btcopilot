"""FD-336 item 2: the User/Assistant chat placeholders are injected only into
the caller's free diagram, never into a real case file."""

import pickle

import pytest
from mock import patch, AsyncMock

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, SpeakerType
from btcopilot.pro.models import Diagram
from btcopilot.schema import PDP, PDPDeltas, Person, DEFAULT_SUBJECT_NAME

CASE_PEOPLE = [
    {"id": 10, "name": "Connie", "lastName": "Stinson", "gender": "female"},
    {"id": 11, "name": "Roger", "lastName": "Stinson", "gender": "male"},
    {"id": 12, "name": "Patrick", "lastName": "Stinson", "gender": "male"},
]
CASE_EVENTS = [{"id": 2, "kind": "shift", "person": 10, "description": "moved out"}]


def _case_diagram(user):
    diagram = Diagram(
        user_id=user.id,
        name="Case File",
        data=pickle.dumps(
            {
                "people": [dict(p) for p in CASE_PEOPLE],
                "events": [dict(e) for e in CASE_EVENTS],
                "pair_bonds": [],
                "lastItemId": 12,
            }
        ),
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _legacy_free_diagram(user):
    """A free diagram seeded before the placeholder carried a primary flag."""
    diagram = user.free_diagram
    diagram.data = pickle.dumps(
        {
            "people": [{"id": 1, "name": "User"}, {"id": 2, "name": "Assistant"}],
            "events": [],
            "pair_bonds": [],
            "lastItemId": 2,
        }
    )
    db.session.commit()
    return diagram


def _discussion(user, diagram):
    discussion = Discussion(
        user_id=user.id,
        diagram_id=diagram.id,
        speakers=[
            Speaker(name=DEFAULT_SUBJECT_NAME, type=SpeakerType.Subject),
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(discussion)
    db.session.flush()
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    discussion.chat_ai_speaker_id = discussion.speakers[1].id
    db.session.commit()
    return discussion


def _user_less_discussion(user, diagram):
    """The familydiagram test app creates discussions with no user_id."""
    discussion = _discussion(user, diagram)
    discussion.user_id = None
    db.session.commit()
    return discussion


def _chat(client, discussion):
    return client.post(
        f"/personal/discussions/{discussion.id}/statements",
        json={"statement": "Hello"},
    )


@pytest.mark.chat_flow
def test_chat_leaves_a_case_file_structure_untouched(subscriber):
    diagram = _case_diagram(subscriber.user)
    discussion = _discussion(subscriber.user, diagram)

    _chat(subscriber, discussion)

    data = Diagram.query.get(diagram.id).get_diagram_data()
    assert data.people == CASE_PEOPLE
    assert data.events == CASE_EVENTS
    assert data.lastItemId == 12


@pytest.mark.chat_flow
def test_chat_does_not_write_the_case_file_row(subscriber):
    diagram = _case_diagram(subscriber.user)
    discussion = _discussion(subscriber.user, diagram)
    version = diagram.version

    _chat(subscriber, discussion)
    assert Diagram.query.get(diagram.id).version == version


@pytest.mark.chat_flow
def test_chat_still_seeds_the_free_diagram(subscriber):
    diagram = subscriber.user.free_diagram
    discussion = _discussion(subscriber.user, diagram)

    _chat(subscriber, discussion)

    people = {
        p["id"]: p for p in Diagram.query.get(diagram.id).get_diagram_data().people
    }
    assert people[1]["name"] == "User"
    assert people[1]["primary"] is True
    assert people[2]["name"] == "Assistant"


@pytest.mark.chat_flow
def test_chat_heals_a_legacy_free_diagram_placeholder(subscriber):
    diagram = _legacy_free_diagram(subscriber.user)
    discussion = _discussion(subscriber.user, diagram)
    version = diagram.version

    _chat(subscriber, discussion)

    people = Diagram.query.get(diagram.id).get_diagram_data().people
    placeholders = [p for p in people if p["id"] == 1]
    assert len(placeholders) == 1
    assert placeholders[0].get("primary") is True
    assert Diagram.query.get(diagram.id).version == version + 1


@pytest.mark.chat_flow
def test_chat_on_a_user_less_discussion_keys_defaults_off_the_caller(subscriber):
    free_diagram = subscriber.user.free_diagram
    free_discussion = _user_less_discussion(subscriber.user, free_diagram)

    assert _chat(subscriber, free_discussion).status_code == 200

    people = {
        p["id"]: p for p in Diagram.query.get(free_diagram.id).get_diagram_data().people
    }
    assert people[1]["name"] == "User"
    assert people[2]["name"] == "Assistant"

    case_diagram = _case_diagram(subscriber.user)
    case_discussion = _user_less_discussion(subscriber.user, case_diagram)

    assert _chat(subscriber, case_discussion).status_code == 200
    assert Diagram.query.get(case_diagram.id).get_diagram_data().people == CASE_PEOPLE


def test_import_text_leaves_a_case_file_structure_untouched(subscriber):
    diagram = _case_diagram(subscriber.user)
    extracted = PDP(people=[Person(id=-1, name="Mom")])

    with patch(
        "btcopilot.pdp.import_text",
        AsyncMock(return_value=(extracted, PDPDeltas(people=extracted.people))),
    ):
        response = subscriber.post(
            f"/personal/diagrams/{diagram.id}/import-text",
            json={"text": "Mom called about money."},
        )
    assert response.status_code == 200

    data = Diagram.query.get(diagram.id).get_diagram_data()
    assert data.people == CASE_PEOPLE
    assert [p.name for p in data.pdp.people] == ["Mom"]
