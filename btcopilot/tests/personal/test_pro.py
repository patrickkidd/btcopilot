"""What a professional licence adds: cases, recordings and notes. Everything
here is refused as not-found without the licence, because a reader who does not
have it is never told the surface exists (R-0237, R-0285)."""

import io

import pytest

from btcopilot.extensions import db
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import Discussion, DiscussionKind, SpeakerType
from btcopilot.personal.prompts import note_register
from btcopilot.schema import Person, PersonKind, asdict
from btcopilot.tests.personal.conftest import Model, csrf_token, said
from btcopilot.personal import transcription

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
    # R-0237
    page = web.get("/app/").get_data(as_text=True)
    assert '"pro": false' in page
    assert web.get("/app/account").get_json()["pro"] is False


def test_a_licenced_reader_is_professional(pro):
    # R-0237
    page = pro.get("/app/").get_data(as_text=True)
    assert '"pro": true' in page
    assert pro.get("/app/account").get_json()["pro"] is True


def test_a_case_is_made_and_the_app_is_put_on_it(pro):
    # R-0285
    made = pro.post(
        "/app/diagrams",
        json={"name": "Whitlock"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert made.status_code == 201
    assert made.get_json()["name"] == "Whitlock"
    assert made.get_json()["current"] is True


def test_only_a_professional_makes_a_case(web):
    # R-0285
    refused = web.post(
        "/app/diagrams",
        json={"name": "Whitlock"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_note_is_a_session_of_its_own(pro):
    # R-0281
    made = pro.post(
        "/app/sessions",
        json={"kind": "note"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert made.status_code == 201
    assert made.get_json()["kind"] == "note"


def test_only_a_professional_starts_a_note(web):
    # R-0243
    refused = web.post(
        "/app/sessions",
        json={"kind": "note"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_chat_session_is_still_the_default(web):
    # R-0281
    made = web.post("/app/sessions", headers={"X-CSRFToken": csrf_token(web)})
    assert made.get_json()["kind"] == "chat"


def test_a_recording_cannot_be_started_without_its_transcript(pro):
    # R-0348
    refused = pro.post(
        "/app/sessions",
        json={"kind": "recording"},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert refused.status_code == 400


def test_the_voices_of_a_transcript_carry_what_each_first_said(pro):
    # R-0281
    voices = pro.post(
        "/app/recordings/voices",
        json={"utterances": UTTERANCES},
        headers={"X-CSRFToken": csrf_token(pro)},
    ).get_json()
    assert [v["label"] for v in voices] == ["A", "B"]
    assert voices[0]["said"].startswith("When did your father")


def test_a_mapped_recording_reads_as_a_session(pro):
    # R-0243
    made = pro.post(
        "/app/recordings",
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
    listed = pro.get("/app/sessions").get_json()
    assert payload["id"] in [s["id"] for s in listed]


def test_the_clinician_becomes_the_coachs_side_of_the_thread(pro):
    # R-0243
    made = pro.post(
        "/app/recordings",
        json={"utterances": UTTERANCES, "voices": VOICES, "title": "Session 3"},
        headers={"X-CSRFToken": csrf_token(pro)},
    ).get_json()
    discussion = db.session.get(Discussion, made["id"])
    assert discussion.chat_ai_speaker.type == SpeakerType.Expert
    assert discussion.chat_user_speaker.type == SpeakerType.Subject
    thread = pro.get(f"/app/sessions/{made['id']}").get_json()["statements"]
    assert [s["role"] for s in thread] == ["coach", "user", "coach"]


def test_a_recording_with_no_clinician_is_refused(pro):
    # R-0243
    refused = pro.post(
        "/app/recordings",
        json={
            "utterances": UTTERANCES,
            "voices": {"A": {"type": "subject"}, "B": {"type": "subject"}},
            "title": "Session 3",
        },
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert refused.status_code == 400


def test_only_a_professional_uploads_a_recording(web):
    # R-0243
    refused = web.post(
        "/app/recordings",
        json={"utterances": UTTERANCES, "voices": VOICES, "title": "Session 3"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert refused.status_code == 404


def test_a_person_keeps_notes(web, family):
    # R-0281
    changed = web.patch(
        "/app/people/1",
        json={"notes": "Dates everything from the divorce."},
        headers={"X-CSRFToken": csrf_token(web)},
    ).get_json()
    assert changed["notes"] == "Dates everything from the divorce."
    people = web.get("/app/timeline").get_json()["people"]
    assert people[0]["notes"] == "Dates everything from the divorce."


@pytest.mark.chat_flow
def test_a_note_tells_the_coach_who_it_is_talking_to(discussion):
    # R-0281
    """A note is the clinician talking about the case after the fact, so the
    coach is told the register it is in; a chat is told nothing extra."""
    model = Model(said("Noted."))
    CoachTurn(discussion, "she never says the word divorce", model=model).run()
    assert note_register() not in model.systems[0]

    discussion.kind = DiscussionKind.Note
    db.session.commit()
    model = Model(said("Noted."))
    CoachTurn(discussion, "she never says the word divorce", model=model).run()
    assert note_register() in model.systems[0]


class Answer:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def test_the_audio_is_sent_on_from_this_server_and_the_key_stays_here(pro, monkeypatch):
    # R-0348
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "secret")
    sent = {}

    def post(url, headers, data=None, json=None):
        sent[url] = (headers["authorization"], data.read() if data else json)
        return Answer({"upload_url": "u://1"} if url.endswith("/upload") else {"id": "t1"})

    monkeypatch.setattr(transcription.requests, "post", post)
    started = pro.post(
        "/app/transcriptions",
        data={"audio": (io.BytesIO(b"RIFF"), "session.wav")},
        headers={"X-CSRFToken": csrf_token(pro)},
    )
    assert started.status_code == 202
    assert started.get_json() == {"id": "t1"}
    assert sent[transcription.SERVICE + "/upload"] == ("secret", b"RIFF")
    assert sent[transcription.SERVICE + "/transcript"][1]["speaker_labels"] is True
    assert "secret" not in started.get_data(as_text=True)


def test_a_finished_transcript_is_read_back_through_this_server(pro, monkeypatch):
    # R-0348
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "secret")
    done = Answer({"status": "completed", "utterances": UTTERANCES})
    monkeypatch.setattr(transcription.requests, "get", lambda url, headers: done)
    read = pro.get("/app/transcriptions/t1").get_json()
    assert read["status"] == "completed"
    assert [u["speaker"] for u in read["utterances"]] == [u["speaker"] for u in UTTERANCES]
