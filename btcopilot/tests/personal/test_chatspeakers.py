"""The other side of the chat is not a member of the family: it is a speaker in
the transcript and never a person in the record."""

from btcopilot.personal.models import Discussion, Speaker, SpeakerType
from btcopilot.schema import DiagramData


def test_the_coach_is_not_a_person_in_a_new_record():
    data = DiagramData()
    user_person_id, changed = data.ensure_chat_defaults()

    assert user_person_id == 1
    assert changed
    assert [p["name"] for p in data.people] == ["User"]


def test_the_id_the_coach_used_to_hold_is_never_handed_to_anyone():
    data = DiagramData()
    data.ensure_chat_defaults()

    assert data.lastItemId == 2


def test_a_new_session_points_the_coach_at_no_person(subscriber):
    response = subscriber.post("/personal/discussions/", json={})
    assert response.status_code == 200

    discussion = Discussion.query.get(response.get_json()["id"])
    coach = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Expert
    ).one()
    assert coach.person_id is None

    people = discussion.diagram.get_diagram_data().people
    assert "Assistant" not in [p.get("name") for p in people]
