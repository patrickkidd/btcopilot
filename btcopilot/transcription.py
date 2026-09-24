"""Transcribing a recorded session at AssemblyAI, from this server. The
browser never holds the account key (R-0348): the audio comes here and goes
on, and the transcript is read back through here."""

import os

import requests

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


def status(transcript_id: str) -> dict:
    """{status, utterances, error}: the utterances only once it is completed."""
    answer = requests.get(
        f"{SERVICE}/transcript/{transcript_id}", headers={"authorization": _key()}
    )
    answer.raise_for_status()
    data = answer.json()
    return {
        "status": data["status"],
        "utterances": data.get("utterances") or [] if data["status"] == "completed" else None,
        "error": data.get("error"),
    }
