"""Putting a recorded session into the record. The browser sends the audio
straight to the transcription service, the way the training app already does,
and posts the transcript here with the reader's answer to who each voice is
(R-0243, R-0267)."""

import datetime
import os

from flask import jsonify, request

from btcopilot.personal.discussions import create_recording, transcript_voices
from btcopilot.personal.licence import require_professional
from btcopilot.personal.models import SpeakerType
from btcopilot.personal.routes import bp, writable_diagram
from btcopilot.personal.routes.sessions import session_payload


@bp.route("/transcription")
def transcription_key():
    """The key the browser uploads the audio with. Without one configured the
    upload fails where the reader can see it rather than pretending to work."""
    require_professional()
    key = os.getenv("ASSEMBLYAI_API_KEY")
    if not key:
        raise ValueError("Transcription is not configured on this server")
    return jsonify({"key": key})


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
