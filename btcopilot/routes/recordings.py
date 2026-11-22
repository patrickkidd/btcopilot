"""A recording sent in the chat. The browser sends the audio here, this server
sends it on to be transcribed and hands the transcript back (R-0348), with a
suggestion of who each speaker is (R-0951); the message that carries it is
sent to /chat like a file's (R-0954, R-0959)."""

from flask import abort, jsonify, request

from btcopilot import auth, speakers, transcription
from btcopilot.routes import bp, writable_diagram


@bp.route("/transcriptions", methods=["POST"])
def transcription_start():
    """The audio, as the one file of a multipart form. Answers with the id to
    poll; without a key configured it fails where the reader can see it."""
    writable_diagram()
    if request.content_length and request.content_length > transcription.MAX_BYTES:
        abort(413, description=transcription.TOO_BIG)
    audio = request.files.get("audio")
    if audio is None:
        raise ValueError("No audio in the upload")
    return jsonify({"id": transcription.start(audio.stream)}), 202


@bp.route("/transcriptions/<transcript_id>")
def transcription_status(transcript_id: str):
    diagram = writable_diagram()
    return jsonify(
        transcription.status(transcript_id, auth.current_user().id, diagram.id)
    )


@bp.route("/transcriptions/<transcript_id>", methods=["DELETE"])
def transcription_delete(transcript_id: str):
    """A recording removed or replaced before it was sent: AssemblyAI's copy
    goes with it."""
    diagram = writable_diagram()
    transcription.removed(transcript_id, diagram.id, transcript_id)
    return "", 204


@bp.route("/recordings/voices", methods=["POST"])
def recording_voices():
    """What the person is shown when saying who is who: each voice in the
    transcript with the first thing it said, and who it seems to be."""
    return jsonify(
        speakers.suggested(
            request.get_json()["utterances"], writable_diagram(), auth.current_user()
        )
    )
