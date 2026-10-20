"""The scribe writes what a coder says, adding the people they name (R-0270)."""

import importlib
import os
import re

from mock import patch

from btcopilot import prompts
from btcopilot.coachmodel import ModelTurn, ToolCall
from btcopilot.llmutil import Served
from btcopilot.models import Change, ModelCall, Observation, ObservationKind, Purpose, TurnEvent
from btcopilot.review import adapter
from btcopilot.review.scribe import written
from btcopilot.tests.review.conftest import coded, person, shift

HAIKU = Served("claude-haiku-4-5")


class Scripted:
    """A model that makes the calls it was given, one turn at a time, and ends
    in words. `{person}` stands for the id the record just handed back."""

    def __init__(self, *steps, said=""):
        self.steps = list(steps)
        self.said = said

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        if not self.steps:
            return ModelTurn(text=self.said, served=HAIKU)
        calls = [
            ToolCall(id=f"call-{i}", name=name, args=self._filled(args, messages))
            for i, (name, args) in enumerate(self.steps.pop(0))
        ]
        return ModelTurn(calls=calls, blocks=[], served=HAIKU)

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
    # R-0270
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_person", {"name": "James Cooper"})],
        [("edit_event", {"date_certainty": "certain", "kind": "noted", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "{person}"})],
    )
    response = scribe(
        coder, coding, turns[0], model, "James Cooper moved to Ohio in 1971"
    )
    assert response.status_code == 200
    assert response.json["asked"] == ""

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert [p["name"] for p in record["people"]] == ["Marcus", "James Cooper"]
    assert [(e["kind"], adapter.date_text(e["dateTime"])) for e in record["events"]] == [
        ("noted", "1971-01-01")
    ]
    changes = Change.query.filter_by(diagram_id=coding.diagram_id).all()
    assert [c.statement_id for c in changes] == [turns[0].id] * len(changes)
    assert len(changes) == 2


def test_each_scribe_call_writes_a_ledger_row_for_the_coder_and_their_record(
    coder, cut, turns
):
    # R-0270, R-0388
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("edit_person", {"name": "James Cooper"})], said="Added him.")
    scribe(coder, coding, turns[0], model, "James Cooper came to stay")
    rows = ModelCall.query.filter_by(purpose=Purpose.Scribe).all()
    assert [(r.user_id, r.diagram_id, r.model) for r in rows] == [
        (coder.user.id, coding.diagram_id, "claude-haiku-4-5")
    ] * 2


def test_the_coders_words_stay_in_the_thread(coder, cut, turns):
    # R-0270
    """Re-reading the thread gives the coder their own words back under the
    line they coded, with the scribe's line after them (R-0270)."""
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_event", {"date_certainty": "certain", "kind": "noted", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "1"})]
    )
    scribe(coder, coding, turns[0], model, "Marcus moved to Ohio in 1971")

    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert [one["text"] for one in said[turns[0].id]] == ["Marcus moved to Ohio in 1971"]
    assert said[turns[0].id][0]["lines"]
    assert said[turns[1].id] == []


def test_two_things_said_about_one_turn_keep_their_own_lines(coder, cut, turns):
    # R-0270
    """Each utterance carries the lines the scribe wrote from it, so the thread
    reads words, then what they did, then the next words (R-0270)."""
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    scribe(
        coder,
        coding,
        turns[0],
        Scripted([("edit_event", {"date_certainty": "certain", "kind": "noted", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "1"})]),
        "Marcus moved to Ohio in 1971",
    )
    scribe(
        coder,
        coding,
        turns[0],
        Scripted([("edit_event", {"date_certainty": "certain", "kind": "noted", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1972-01-01", "person": "1"})]),
        "Marcus moved again the year after",
    )

    said = {
        turn["id"]: turn["said"]
        for turn in coder.get(f"/review/codings/{coding.id}/thread").json["turns"]
    }
    assert [one["text"] for one in said[turns[0].id]] == [
        "Marcus moved to Ohio in 1971",
        "Marcus moved again the year after",
    ]
    assert all(one["lines"] for one in said[turns[0].id])
    assert said[turns[0].id][0]["lines"] != said[turns[0].id][1]["lines"]


class Never:
    """A model the scribe must not reach."""

    def turn(self, system, messages, tools, turn_id=""):
        raise AssertionError("the scribe called the model")
        yield


class Endless:
    """A model that never ends in words: every step adds one more person."""

    def __init__(self):
        self.step = 0

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        self.step += 1
        call = ToolCall(
            id=f"call-{self.step}", name="edit_person", args={"name": f"Person {self.step}"}
        )
        return ModelTurn(calls=[call], blocks=[], served=HAIKU)


def test_says_so_when_it_runs_out_of_steps(coder, cut, turns):
    # R-0411, R-0869
    """What was written stays, and the coder is told, never shown it as done."""
    coding = coded(coder.user, cut, {"people": []}, done=False)
    response = scribe(coder, coding, turns[0], Endless(), "a sentence that never ends")
    assert response.status_code == 400
    shown = response.get_data(as_text=True).split(": ", 1)[1]
    assert shown.startswith("Person 1, Person 2")
    assert shown.endswith(" went in. The rest did not. Say the rest again in one sentence.")

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert len(record["people"]) == 8


class Heard:
    """A model that keeps the system prompt it was handed and writes nothing."""

    def __init__(self):
        self.system = ""

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        self.system = system
        return ModelTurn(text="which one?", served=HAIKU)


def test_a_private_file_replaces_the_scribe_prompt(coder, cut, turns, tmp_path):
    # R-0314
    """The words the scribe works by come from the private prompt file when one
    is installed, and reach the model whole (R-0314)."""
    (tmp_path / "scribe.prompty").write_text(
        "---\nname: scribe\ndescription: private\n"
        "inputs:\n  committed_state:\n    type: string\n---\n"
        "the private scribe words\n{{ committed_state }}"
    )
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Heard()
    try:
        with patch.dict(os.environ, {"FD_PRIVATE_PROMPTS": str(tmp_path)}):
            importlib.reload(prompts)
            scribe(coder, coding, turns[0], model, "James Cooper moved in 1971")
    finally:
        importlib.reload(prompts)
    assert model.system.startswith("the private scribe words")
    assert "Marcus" in model.system
    assert "the private scribe words" not in prompts.scribe_prompt("")


def test_a_marriage_and_a_child_are_written_and_said_back(coder, cut, turns):
    # R-0326
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
                {"date_certainty": "certain",
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
        "Marcus & Delphine · Married · Jun 1970",
        "Corinne · daughter of Marcus & Delphine",
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
    # R-0326
    """The line the coder sees for a structure write (R-0326, drawing 1a)."""
    assert written(STRUCTURE, ["20"], [], ["10"]) == [
        "Marcus & Delphine · Married · Jun 1970"
    ]


def test_a_child_reads_as_whose_child_they_are():
    # R-0326
    assert written(STRUCTURE, [], ["3", "4"]) == [
        "Corinne · daughter of Marcus & Delphine",
        "Theo · son of Marcus & Delphine",
    ]


def test_a_bond_with_no_event_says_it_has_no_date_yet():
    # R-0013
    record = dict(STRUCTURE, events=[])
    assert written(record, [], [], ["10"]) == [
        "Marcus & Delphine · Married · no date yet"
    ]


def test_a_year_the_coder_only_said_as_a_year_reads_as_the_year():
    # R-0438
    """A year alone is stored as the first of January, approximate; the month
    was never said, so it is not read back (R-0326)."""
    record = dict(
        STRUCTURE,
        events=[
            dict(
                STRUCTURE["events"][0],
                dateTime="1970-01-01",
                dateCertainty="approximate",
            )
        ],
    )
    assert written(record, ["20"], [], ["10"]) == [
        "Marcus & Delphine · Married · 1970"
    ]


def test_a_january_date_the_coder_stated_keeps_its_month():
    # R-0438
    record = dict(
        STRUCTURE,
        events=[
            dict(
                STRUCTURE["events"][0],
                dateTime="1970-01-01",
                dateCertainty="certain",
            )
        ],
    )
    assert written(record, ["20"], [], ["10"]) == [
        "Marcus & Delphine · Married · Jan 1970"
    ]


def test_a_reopened_thread_says_which_events_each_line_wrote(coder, cut, turns):
    # R-0541
    """So the concept pages of their codes hang under the lines on every
    load, not only right after the scribe wrote them."""
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_event", {"date_certainty": "certain", "kind": "shift", "anxiety": "up", "date": "1971-01-01", "person": "1", "title": "Got anxious", "description": "got anxious"})]
    )
    made = scribe(coder, coding, turns[0], model, "Marcus got anxious in 1971").json["made"]

    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert said[turns[0].id][0]["event_ids"] == [int(one["id"]) for one in made]


class Versioned:
    """A model that changes existing events, each step naming the record
    version its system prompt shows; with none shown it guesses 1, as Haiku
    did on production."""

    def __init__(self, *steps):
        self.steps = list(steps)

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        if not self.steps:
            return ModelTurn(text="", served=HAIKU)
        shown = re.search(r"Record version (\d+)\.", system)
        version = int(shown.group(1)) if shown else 1
        calls = [
            ToolCall(id=f"call-{i}", name=name, args=dict(args, version=version))
            for i, (name, args) in enumerate(self.steps.pop(0))
        ]
        return ModelTurn(calls=calls, blocks=[], served=HAIKU)


def test_a_second_request_changes_an_existing_event(coder, cut, turns):
    # R-0270, R-0480
    record = {"people": [person(1, "Marcus")], "events": [shift(2, 1, "drank more"), shift(3, 1, "slept less")]}
    coding = coded(coder.user, cut, record, done=False)
    first = Scripted([("edit_person", {"name": "James Cooper"})], said="Added him.")
    assert scribe(coder, coding, turns[0], first, "James Cooper came to stay").status_code == 200

    model = Versioned(
        [
            ("edit_event", {"id": 2, "title": "Drank much more"}),
            ("edit_event", {"id": 3, "title": "Slept much less"}),
        ]
    )
    response = scribe(coder, coding, turns[0], model, "both got worse")
    assert response.status_code == 200

    events = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"]
    assert [e["title"] for e in events] == ["Drank much more", "Slept much less"]


SHIFT = {"date_certainty": "certain", "kind": "shift", "description": "could not sleep", "symptom": "up", "date": "2010-01-01", "person": "1"}
NOTHING = "That did not go in. Say it again in one sentence."


def test_a_refusal_the_scribe_falls_silent_on_says_it_did_not_go_in(coder, cut, turns):
    # R-0270, R-0869
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    response = scribe(coder, coding, turns[0], Scripted([("edit_event", SHIFT)]), "Marcus could not sleep")
    assert response.status_code == 400
    assert response.get_data(as_text=True).split(": ", 1)[1] == NOTHING


def test_a_refusal_the_scribe_talks_about_shows_only_what_went_in(coder, cut, turns):
    # R-0270, R-0869
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("edit_person", {"name": "James Cooper"}), ("edit_event", SHIFT)],
        said="I need to see the updated record to write this change with the current version number.",
    )
    response = scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    assert response.status_code == 400
    assert response.get_data(as_text=True).split(": ", 1)[1] == (
        "James Cooper went in. The rest did not. Say the rest again in one sentence."
    )


def test_the_scribe_talking_instead_of_writing_says_it_did_not_go_in(coder, cut, turns):
    # R-0270, R-0869
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        said=(
            "I need to reread the current record. Let me check what events are there "
            "now and get the correct version number for event 2. Could you provide the "
            "current version number shown in the record for event 2?"
        )
    )
    response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert response.status_code == 400
    assert response.get_data(as_text=True).split(": ", 1)[1] == NOTHING


def test_the_question_asked_before_the_model_reaches_the_coder(coder, cut, turns):
    # R-0270
    people = [person(1, "Marcus Smith"), person(2, "Marcus Jones")]
    coding = coded(coder.user, cut, {"people": people}, done=False)
    response = scribe(coder, coding, turns[0], Never(), "Marcus could not sleep")
    assert response.status_code == 200
    assert response.json["asked"] == "Which person is this about — Marcus Smith or Marcus Jones?"


def test_a_shift_reads_as_its_title():
    # R-0681, R-0869
    data = {
        "people": [person(1, "Ann")],
        "events": [dict(shift(2, 1, "could not sleep", date="1990-01-01"), title="Sleep problems began")],
    }
    assert written(data, ["2"]) == ["Ann · Sleep problems began · Jan 1990"]


def test_an_empty_diagram_is_asked_about_as_the_diagram(coder, cut, turns):
    # R-0270, R-0869
    coding = coded(coder.user, cut, {"people": []}, done=False)
    response = scribe(coder, coding, turns[0], Never(), "she could not sleep")
    assert response.json["asked"] == "Which person is this about? The diagram has nobody in it yet."


def test_a_death_reads_as_its_kind_name():
    # R-0869
    data = {
        "people": [person(1, "Rose")],
        "events": [
            {"id": 2, "kind": "death", "person": 1, "dateTime": "2011-02-01"},
            {"id": 3, "kind": "death", "person": 1, "description": "in Oklahoma", "dateTime": "2011-02-01"},
            {"id": 4, "kind": "death", "person": 1, "description": "Died in hospital. ", "dateTime": "2011-02-01"},
        ],
    }
    assert written(data, ["2", "3", "4"]) == [
        "Rose · Death · Feb 2011",
        "Rose · Death · in Oklahoma · Feb 2011",
        "Rose · Death · Died in hospital · Feb 2011",
    ]


def test_a_scribe_turn_keeps_its_calls_with_the_turn(coder, cut, turns):
    # R-0871, R-0517
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("edit_event", SHIFT)], [("edit_person", {"name": "James Cooper"})])
    scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    kept = TurnEvent.query.order_by(TurnEvent.seq).all()
    assert [(e.kind, e.payload["name"], bool(e.payload["refusal"])) for e in kept] == [
        ("tool_call", "edit_event", True),
        ("tool_call", "edit_person", False),
    ]
    assert {e.discussion_id for e in kept} == {turns[0].discussion_id}
    assert len({e.turn_id for e in kept}) == 1


def test_an_earlier_statement_keeps_its_line_after_a_later_one_changes_the_event(coder, cut, turns):
    # R-0270
    coding = coded(coder.user, cut, {"people": [person(1, "Tom")]}, done=False)
    moved = {"date_certainty": "certain", "kind": "noted", "title": "Moved to Glasgow", "description": "moved", "date": "2006-09-01", "person": "1"}
    scribe(coder, coding, turns[0], Scripted([("edit_event", moved)]), "Tom moved to Glasgow in 2006")
    event_id = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"][0]["id"]
    later = Versioned([("edit_event", {"id": event_id, "date": "2007-09-01", "date_certainty": "certain"})])
    fixed = scribe(coder, coding, turns[1], later, "it was 2007, not 2006")
    assert fixed.status_code == 200, fixed.get_data(as_text=True)

    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert said[turns[0].id][0]["lines"] == ["Tom · Moved to Glasgow · Sep 2007"]
    assert said[turns[1].id][0]["lines"] == ["Tom · Moved to Glasgow · Sep 2007"]


def test_a_refused_scribe_call_is_written_down_as_the_coachs_are(coder, cut, turns):
    # R-0871, R-0517
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("edit_event", SHIFT)], [("edit_person", {"name": "James Cooper"})])
    scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    rows = Observation.query.all()
    assert [(r.kind, r.diagram_id, r.detail["tool"], r.detail["retried"]) for r in rows] == [
        (ObservationKind.ToolRefused, coding.diagram_id, "edit_event", False)
    ]
