"""Who each speaker in a recording seems to be, from what was said: one model
call suggests a person in the diagram, the clinician, or nobody, with the
words it rests on; a suggestion whose words are not in the transcript, or that
names no one in the diagram, is dropped. The person picks, the suggestion only
puts a pick first (R-0951, R-0952)."""

import enum
import uuid
from dataclasses import dataclass

from btcopilot import coverage, prompts, profile
from btcopilot.metered import Metered
from btcopilot.models import Diagram, TokenMeter
from btcopilot.models.modelcall import Purpose
from btcopilot.transcription import full_name

# Each speaker's opening turns the model reads; who someone is is said early.
FIRST_TURNS = 6
TOKENS = 8000


class Who(enum.StrEnum):
    Person = "person"
    Clinician = "clinician"
    Nobody = "nobody"


@dataclass
class Guess:
    speaker: str
    who: Who
    person_id: int | None
    because: str
    said_by: str


@dataclass
class Guesses:
    speakers: list[Guess]


SCHEMA = {
    "type": "object",
    "properties": {
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "who": {"type": "string", "enum": [w.value for w in Who]},
                    "person_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                    "because": {"type": "string"},
                    "said_by": {"type": "string"},
                },
                "required": ["speaker", "who", "person_id", "because", "said_by"],
            },
        }
    },
    "required": ["speakers"],
}


def first(utterances: list[dict]) -> list[dict]:
    """Each voice with the first thing it said, in the order they first speak."""
    found: dict[str, dict] = {}
    for utterance in utterances:
        found.setdefault(
            utterance["speaker"],
            {"label": utterance["speaker"], "said": utterance["text"]},
        )
    return list(found.values())


def opening(utterances: list[dict]) -> list[dict]:
    """The transcript cut to each speaker's first FIRST_TURNS utterances, in
    the order they were said."""
    seen: dict[str, int] = {}
    kept = []
    for utterance in utterances:
        seen[utterance["speaker"]] = seen.get(utterance["speaker"], 0) + 1
        if seen[utterance["speaker"]] <= FIRST_TURNS:
            kept.append(utterance)
    return kept


def prompt(utterances: list[dict], diagram: Diagram, user) -> str:
    """The suggestion call's prompt: the instruction, the diagram's people,
    who the user is in it, and the opening of the transcript."""
    data = diagram.get_diagram_data()
    roles = coverage.roles(data)
    people = "\n".join(
        f"{p['id']}: {full_name(p) or 'no name'}"
        + (f", {roles[p['id']]}" if p["id"] in roles else "")
        for p in data.people
    )
    mine = profile.person_of(user, diagram)
    me = next((p for p in data.people if p["id"] == mine), None)
    sender = (
        f"The user who sent the recording is {me['id']}: {full_name(me)}."
        if me
        else "The user who sent the recording is no one in the diagram."
    )
    lines = "\n".join(f"{u['speaker']}: {u['text']}" for u in opening(utterances))
    return (
        f"{prompts.files().fragment('speakers')}\n\n"
        f"People in the diagram:\n{people or 'none yet'}\n\n"
        f"{sender}\n\n"
        f"Speaker labels: {', '.join(v['label'] for v in first(utterances))}\n\n"
        f"The transcript's opening turns:\n{lines}"
    )


def kept(guess: Guess, utterances: list[dict], ids: set[int]) -> dict | None:
    """A guess the transcript bears out, as the page takes it, or None."""
    if guess.who is Who.Nobody:
        return None
    if guess.who is Who.Person and guess.person_id not in ids:
        return None
    quoted = guess.because.strip()
    if not quoted or not any(
        u["speaker"] == guess.said_by and quoted in u["text"] for u in utterances
    ):
        return None
    return {
        "person_id": guess.person_id if guess.who is Who.Person else None,
        "because": quoted,
        "speaker": guess.said_by,
    }


def suggested(utterances: list[dict], diagram: Diagram, user) -> list[dict]:
    """[{label, said, suggestion}] for every voice, `suggestion` null where
    nothing said points to anyone. One structured call on the attachment
    read's model, charged to the person as a file's read is."""
    voices = first(utterances)
    if not voices:
        return []
    meter = Metered(user.id, diagram.id, uuid.uuid4().hex, Purpose.Transcribe)
    try:
        answer = meter.asked(prompt(utterances, diagram, user), Guesses, SCHEMA, TOKENS)
    finally:
        TokenMeter.charge(user.id, meter.spent)
    ids = {p["id"] for p in diagram.get_diagram_data().people}
    guesses: dict[str, dict | None] = {}
    for guess in answer.speakers:
        if guess.speaker not in guesses:
            guesses[guess.speaker] = kept(guess, utterances, ids)
    return [dict(voice, suggestion=guesses.get(voice["label"])) for voice in voices]
