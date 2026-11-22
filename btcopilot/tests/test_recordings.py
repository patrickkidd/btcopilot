"""A recording sent in the chat: the audio goes on to AssemblyAI from this
server, any user who may write to the diagram transcribes, the app suggests
who each speaker is from what was said, and the message carries the
transcript written out as text, stored and read exactly as a text file's
(R-0951 to R-0955, R-0959). AssemblyAI and the model are stood in for here.

Invented names and words only.
"""

import datetime
import io
from decimal import Decimal

import pytest
import requests

import btcopilot
from btcopilot import diagramjson, transcription
from btcopilot.extensions import db
from btcopilot.llmutil import Parsed, Served, Spent
from btcopilot.models import (
    Diagram,
    ModelCall,
    Observation,
    ObservationKind,
    Statement,
    TokenMeter,
)
from btcopilot.models.modelcall import Purpose
from btcopilot.schema import Person, PersonKind, asdict
from btcopilot.speakers import Guess, Guesses, Who
from btcopilot.tests.conftest import Model, csrf_token, said
from btcopilot.tests.test_turnhistory import coach

KEY = "secret-key"
UTTERANCES = [
    {"speaker": "A", "text": "What brings you both in today?"},
    {"speaker": "B", "text": "Hugh and I keep fighting about his mother."},
    {"speaker": "B", "text": "It started when she moved in."},
    {"speaker": "C", "text": "That's not how I remember it, Ada."},
    {"speaker": "A", "text": "Tell me more."},
]
DONE = {
    "status": "completed",
    "utterances": UTTERANCES,
    "speech_model_used": "universal-3-5-pro",
    "audio_duration": 1800,
}


class Answer:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Service:
    """AssemblyAI as this server calls it, each call written down."""

    def __init__(self, body=DONE, deletes=True):
        self.body = body
        self.deletes = deletes
        self.calls = []

    def post(self, url, headers, data=None, json=None):
        self.calls.append(("post", url, headers["authorization"], data.read() if data else json))
        return Answer({"upload_url": "u://1"} if url.endswith("/upload") else {"id": "t1"})

    def get(self, url, headers):
        self.calls.append(("get", url, headers["authorization"], None))
        return Answer(self.body)

    def delete(self, url, headers):
        self.calls.append(("delete", url, headers["authorization"], None))
        if not self.deletes:
            raise requests.ConnectionError("no answer")
        return Answer({})


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", KEY)
    found = Service()
    for verb in ("post", "get", "delete"):
        monkeypatch.setattr(transcription.requests, verb, getattr(found, verb))
    return found


@pytest.fixture
def token(web):
    return csrf_token(web)


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [
        asdict(Person(id=1, name="Ada", last_name="Hale", gender=PersonKind.Female)),
        asdict(Person(id=2, name="Hugh", last_name="Hale", gender=PersonKind.Male)),
    ]
    data.lastItemId = 2
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def form(voices: str, **more) -> dict:
    return {
        "statement": "",
        "transcription": "t1",
        "voices": voices,
        "title": "First meeting",
        "date": "2026-10-12",
        **more,
    }


VOICES = '{"A": {"clinician": true}, "B": {"person_id": 1}, "C": {"person_id": 2}}'


def send(web, token, body: dict):
    return web.post(
        "/app/chat",
        data=body,
        content_type="multipart/form-data",
        headers={"X-CSRFToken": token},
    )


def words(model: Model) -> str:
    return "".join(
        b["text"] for b in model.histories[0][-1]["content"] if b["type"] == "text"
    )


def test_a_user_without_a_professional_licence_transcribes(web, token, service):
    # R-0953, R-0348
    started = web.post(
        "/app/transcriptions",
        data={"audio": (io.BytesIO(b"RIFF"), "uncle.m4a")},
        headers={"X-CSRFToken": token},
    )
    assert started.status_code == 202
    assert started.get_json() == {"id": "t1"}
    assert ("post", transcription.SERVICE + "/upload", KEY, b"RIFF") in service.calls
    asked = next(c for c in service.calls if c[1].endswith("/transcript"))
    assert asked[3]["speaker_labels"] is True


def test_a_user_who_may_only_read_the_diagram_does_not_transcribe(
    web, token, service, test_user, test_user_2
):
    # R-0951
    shared = Diagram(user_id=test_user_2.id, name="Shared", data=diagramjson.dumps({}))
    db.session.add(shared)
    db.session.commit()
    shared.grant_access(test_user, btcopilot.ACCESS_READ_ONLY, _commit=True)
    refused = web.post(
        f"/app/transcriptions?diagram_id={shared.id}",
        data={"audio": (io.BytesIO(b"RIFF"), "uncle.m4a")},
        headers={"X-CSRFToken": token},
    )
    assert refused.status_code == 403
    assert service.calls == []


def test_a_recording_over_the_size_limit_is_refused_and_not_sent(
    web, token, service, monkeypatch
):
    # R-0951
    monkeypatch.setattr(transcription, "MAX_BYTES", 10)
    refused = web.post(
        "/app/transcriptions",
        data={"audio": (io.BytesIO(b"R" * 100), "long.m4a")},
        headers={"X-CSRFToken": token},
    )
    assert refused.status_code == 413
    assert transcription.TOO_BIG in refused.get_data(as_text=True)
    assert service.calls == []


def test_a_finished_transcript_carries_its_length_and_price_and_is_charged_once(
    web, test_user, service
):
    # R-0348
    read = web.get("/app/transcriptions/t1").get_json()
    web.get("/app/transcriptions/t1")
    assert (read["status"], read["audio_seconds"], read["price"]) == ("completed", 1800, 0.115)
    assert [u["speaker"] for u in read["utterances"]] == ["A", "B", "B", "C", "A"]
    rows = ModelCall.query.filter_by(purpose=Purpose.Transcribe).all()
    assert [(r.user_id, r.turn_id, r.model, r.cost_usd) for r in rows] == [
        (test_user.id, "t1", "universal-3-5-pro", Decimal("0.115"))
    ]


@pytest.mark.parametrize(
    "model, seconds", [("universal-3-5-pro", 0.5), ("universal-2", 7200), ("universal-3-5-pro", 61.25)]
)
def test_a_completed_transcript_always_carries_its_length_and_price(
    web, service, model, seconds
):
    # R-0348
    service.body = dict(DONE, speech_model_used=model, audio_duration=seconds)
    read = web.get("/app/transcriptions/t1").get_json()
    assert read["status"] == "completed"
    assert isinstance(read["audio_seconds"], (int, float)) and read["audio_seconds"] == seconds
    assert isinstance(read["price"], float) and read["price"] > 0


def test_the_diagram_the_page_names_is_the_one_checked_and_charged(
    web, token, service, guessed, test_user
):
    # R-0951, R-0348
    other = Diagram(user_id=test_user.id, name="Second", data=diagramjson.dumps({}))
    db.session.add(other)
    db.session.commit()
    other.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, _commit=True)
    guessed.guesses = []
    assert web.get(f"/app/transcriptions/t1?diagram_id={other.id}").status_code == 200
    web.post(
        f"/app/recordings/voices?diagram_id={other.id}",
        json={"utterances": UTTERANCES},
        headers={"X-CSRFToken": token},
    )
    rows = ModelCall.query.filter_by(purpose=Purpose.Transcribe).order_by(ModelCall.id).all()
    assert [r.diagram_id for r in rows] == [other.id, other.id]
    assert other.id != test_user.free_diagram_id


def test_a_transcript_still_running_has_no_length_or_price(web, service):
    # R-0348
    service.body = {"status": "processing", "audio_duration": None}
    read = web.get("/app/transcriptions/t1").get_json()
    assert (read["utterances"], read["audio_seconds"], read["price"]) == (None, None, None)


def test_a_transcription_that_fails_at_assemblyai_is_observed_once(web, service):
    # R-0951
    service.body = {"status": "error", "error": "Audio file has no sound"}
    read = web.get("/app/transcriptions/t1").get_json()
    web.get("/app/transcriptions/t1")
    assert read["error"] == "Audio file has no sound"
    rows = Observation.query.filter_by(turn_id="t1").all()
    assert [(r.kind, r.detail) for r in rows] == [
        (
            ObservationKind.Import,
            {
                "outcome": "not transcribed",
                "transcript": "t1",
                "error": "Audio file has no sound",
            },
        )
    ]


def deletes(service) -> list[str]:
    return [url for verb, url, _, _ in service.calls if verb == "delete"]


def test_a_failed_transcription_is_deleted_at_assemblyai_once(web, service):
    # R-0348
    service.body = {"status": "error", "error": "Audio file has no sound"}
    web.get("/app/transcriptions/t1")
    web.get("/app/transcriptions/t1")
    assert deletes(service) == [transcription.SERVICE + "/transcript/t1"]


def test_a_failed_transcription_whose_delete_fails_is_recorded_and_still_answers(
    web, service
):
    # R-0348
    service.body = {"status": "error", "error": "Audio file has no sound"}
    service.deletes = False
    read = web.get("/app/transcriptions/t1")
    assert read.status_code == 200
    rows = Observation.query.filter_by(turn_id="t1").order_by(Observation.id).all()
    assert [(r.kind, r.detail["outcome"]) for r in rows] == [
        (ObservationKind.Import, "not transcribed"),
        (ObservationKind.Import, "not deleted at AssemblyAI"),
    ]


def test_a_recording_removed_before_it_is_sent_is_deleted_at_assemblyai(
    web, token, service
):
    # R-0348
    gone = web.delete("/app/transcriptions/t1", headers={"X-CSRFToken": token})
    assert (gone.status_code, gone.get_data()) == (204, b"")
    assert deletes(service) == [transcription.SERVICE + "/transcript/t1"]
    assert Observation.query.count() == 0


def test_a_removal_whose_delete_fails_is_recorded_and_still_answers(
    web, token, service, test_user
):
    # R-0348
    service.deletes = False
    gone = web.delete("/app/transcriptions/t1", headers={"X-CSRFToken": token})
    assert gone.status_code == 204
    row = Observation.query.one()
    assert (row.kind, row.turn_id, row.diagram_id) == (
        ObservationKind.Import,
        "t1",
        test_user.free_diagram_id,
    )
    assert row.detail == {
        "outcome": "not deleted at AssemblyAI",
        "transcript": "t1",
        "error": "no answer",
    }


def test_only_a_user_who_may_write_removes_a_recording(
    web, token, service, test_user, test_user_2
):
    # R-0951
    shared = Diagram(user_id=test_user_2.id, name="Shared", data=diagramjson.dumps({}))
    db.session.add(shared)
    db.session.commit()
    shared.grant_access(test_user, btcopilot.ACCESS_READ_ONLY, _commit=True)
    refused = web.delete(
        f"/app/transcriptions/t1?diagram_id={shared.id}", headers={"X-CSRFToken": token}
    )
    assert refused.status_code == 403
    assert deletes(service) == []


def test_the_text_names_a_clinician_and_two_people_and_joins_one_speakers_lines():
    # R-0951, R-0954
    named = transcription.names(
        {"A": {"clinician": True}, "B": {"person_id": 1}, "C": {"person_id": 2}},
        [{"id": 1, "name": "Ada", "last_name": "Hale"}, {"id": 2, "name": "Hugh", "last_name": "Hale"}],
    )
    text = transcription.written(
        UTTERANCES,
        {label: one["name"] for label, one in named.items()},
        "First meeting",
        datetime.date(2026, 10, 12),
    )
    assert text == (
        "Recording: First meeting\n"
        "Recorded on 12 October 2026.\n"
        "Speakers: The clinician, Ada Hale, Hugh Hale.\n\n"
        "The clinician\nWhat brings you both in today?\n\n"
        "Ada Hale\nHugh and I keep fighting about his mother. It started when she moved in.\n\n"
        "Hugh Hale\nThat's not how I remember it, Ada.\n\n"
        "The clinician\nTell me more."
    )


def test_the_text_of_a_recording_with_no_clinician_and_a_typed_name():
    # R-0952, R-0953
    named = transcription.names(
        {"A": {"person_id": 1}, "B": {"name": " Uncle Rory "}},
        [{"id": 1, "name": "Ada", "last_name": None}],
    )
    text = transcription.written(
        [{"speaker": "A", "text": "Where were you born?"}, {"speaker": "B", "text": "Galway."}],
        {label: one["name"] for label, one in named.items()},
        "Rory",
        datetime.date(2026, 3, 1),
    )
    assert text.splitlines()[:3] == [
        "Recording: Rory",
        "Recorded on 1 March 2026.",
        "Speakers: Ada, Uncle Rory.",
    ]
    assert "The clinician" not in text
    assert text.endswith("Ada\nWhere were you born?\n\nUncle Rory\nGalway.")


def test_a_speaker_left_unnamed_or_a_person_not_in_the_diagram_is_refused():
    # R-0951
    with pytest.raises(ValueError):
        transcription.names({"A": {"person_id": 9}}, [{"id": 1, "name": "Ada"}])
    with pytest.raises(ValueError):
        transcription.names({"A": {"name": "  "}}, [])
    with pytest.raises(ValueError):
        transcription.written(UTTERANCES, {"A": "Ada"}, "x", datetime.date(2026, 1, 1))


def test_a_recording_is_stored_as_a_text_files_attachment_and_the_coach_reads_it(
    web, token, service, family, monkeypatch
):
    # R-0954, R-0959
    model = coach(monkeypatch, Model(said("Thank you.")))
    sent = send(web, token, form(VOICES))
    assert sent.status_code == 202, sent.get_data(as_text=True)
    body = sent.get_json()
    stored = Statement.query.filter(Statement.attachment_name.isnot(None)).one()
    assert (body["attachment_name"], stored.attachment_name) == ("First meeting", "First meeting")
    assert stored.attachment_text == body["attachment_text"]
    assert stored.attachment_text.startswith("Recording: First meeting\nRecorded on 12 October 2026.")
    assert words(model).endswith(
        "From the file First meeting (enter every person and every dated event in it, "
        "births too, before you reply):\n" + stored.attachment_text
    )


def test_a_recording_not_yet_transcribed_is_refused_and_nothing_is_stored(
    web, token, service, family
):
    # R-0954
    service.body = {"status": "processing", "audio_duration": None}
    refused = send(web, token, form(VOICES))
    assert refused.status_code == 409
    assert transcription.UNFINISHED in refused.get_data(as_text=True)
    assert Statement.query.count() == 0


def test_assemblyais_copy_is_deleted_after_the_statement_is_stored(
    web, token, service, family, monkeypatch
):
    # R-0348
    coach(monkeypatch, Model(said("Thank you.")))
    send(web, token, form(VOICES))
    assert service.calls[-1] == ("delete", transcription.SERVICE + "/transcript/t1", KEY, None)
    assert Statement.query.filter(Statement.attachment_name.isnot(None)).count() == 1


def test_a_failed_delete_is_observed_and_the_message_still_goes(
    web, token, service, family, monkeypatch
):
    # R-0348
    coach(monkeypatch, Model(said("Thank you.")))
    service.deletes = False
    sent = send(web, token, form(VOICES))
    assert sent.status_code == 202
    rows = Observation.query.filter_by(turn_id=sent.get_json()["turn_id"]).all()
    assert [(r.kind, r.detail["outcome"]) for r in rows] == [
        (ObservationKind.Import, "imported"),
        (ObservationKind.Import, "not deleted at AssemblyAI"),
    ]
    assert (rows[1].detail["transcript"], rows[1].detail["error"]) == ("t1", "no answer")
    assert not Observation.query.filter_by(kind=ObservationKind.TurnFailed).count()


def test_the_import_leaves_one_record_of_who_each_speaker_was_said_to_be(
    web, token, service, family, monkeypatch
):
    # R-0954
    coach(monkeypatch, Model(said("Thank you.")))
    sent = send(web, token, form(VOICES))
    row = Observation.query.filter_by(kind=ObservationKind.Import).one()
    assert (row.turn_id, row.diagram_id) == (sent.get_json()["turn_id"], family.id)
    assert row.detail == {
        "outcome": "imported",
        "title": "First meeting",
        "seconds": 1800,
        "speakers": [
            {"label": "A", "name": "The clinician", "person_id": None},
            {"label": "B", "name": "Ada Hale", "person_id": 1},
            {"label": "C", "name": "Hugh Hale", "person_id": 2},
        ],
    }


@pytest.fixture
def guessed(monkeypatch):
    """The suggestion call, answering with `answer.guesses`; each prompt kept."""

    class Answered:
        guesses: list[Guess] = []
        prompts: list[str] = []

    def call(prompt, response_format, schema=None, limit=None, model=None):
        Answered.prompts.append(prompt)
        return Parsed(
            Guesses(speakers=Answered.guesses),
            Spent(input=900, output=80),
            Served("claude-opus-5-5"),
        )

    monkeypatch.setattr("btcopilot.metered.gemini_structured_sync", call)
    monkeypatch.setattr("btcopilot.speakers.prompts", Prompts)
    return Answered


class Prompts:
    """The private fragment stood in for: CI runs on the open prompts."""

    @staticmethod
    def files():
        return Prompts

    @staticmethod
    def fragment(name):
        return f"<{name}>"


def test_a_suggestion_needs_its_words_in_the_transcript_from_the_speaker_named(
    web, token, family, guessed, test_user
):
    # R-0951
    guessed.guesses = [
        Guess("A", Who.Clinician, None, "What brings you both in today?", "A"),
        Guess("B", Who.Person, 1, "That's not how I remember it, Ada.", "C"),
        Guess("C", Who.Person, 2, "Hugh, you never listen", "B"),
    ]
    voices = web.post(
        "/app/recordings/voices",
        json={"utterances": UTTERANCES},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert [(v["label"], v["said"], v["suggestion"]) for v in voices] == [
        ("A", "What brings you both in today?", {"person_id": None, "because": "What brings you both in today?", "speaker": "A"}),
        ("B", "Hugh and I keep fighting about his mother.", {"person_id": 1, "because": "That's not how I remember it, Ada.", "speaker": "C"}),
        ("C", "That's not how I remember it, Ada.", None),
    ]
    assert "1: Ada Hale" in guessed.prompts[0]
    row = ModelCall.query.filter_by(purpose=Purpose.Transcribe).one()
    assert (row.user_id, row.diagram_id, row.input_tokens) == (test_user.id, family.id, 900)
    meter = TokenMeter.query.filter_by(user_id=test_user.id).one()
    assert (meter.input_tokens, meter.output_tokens) == (900, 80)


def test_a_suggestion_of_someone_not_in_the_diagram_or_of_nobody_is_dropped(
    web, token, family, guessed
):
    # R-0951
    guessed.guesses = [
        Guess("A", Who.Nobody, None, "", ""),
        Guess("B", Who.Person, 7, "Hugh and I keep fighting about his mother.", "B"),
    ]
    voices = web.post(
        "/app/recordings/voices",
        json={"utterances": UTTERANCES},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert [v["suggestion"] for v in voices] == [None, None, None]


def test_the_key_is_in_no_answer(web, token, service, family, guessed, monkeypatch):
    # R-0348
    coach(monkeypatch, Model(said("Thank you.")))
    answers = [
        web.post(
            "/app/transcriptions",
            data={"audio": (io.BytesIO(b"RIFF"), "a.m4a")},
            headers={"X-CSRFToken": token},
        ),
        web.get("/app/transcriptions/t1"),
        web.post(
            "/app/recordings/voices",
            json={"utterances": UTTERANCES},
            headers={"X-CSRFToken": token},
        ),
        send(web, token, form(VOICES)),
        web.get("/app/statements"),
    ]
    assert [a.status_code for a in answers] == [202, 200, 200, 202, 200]
    assert not [a for a in answers if KEY in a.get_data(as_text=True)]


def test_the_old_recording_session_route_is_gone(web, token):
    # R-0959
    gone = web.post("/app/recordings", json={}, headers={"X-CSRFToken": token})
    assert gone.status_code in (404, 405)
