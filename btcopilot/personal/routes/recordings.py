"""Putting a recorded session into the record. The browser sends the audio
here, this server sends it on to be transcribed and hands the transcript back
(R-0348), and the reader's answer to who each voice is comes back with it
(R-0243, R-0267)."""

import datetime

from flask import jsonify, request

from btcopilot.personal import transcription
from btcopilot.personal.discussions import (
    create_recording,
    session_payload,
    transcript_voices,
)
from btcopilot.personal.licence import require_professional
from btcopilot.personal.models import SpeakerType
from btcopilot.personal.routes import bp, writable_diagram


@bp.route("/transcriptions", methods=["POST"])
def transcription_start():
    """The audio, as the one file of a multipart form. Answers with the id to
    poll; without a key configured it fails where the reader can see it."""
    require_professional()
    audio = request.files.get("audio")
    if audio is None:
        raise ValueError("No audio in the upload")
    return jsonify({"id": transcription.start(audio.stream)}), 202


@bp.route("/transcriptions/<transcript_id>")
def transcription_status(transcript_id: str):
    require_professional()
    return jsonify(transcription.status(transcript_id))


@bp.route("/recordings/voices", methods=["POST"])
def recording_voices():
    """What the reader is shown in the who-is-who sheet: each voice in the
    transcript with the first thing it said."""
    require_professional()
    return jsonify(transcript_voices(request.get_json()["utterances"]))


@bp.route("/recordings", methods=["POST"])
def recording_create():
    """The point of no return: the thread exists after this and the coach can
    read it, so the voices are named before it is called."""
    require_professional()
    body = request.get_json()
    unknown = set(body) - {"utterances", "voices", "title", "date"}
    if unknown:
        raise ValueError(f"Unknown recording field(s): {', '.join(sorted(unknown))}")
    title = (body.get("title") or "").strip()
    if not title:
        raise ValueError("A recording needs a title")
    voices = {
        label: {**said, "type": SpeakerType(said["type"])}
        for label, said in body["voices"].items()
    }
    made = create_recording(
        writable_diagram(),
        body["utterances"],
        voices,
        title,
        datetime.date.fromisoformat(body["date"]) if body.get("date") else None,
    )
    return jsonify(session_payload(made)), 201
