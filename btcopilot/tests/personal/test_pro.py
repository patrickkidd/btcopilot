"""What a professional licence adds: cases, recordings and notes. Everything
here is refused as not-found without the licence, because a reader who does not
have it is never told the surface exists (R-0237, R-0285)."""

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, SpeakerType
from btcopilot.schema import Person, PersonKind, asdict
from btcopilot.tests.personal.conftest import csrf_token

UTTERANCES = [
    {"speaker": "A", "text": "When did your father go down to Arizona, roughly?"},
    {"speaker": "B", "text": "March of 1969. He'd just finished his apprenticeship."},
    {"speaker": "A", "text": "And your mother?"},
]

VOICES = {
    "A": {"type": "expert", "name": "Dr Okafor"},
    "B": {"type": "subject", "name": "Marcus"},
}


@pytest.fixture
def pro(web, test_license):
    return web


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren", gender=PersonKind.Female))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_a_reader_without_the_licence_is_not_professional(web):
    page = web.get("/personal/").get_data(as_text=True)
    assert '"pro": false' in page
    assert web.get("/personal/account").get_json()["pro"] is False


def test_a_licenced_reader_is_professional(pro):
    page = pro.get("/personal/").get_data(as_text=True)
    assert '"pro": true' in page
    assert pro.get("/personal/account").get_json()["pro"] is True


def test_a_case_is_made_and_the_app_is_put_on_it(pro):
    made = pro.post(
        "/personal/diagrams",
        json={"name": "Whitlock"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert made.status_code == 201
    assert made.get_json()["name"] == "Whitlock"
    assert made.get_json()["current"] is True


def test_only_a_professional_makes_a_case(web):
    refused = web.post(
        "/personal/diagrams",
        json={"name": "Whitlock"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_note_is_a_session_of_its_own(pro):
    made = pro.post(
        "/personal/sessions",
        json={"kind": "note"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert made.status_code == 201
    assert made.get_json()["kind"] == "note"


def test_only_a_professional_starts_a_note(web):
    refused = web.post(
        "/personal/sessions",
        json={"kind": "note"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_chat_session_is_still_the_default(web):
    made = web.post("/personal/sessions", headers={"X-CSRFToken": csrf_token(web)})
    assert made.get_json()["kind"] == "chat"


def test_a_recording_cannot_be_started_without_its_transcript(pro):
    refused = pro.post(
        "/personal/sessions",
        json={"kind": "recording"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert refused.status_code == 400


def test_the_voices_of_a_transcript_carry_what_each_first_said(pro):
    voices = pro.post(
        "/personal/recordings/voices",
        json={"utterances": UTTERANCES},
        headers={"X-CSRFToken": csrf_token(pro)},
    ).get_json()
    assert [v["label"] for v in voices] == ["A", "B"]
    assert voices[0]["said"].startswith("When did your father")


def test_a_mapped_recording_reads_as_a_session(pro):
    made = pro.post(
        "/personal/recordings",
        json={
            "utterances": UTTERANCES,
            "voices": VOICES,
            "title": "Session 3 — recording",
            "date": "2024-11-02",
        },
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert made.status_code == 201
    payload = made.get_json()
    assert payload["kind"] == "recording"
    assert payload["date"] == "2024-11-02"
    assert payload["message_count"] == 3
    listed = pro.get("/personal/sessions").get_json()
    assert payload["id"] in [s["id"] for s in listed]


def test_the_clinician_becomes_the_coachs_side_of_the_thread(pro):
    made = pro.post(
        "/personal/recordings",
        json={"utterances": UTTERANCES, "voices": VOICES, "title": "Session 3"},
        headers={"X-CSRFToken": csrf_token(pro)},
    ).get_json()
    discussion = db.session.get(Discussion, made["id"])
    assert discussion.chat_ai_speaker.type == SpeakerType.Expert
    assert discussion.chat_user_speaker.type == SpeakerType.Subject
    thread = pro.get(f"/personal/sessions/{made['id']}").get_json()["statements"]
    assert [s["role"] for s in thread] == ["coach", "user", "coach"]


def test_a_recording_with_no_clinician_is_refused(pro):
    refused = pro.post(
        "/personal/recordings",
        json={
            "utterances": UTTERANCES,
            "voices": {"A": {"type": "subject"}, "B": {"type": "subject"}},
            "title": "Session 3",
        },
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert refused.status_code == 400


def test_only_a_professional_uploads_a_recording(web):
    refused = web.post(
        "/personal/recordings",
        json={"utterances": UTTERANCES, "voices": VOICES, "title": "Session 3"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_person_keeps_notes(web, family):
    changed = web.patch(
        "/personal/people/1",
        json={"notes": "Dates everything from the divorce."},
        headers={"X-CSRFToken": csrf_token(web)},
    ).get_json()
    assert changed["notes"] == "Dates everything from the divorce."
    people = web.get("/personal/timeline").get_json()["people"]
    assert people[0]["notes"] == "Dates everything from the divorce."
