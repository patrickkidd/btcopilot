"""The other side of the chat is not a member of the family: it is a speaker in
the transcript and never a person in the record."""

from btcopilot import profile, recordtext
from btcopilot.discussions import open_session, sync_chat_speakers
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, Speaker, SpeakerType
from btcopilot.tests.conftest import csrf_token
from btcopilot.schema import DEFAULT_SUBJECT_NAME, DiagramData


def test_the_coach_is_not_a_person_in_a_new_record():
    # R-0360
    data = DiagramData()
    user_person_id, changed = data.ensure_chat_defaults()

    assert user_person_id == 1
    assert changed
    assert [p["name"] for p in data.people] == ["User"]


def test_the_id_the_coach_used_to_hold_is_never_handed_to_anyone():
    # R-0455
    data = DiagramData()
    data.ensure_chat_defaults()

    assert data.lastItemId == 2


def test_a_new_session_points_the_coach_at_no_person(web):
    # R-0360
    response = web.post(
        "/app/sessions", json={}, headers={"X-CSRFToken": csrf_token(web)}
    )
    assert response.status_code == 201

    discussion = Discussion.query.get(response.get_json()["id"])
    coach = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Expert
    ).one()
    assert coach.person_id is None

    people = discussion.diagram.get_diagram_data().people
    assert "Assistant" not in [p.get("name") for p in people]


def made(web, own: bool):
    """A diagram made from the page, then readied for its first message."""
    made = web.post(
        "/app/diagrams",
        json={"name": "Delgado", "own_family": own},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert made.status_code == 201
    diagram = db.session.get(Diagram, made.get_json()["id"])
    sync_chat_speakers(open_session(web.user, diagram))
    return diagram.get_diagram_data()


def test_a_family_a_human_coach_made_starts_with_its_client_unnamed(web):
    # R-0893
    data = made(web, own=False)
    assert [(p["id"], p["name"]) for p in data.people] == [(1, None)]
    assert profile.own(data)["id"] == 1
    assert profile.missing(data)[0] is profile.Required.FirstName
    assert data.subject_display_name() == DEFAULT_SUBJECT_NAME
    assert "1 unnamed" in recordtext.outline(data, 1, None)


def test_the_makers_own_family_starts_with_them_as_user(web):
    # R-0893
    data = made(web, own=True)
    assert [(p["id"], p["name"]) for p in data.people] == [(1, "User")]
