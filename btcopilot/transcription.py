"""Transcribing a recording at AssemblyAI, from this server. The browser never
holds the account key (R-0348): the audio comes here and goes on, the
transcript is read back through here, and once a message carries it the
transcript is written out as the message's attachment text, the way a text
file's is (R-0954, R-0959), and deleted at AssemblyAI."""

import datetime
import enum
import json
import os

import requests
from werkzeug.exceptions import Conflict

from btcopilot.attachments import Written
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import Diagram, Observation, ObservationKind
from btcopilot.models.modelcall import ModelCall, Purpose
from btcopilot.pricing import heard

SERVICE = "https://api.assemblyai.com/v2"
# Names another address, such as a stand-in for AssemblyAI on a sandbox.
ADDRESS = "ASSEMBLYAI_URL"
MAX_BYTES = 500 * 1024 * 1024
TOO_BIG = "That recording is over 500 MB; the app takes recordings up to 500 MB."
UNFINISHED = "That recording is not transcribed yet."
CLINICIAN = "The clinician"


class NotConfigured(ValueError):
    """No transcription key on this server, said where the reader can see it."""


class Outcome(enum.StrEnum):
    """How a recording's import ended, in its import record."""

    Imported = "imported"
    Untranscribed = "not transcribed"
    Undeleted = "not deleted at AssemblyAI"


class Status(enum.StrEnum):
    Queued = "queued"
    Processing = "processing"
    Completed = "completed"
    Error = "error"


def _key() -> str:
    key = os.getenv("ASSEMBLYAI_API_KEY")
    if not key:
        raise NotConfigured("Transcription is not configured on this server")
    return key


def _service() -> str:
    return os.getenv(ADDRESS, SERVICE)


def _headers() -> dict:
    return {"authorization": _key()}


def start(audio) -> str:
    """Upload a file-like audio stream and ask for a transcript with the
    speakers told apart; returns the transcript id to poll."""
    headers = _headers()
    put = requests.post(f"{_service()}/upload", headers=headers, data=audio)
    put.raise_for_status()
    asked = requests.post(
        f"{_service()}/transcript",
        headers=headers,
        json={"audio_url": put.json()["upload_url"], "speaker_labels": True},
    )
    asked.raise_for_status()
    return asked.json()["id"]


def fetched(transcript_id: str, user_id: int, diagram_id: int) -> dict:
    """AssemblyAI's transcript as it stands. A completed one is charged to
    `user_id` once, however often it is read back."""
    answer = requests.get(f"{_service()}/transcript/{transcript_id}", headers=_headers())
    answer.raise_for_status()
    data = answer.json()
    if (
        data["status"] == Status.Completed
        and not ModelCall.query.filter_by(
            turn_id=transcript_id, purpose=Purpose.Transcribe
        ).first()
    ):
        Metered(user_id, diagram_id, transcript_id, Purpose.Transcribe).transcribed(
            data["speech_model_used"], data["audio_duration"]
        )
    return data


def status(transcript_id: str, user_id: int, diagram_id: int) -> dict:
    """{status, utterances, audio_seconds, price, error}: the last three of a
    completed transcript only. AssemblyAI's error goes to the observations
    table once."""
    data = fetched(transcript_id, user_id, diagram_id)
    done = data["status"] == Status.Completed
    if (
        data["status"] == Status.Error
        and not Observation.query.filter_by(
            turn_id=transcript_id, kind=ObservationKind.Import
        ).first()
    ):
        _recorded(
            diagram_id,
            transcript_id,
            {
                "outcome": Outcome.Untranscribed,
                "transcript": transcript_id,
                "error": data.get("error"),
            },
        )
    return {
        "status": data["status"],
        "utterances": (data.get("utterances") or []) if done else None,
        "audio_seconds": data["audio_duration"] if done else None,
        "price": (
            float(heard(data["speech_model_used"], data["audio_duration"]))
            if done
            else None
        ),
        "error": data.get("error"),
    }


def delete(transcript_id: str) -> None:
    answer = requests.delete(f"{_service()}/transcript/{transcript_id}", headers=_headers())
    answer.raise_for_status()


def _recorded(diagram_id: int, turn_id: str, report: dict) -> None:
    """One import record: a recording's outcome is the import's, never a
    coach turn's."""
    db.session.add(
        Observation(
            diagram_id=diagram_id,
            turn_id=turn_id,
            kind=ObservationKind.Import,
            detail=report,
        )
    )
    db.session.commit()


def full_name(person: dict) -> str:
    return " ".join(filter(None, (person.get("name"), person.get("last_name"))))


def names(voices: dict, people: list[dict]) -> dict[str, dict]:
    """Each speaker label to {name, person_id}, from what the person said
    each one is: a person in the diagram, the clinician, or a name typed
    (R-0951, R-0952)."""
    found = {p["id"]: p for p in people}
    out = {}
    for label, said in voices.items():
        if set(said) == {"person_id"}:
            person = found.get(said["person_id"])
            if person is None:
                raise ValueError(f"No person {said['person_id']} in the diagram")
            out[label] = {"name": full_name(person), "person_id": person["id"]}
        elif said == {"clinician": True}:
            out[label] = {"name": CLINICIAN, "person_id": None}
        elif set(said) == {"name"} and said["name"].strip():
            out[label] = {"name": said["name"].strip(), "person_id": None}
        else:
            raise ValueError(f"Who speaker {label} is was not said")
    return out


def written(
    utterances: list[dict], named: dict[str, str], title: str, date: datetime.date
) -> str:
    """The recording as the text the coach reads: a heading, then each turn of
    talk under its speaker's name, one speaker's consecutive utterances one
    turn."""
    turns: list[list] = []
    for utterance in utterances:
        if turns and turns[-1][0] == utterance["speaker"]:
            turns[-1][1].append(utterance["text"])
        else:
            turns.append([utterance["speaker"], [utterance["text"]]])
    unnamed = {label for label, _ in turns} - set(named)
    if unnamed:
        raise ValueError(f"Who speaker {', '.join(sorted(unnamed))} is was not said")
    speakers = ", ".join(dict.fromkeys(named[label] for label, _ in turns))
    head = (
        f"Recording: {title}\n"
        f"Recorded on {date.day} {date:%B %Y}.\n"
        f"Speakers: {speakers}."
    )
    return "\n\n".join(
        [head, *(f"{named[label]}\n{' '.join(said)}" for label, said in turns)]
    )


class Recording:
    """A recording a message carries, from the message's form: the transcript
    id, who each speaker is, and the title and date it is kept under."""

    def __init__(self, form):
        self.id = form["transcription"]
        self.voices = json.loads(form["voices"])
        self.title = form.get("title", "").strip()
        if not self.title:
            raise ValueError("A recording needs a title")
        if not form.get("date"):
            raise ValueError("A recording needs a date")
        self.date = datetime.date.fromisoformat(form["date"])

    def read(self, diagram: Diagram, user_id: int) -> Written:
        """The finished transcript as the message's attachment; one not
        finished is refused before anything is stored."""
        data = fetched(self.id, user_id, diagram.id)
        if data["status"] != Status.Completed:
            raise Conflict(UNFINISHED)
        self.seconds = data["audio_duration"]
        self.named = names(self.voices, diagram.get_diagram_data().people)
        return Written(
            self.title,
            written(
                data.get("utterances") or [],
                {label: one["name"] for label, one in self.named.items()},
                self.title,
                self.date,
            ),
        )

    def done(self, diagram_id: int, turn_id: str) -> None:
        """After the statement is stored: one import record, and AssemblyAI's
        copy deleted; a delete that fails is written down, not the person's
        error."""
        _recorded(
            diagram_id,
            turn_id,
            {
                "outcome": Outcome.Imported,
                "title": self.title,
                "seconds": self.seconds,
                "speakers": [
                    {"label": label, **one} for label, one in self.named.items()
                ],
            },
        )
        try:
            delete(self.id)
        except requests.RequestException as error:
            _recorded(
                diagram_id,
                turn_id,
                {
                    "outcome": Outcome.Undeleted,
                    "transcript": self.id,
                    "error": str(error),
                },
            )
