"""Transcribing a recorded session at AssemblyAI, from this server. The
browser never holds the account key (R-0348): the audio comes here and goes
on, and the transcript is read back through here."""

import os

import requests

from btcopilot.metered import Metered
from btcopilot.models.modelcall import ModelCall, Purpose

SERVICE = "https://api.assemblyai.com/v2"


class NotConfigured(ValueError):
    """No transcription key on this server, said where the reader can see it."""


def _key() -> str:
    key = os.getenv("ASSEMBLYAI_API_KEY")
    if not key:
        raise NotConfigured("Transcription is not configured on this server")
    return key


def start(audio) -> str:
    """Upload a file-like audio stream and ask for a diarized transcript;
    returns the transcript id to poll."""
    key = _key()
    put = requests.post(f"{SERVICE}/upload", headers={"authorization": key}, data=audio)
    put.raise_for_status()
    asked = requests.post(
        f"{SERVICE}/transcript",
        headers={"authorization": key},
        json={"audio_url": put.json()["upload_url"], "speaker_labels": True},
    )
    asked.raise_for_status()
    return asked.json()["id"]


def status(transcript_id: str, user_id: int) -> dict:
    """{status, utterances, error}: the utterances only once it is completed.
    A completed transcript is charged to `user_id` once, however often it is
    read back."""
    answer = requests.get(
        f"{SERVICE}/transcript/{transcript_id}", headers={"authorization": _key()}
    )
    answer.raise_for_status()
    data = answer.json()
    if (
        data["status"] == "completed"
        and not ModelCall.query.filter_by(
            turn_id=transcript_id, purpose=Purpose.Transcribe
        ).first()
    ):
        Metered(user_id, None, transcript_id, Purpose.Transcribe).transcribed(
            data["speech_model_used"], data["audio_duration"]
        )
    return {
        "status": data["status"],
        "utterances": (
            data.get("utterances") or [] if data["status"] == "completed" else None
        ),
        "error": data.get("error"),
    }
