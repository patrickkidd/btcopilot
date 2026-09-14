"""The scribe writes what a coder says, adding the people they name (R-0270)."""

import importlib
import os
import re

from mock import patch

from btcopilot.personal import prompts
from btcopilot.personal.coachmodel import ModelTurn, ToolCall
from btcopilot.personal.models import Change
from btcopilot.review import adapter
from btcopilot.review.scribe import written
from btcopilot.tests.review.conftest import coded, person


class Scripted:
    """A model that makes the calls it was given, one turn at a time, and ends
    in words. `{person}` stands for the id the record just handed back."""

    def __init__(self, *steps, said=""):
        self.steps = list(steps)
        self.said = said

    def turn(self, system, messages, tools):
        if False:
            yield
        if not self.steps:
            return ModelTurn(text=self.said)
        calls = [
            ToolCall(id=f"call-{i}", name=name, args=self._filled(args, messages))
            for i, (name, args) in enumerate(self.steps.pop(0))
        ]
        return ModelTurn(calls=calls, blocks=[])

    def _filled(self, args, messages) -> dict:
        return {
            key: self._added(messages) if value == "{person}" else value
            for key, value in args.items()
        }

    def _added(self, messages) -> int:
        for message in reversed(messages):
            for block in message["content"]:
                found = re.search(r"Added person (\d+)", str(block.get("content")))
                if found:
                    return int(found.group(1))
        raise AssertionError("no person was added for the event to be about")


def scribe(client, coding, statement, model, said="what happened"):
    with patch.object(adapter, "coach_model", return_value=model):
        return client.post(
            f"/review/codings/{coding.id}/scribe",
            json={"statement_id": statement.id, "text": said},
        )


def test_adds_the_person_the_coder_names(coder, cut, turns):
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_person", {"name": "James Cooper"})],
        [("edit_event", {"kind": "moved", "date": "1971-01-01", "person": "{person}"})],
    )
    response = scribe(
        coder, coding, turns[0], model, "James Cooper moved to Ohio in 1971"
    )
    assert response.status_code == 200
    assert response.json["asked"] == ""

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert [p["name"] for p in record["people"]] == ["Marcus", "James Cooper"]
    assert [(e["kind"], adapter.date_text(e["dateTime"])) for e in record["events"]] == [
        ("moved", "1971-01-01")
    ]
    changes = Change.query.filter_by(diagram_id=coding.diagram_id).all()
    assert [c.statement_id for c in changes] == [turns[0].id] * len(changes)
    assert len(changes) == 2


class Never:
    """A model the scribe must not reach."""

    def turn(self, system, messages, tools):
        raise AssertionError("the scribe called the model")
        yield


def test_asks_when_the_coder_points_without_naming(coder, cut, turns):
    """A bare pronoun with more than one person in the record is asked about
    before any model call, so nothing can be written (R-0270)."""
    coding = coded(
        coder.user,
        cut,
        {"people": [person(1, "Marcus"), person(2, "Delphine")]},
        done=False,
    )
    response = scribe(coder, coding, turns[0], Never(), "he moved away that year")
    assert response.status_code == 200
    assert response.json["asked"] == "Which person is this about — Marcus or Delphine?"
    assert response.json["lines"] == []

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert record.get("events") in (None, [])
    assert Change.query.filter_by(diagram_id=coding.diagram_id).count() == 0


def test_asks_when_one_name_could_be_two_people(coder, cut, turns):
    coding = coded(
        coder.user,
        cut,
        {"people": [person(1, "Marcus Webb"), person(2, "Marcus Cooper")]},
        done=False,
    )
    response = scribe(coder, coding, turns[0], Never(), "Marcus moved in 1971")
    assert (
        response.json["asked"]
        == "Which person is this about — Marcus Webb or Marcus Cooper?"
    )
    assert Change.query.filter_by(diagram_id=coding.diagram_id).count() == 0


def test_a_whole_name_settles_shared_words(coder, cut, turns):
    """"Marcus's father" against "Marcus's grandmother" is not ambiguity."""
    coding = coded(
        coder.user,
        cut,
        {"people": [person(1, "Marcus's father"), person(2, "Marcus's grandmother")]},
        done=False,
    )
    model = Scripted(
        [("edit_event", {"kind": "moved", "date": "1969-03-01", "person": 1})]
    )
    response = scribe(coder, coding, turns[0], model, "Marcus's father drove to Arizona")
    assert response.json["asked"] == ""
    assert response.json["lines"]


def test_a_relation_word_names_a_person(coder, cut, turns):
    """"grandmother stopped speaking to him" names one person and, by gender,
    points at the other: no question."""
    coding = coded(
        coder.user,
        cut,
        {"people": [{"id": 1, "name": "father"}, person(2, "mother")]},
        done=False,
    )
    model = Scripted(
        [("edit_person", {"name": "grandmother", "gender": "female"})],
        [("edit_event", {"kind": "shift", "date": "1969-03-01", "person": "{person}"})],
    )
    response = scribe(
        coder, coding, turns[0], model, "grandmother stopped speaking to him for a year"
    )
    assert response.json["asked"] == ""
    assert response.json["lines"]


def test_a_gendered_pronoun_with_one_candidate_is_not_asked(coder, cut, turns):
    coding = coded(
        coder.user, cut, {"people": [{"id": 1, "name": "father"}, person(2, "mother")]}, done=False
    )
    model = Scripted(
        [("edit_event", {"kind": "moved", "date": "1970-01-01", "person": 1})]
    )
    response = scribe(coder, coding, turns[0], model, "he came round the next year")
    assert response.json["asked"] == ""


def test_a_turn_that_names_nobody_still_reaches_the_model(coder, cut, turns):
    """No name and no pronoun is not ambiguity: the model reads the turn."""
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_event", {"kind": "moved", "date": "1971-01-01", "person": 1})]
    )
    response = scribe(coder, coding, turns[0], model, "the family moved in 1971")
    assert response.json["asked"] == ""
    assert response.json["lines"]


def test_writes_the_event_after_a_wasted_guess(coder, cut, turns):
    """On an empty record the cheap model guesses an id, is refused, then adds
    two people before the event. The loop must outlast that: the event lands."""
    coding = coded(coder.user, cut, {"people": []}, done=False)
    model = Scripted(
        [("edit_event", {"kind": "moved", "date": "1969-03-01", "person": 1})],
        [("edit_person", {"name": "Marcus"})],
        [("edit_person", {"name": "Marcus's father"})],
        [
            (
                "edit_event",
                {
                    "kind": "moved",
                    "date": "1969-03-01",
                    "date_certainty": "approximate",
                    "person": "{person}",
                },
            )
        ],
    )
    response = scribe(
        coder,
        coding,
        turns[0],
        model,
        "Marcus's father moved from Michigan to Arizona in March 1969",
    )
    assert response.status_code == 200
    assert response.json["lines"] == ["+ Marcus's father · moved · Mar 1969", "+ Marcus"]

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert [p["name"] for p in record["people"]] == ["Marcus", "Marcus's father"]
    assert [(e["kind"], adapter.date_text(e["dateTime"])) for e in record["events"]] == [
        ("moved", "1969-03-01")
    ]


class Endless:
    """A model that never ends in words: every step adds one more person."""

    def __init__(self):
        self.step = 0

    def turn(self, system, messages, tools):
        if False:
            yield
        self.step += 1
        call = ToolCall(
            id=f"call-{self.step}", name="edit_person", args={"name": f"Person {self.step}"}
        )
        return ModelTurn(calls=[call], blocks=[])


def test_says_so_when_it_runs_out_of_steps(coder, cut, turns):
    """What was written stays, and the coder is told, never shown it as done."""
    coding = coded(coder.user, cut, {"people": []}, done=False)
    response = scribe(coder, coding, turns[0], Endless(), "a sentence that never ends")
    assert response.status_code == 400
    assert response.get_data(as_text=True).startswith(
        "The scribe stopped before it finished after adding Person 1, Person 2"
    )

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert len(record["people"]) == 8


class Heard:
    """A model that keeps the system prompt it was handed and writes nothing."""

    def __init__(self):
        self.system = ""

    def turn(self, system, messages, tools):
        if False:
            yield
        self.system = system
        return ModelTurn(text="which one?")


def test_fdserver_replaces_the_scribe_prompt(coder, cut, turns, tmp_path):
    """The words the scribe works by come from the private prompts when one is
    named, and reach the model whole (R-0314)."""
    private = tmp_path / "private_prompts.py"
    private.write_text(
        "def scribe_prompt(record=''):\n"
        "    return f'the private scribe words\\n{record}'\n"
    )
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Heard()
    try:
        with patch.dict(os.environ, {"FDSERVER_PROMPTS_PATH": str(private)}):
            importlib.reload(prompts)
            scribe(coder, coding, turns[0], model, "James Cooper moved in 1971")
    finally:
        importlib.reload(prompts)
    assert model.system.startswith("the private scribe words")
    assert "Marcus" in model.system
    assert "the private scribe words" not in prompts.scribe_prompt("")


def test_a_marriage_and_a_child_are_written_and_said_back(coder, cut, turns):
    """The coder says who belongs to whom; the lines under their words are the
    marriage and the child, in the record's own words (R-0326, drawing 1a)."""
    coding = coded(
        coder.user,
        cut,
        {
            "people": [
                {"id": 1, "name": "Marcus", "gender": "male"},
                {"id": 2, "name": "Delphine", "gender": "female"},
            ],
            "lastItemId": 2,
        },
        done=False,
    )
    model = Scripted(
        [("edit_pair_bond", {"person_a": 1, "person_b": 2, "married": True})],
        [
            (
                "edit_event",
                {
                    "kind": "married",
                    "date": "1970-06-01",
                    "person": 1,
                    "spouse": 2,
                },
            )
        ],
        [("edit_person", {"name": "Corinne", "gender": "female", "parents": 3})],
    )
    response = scribe(
        coder,
        coding,
        turns[0],
        model,
        "Marcus married Delphine in 1970 and Corinne is their daughter",
    )
    assert response.status_code == 200
    assert response.json["lines"] == [
        "+ Marcus & Delphine · married · Jun 1970",
        "+ Corinne · daughter of Marcus & Delphine",
    ]


STRUCTURE = {
    "people": [
        {"id": 1, "name": "Marcus", "gender": "male"},
        {"id": 2, "name": "Delphine", "gender": "female"},
        {"id": 3, "name": "Corinne", "gender": "female", "parents": 10},
        {"id": 4, "name": "Theo", "gender": "male", "parents": 10},
    ],
    "pair_bonds": [{"id": 10, "person_a": 1, "person_b": 2, "married": True}],
    "events": [
        {
            "id": 20,
            "kind": "married",
            "person": 1,
            "spouse": 2,
            "dateTime": "1970-06-01",
        }
    ],
}


def test_a_marriage_reads_as_both_names_and_the_year():
    """The line the coder sees for a structure write (R-0326, drawing 1a)."""
    assert written(STRUCTURE, ["20"], [], ["10"]) == [
        "+ Marcus & Delphine · married · Jun 1970"
    ]


def test_a_child_reads_as_whose_child_they_are():
    assert written(STRUCTURE, [], ["3", "4"]) == [
        "+ Corinne · daughter of Marcus & Delphine",
        "+ Theo · son of Marcus & Delphine",
    ]


def test_a_bond_with_no_event_says_it_has_no_date_yet():
    record = dict(STRUCTURE, events=[])
    assert written(record, [], [], ["10"]) == [
        "+ Marcus & Delphine · married · no date yet"
    ]
