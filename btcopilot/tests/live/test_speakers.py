"""The suggestion of who each speaker in a recording is, on an invented family
and an invented three-speaker conversation (R-0951, R-0952). One speaker is
called by his first name by another, one runs the meeting the way a clinician
does, and one says nothing that points to anyone, though the user who sent
the recording is in the diagram and is the one person left.

Pass criterion, 2 of 3 runs, each run checked on the answer the app keeps
(the model's guesses after the app drops those the transcript does not bear
out) and on the model's raw answer:
- speaker B is suggested as Tobias Quill (id 2), resting on words said by A
  that name him;
- speaker A is suggested as the clinician;
- speaker C gets no suggestion;
- no guess, kept or dropped, names an id that is not a person in the diagram.

The app makes this call on the response model with Claude's structured output
option. Here the same prompt and schema go through Claude Code (`claude -p`
with the schema as its JSON schema) on the subscription, the way the cluster
cases run (test_clusters.py), so the case costs nothing; LIVE_SPEAKER_MODEL
names the model, the app's own by default.
"""

import json
import os
import subprocess
import tempfile
from types import SimpleNamespace

from btcopilot.llmutil import RESPONSE_MODEL, output_format
from btcopilot.schema import DiagramData, from_dict
from btcopilot.speakers import SCHEMA, Guesses, first, kept, prompt
from btcopilot.tests.live.criterion import passes

MODEL = os.environ.get("LIVE_SPEAKER_MODEL", RESPONSE_MODEL)
SYSTEM = "Answer with the JSON the schema asks for and nothing else."
TIMEOUT = 600

PEOPLE = [
    {"id": 1, "name": "Mara", "last_name": "Quill"},
    {"id": 2, "name": "Tobias", "last_name": "Quill"},
    {"id": 3, "name": "Juno", "last_name": "Quill"},
    {"id": 4, "name": "Edith", "last_name": "Lark"},
]
UTTERANCES = [
    {"speaker": "A", "text": "Thanks for coming in, both of you. Where would you like to start today?"},
    {"speaker": "B", "text": "Mostly the curfew thing with Juno. It keeps blowing up on weeknights."},
    {"speaker": "C", "text": "I think we just see it differently."},
    {"speaker": "A", "text": "Tobias, what happens for you when it blows up?"},
    {"speaker": "B", "text": "I go quiet and end up in the garage until it settles."},
    {"speaker": "C", "text": "It's been a long year, honestly."},
    {"speaker": "A", "text": "And when things go quiet like that, what do you notice in yourself?"},
    {"speaker": "C", "text": "Mostly tired. I don't know."},
]


class Case:
    """The invented diagram, as much of one as the prompt reads."""

    def get_diagram_data(self):
        return DiagramData(people=PEOPLE, lastItemId=4)

    def access_right(self, user):
        return SimpleNamespace(person_id=1)


def ask(text: str) -> Guesses:
    env = dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS="8000")
    with tempfile.TemporaryDirectory() as cwd:
        ran = subprocess.run(
            [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                MODEL,
                "--system-prompt",
                SYSTEM,
                "--tools",
                "",
                "--max-turns",
                "3",
                "--setting-sources",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--json-schema",
                json.dumps(output_format(SCHEMA)["schema"]),
            ],
            input=text,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=TIMEOUT,
        )
    if ran.returncode and not ran.stdout.strip():
        raise RuntimeError(f"claude -p failed: {ran.stderr.strip()[:500]}")
    result = json.loads(ran.stdout)
    if result.get("is_error"):
        raise RuntimeError(f"claude -p failed: {result.get('subtype')} {result.get('result')}")
    answer = result.get("structured_output") or json.loads(result["result"])
    print(f"  {MODEL}: {json.dumps(answer)}")
    return from_dict(Guesses, answer)


@passes(2, of=3)
def test_who_each_speaker_is_rests_on_what_was_said():
    # R-0951, R-0952
    answer = ask(prompt(UTTERANCES, Case(), None))
    ids = {p["id"] for p in PEOPLE}
    assert all(g.person_id in ids for g in answer.speakers if g.person_id is not None)
    guesses = {}
    for guess in answer.speakers:
        guesses.setdefault(guess.speaker, kept(guess, UTTERANCES, ids))
    assert set(guesses) == {v["label"] for v in first(UTTERANCES)}
    tobias = guesses["B"]
    assert tobias and tobias["person_id"] == 2 and tobias["speaker"] == "A", tobias
    assert "Tobias" in tobias["because"], tobias
    clinician = guesses["A"]
    assert clinician and clinician["person_id"] is None, clinician
    assert guesses["C"] is None, guesses["C"]
