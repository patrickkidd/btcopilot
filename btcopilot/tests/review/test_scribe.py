"""The scribe writes what a coder says, adding the people they name (R-0270)."""

import re

from mock import patch

from btcopilot.personal.coachmodel import ModelTurn, ToolCall
from btcopilot.personal.models import Change
from btcopilot.review import adapter
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
