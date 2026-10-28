"""The scribe writes what a coder says, adding the people they name (R-0270)."""

import importlib
import os
import re

import pytest
from mock import patch

from btcopilot import prompts
from btcopilot.coachmodel import ModelTurn, ToolCall
from btcopilot.llmutil import GEMINI_TIMEOUT_MS, NotOnBedrockError, Served
from btcopilot.extensions import db
from btcopilot.models import Change, Diagram, ModelCall, Observation, ObservationKind, Purpose, TurnEvent
from btcopilot.review import adapter
from btcopilot.review import scribe as scribe_module
from btcopilot.review.scribe import written
from btcopilot.review.scribetools import ScribeTools
from btcopilot.tests.repo import REPO
from btcopilot.tests.review.conftest import coded, person, shift

HAIKU = Served("claude-haiku-4-5")


def added(text: str) -> dict:
    return {"verb": "add", "text": text}


def changed(text: str) -> dict:
    return {"verb": "change", "text": text}


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
        if isinstance(self.steps[0], str):
            return ModelTurn(text=self.steps.pop(0), served=HAIKU)
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


def scribe(client, coding, statement, model, said="what happened", chosen=None):
    with patch.object(adapter, "scribe_model", return_value=model):
        return client.post(
            f"/review/codings/{coding.id}/scribe",
            json={"statement_id": statement.id, "text": said, "person_id": chosen},
        )


def test_adds_the_person_the_coder_names(coder, cut, turns):
    # R-0270
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("add_person", {"name": "James Cooper"})],
        [("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "{person}"})],
    )
    response = scribe(
        coder, coding, turns[0], model, "James Cooper moved to Ohio in 1971"
    )
    assert response.status_code == 200
    assert (response.json["refused"], response.json["choices"]) == ([], [])

    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert [p["name"] for p in record["people"]] == ["Marcus", "James Cooper"]
    assert [(e["kind"], adapter.date_text(e["dateTime"])) for e in record["events"]] == [
        ("noted", "1971-01-01")
    ]
    changes = Change.query.filter_by(diagram_id=coding.diagram_id).all()
    assert [c.statement_id for c in changes] == [turns[0].id] * len(changes)
    assert len(changes) == 2


def test_a_person_the_statement_added_has_a_row_before_the_event_naming_them(coder, cut, turns):
    # R-0883
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("add_person", {"name": "James Cooper"})],
        [("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-03-01", "person": "{person}"})],
    )
    response = scribe(coder, coding, turns[0], model, "James Cooper moved to Ohio in 1971")
    assert response.json["lines"] == [added("James Cooper"), added("James Cooper · Moved to Ohio · 1 Mar 1971")]


def test_a_reopened_thread_shows_the_rows_the_send_showed(coder, cut, turns):
    # R-0883, R-0270
    coding = coded(
        coder.user,
        cut,
        {"people": [{"id": 1, "name": "Marcus", "gender": "male"}], "lastItemId": 1},
        done=False,
    )
    model = Scripted(
        [
            ("add_person", {"name": "Delphine", "sex": "female", "ref": -1}),
            ("add_bond", {"couple": [1, -1], "married": "yes"}),
            ("add_person", {"name": "Corinne", "sex": "female", "parents": [1, -1]}),
            ("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved", "date": "1971-03-01", "person": 1}),
        ]
    )
    sent = scribe(coder, coding, turns[0], model, "Marcus married Delphine, Corinne is theirs, he moved in 1971")
    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert said[turns[0].id][0]["lines"] == sent.json["lines"]
    assert len(sent.json["lines"]) == 4


def test_people_who_share_a_first_name_are_told_apart_on_buttons_and_rows():
    # R-0883
    data = {
        "people": [
            {"id": 1, "name": "Monique", "last_name": "Larsen"},
            {"id": 2, "name": "Monique", "last_name": "Larsen"},
            {"id": 3, "name": "Monique", "last_name": "Dubois"},
            {"id": 4, "name": "Ada"},
            {"id": 5, "name": "Ada"},
            {"id": 6, "name": "Tom", "last_name": "Hale"},
            {"id": 7, "name": "Ruth", "last_name": "Hale"},
            {"id": 12, "name": "Ada"},
        ],
        "pair_bonds": [{"id": 8, "person_a": 6, "person_b": 5}, {"id": 13, "person_a": 4, "person_b": 12}],
        "events": [
            {"id": 9, "kind": "birth", "child": 1, "dateTime": "1985-04-02"},
            {"id": 10, "kind": "death", "person": 3, "dateTime": "2011-02-01"},
            {"id": 11, "kind": "death", "person": 6, "dateTime": "2012-02-01"},
            {"id": 14, "kind": "birth", "child": 4, "dateTime": "1950-01-01"},
        ],
    }
    assert scribe_module.called(data, full=True) == {
        "1": "Monique Larsen · b. 1985",
        "2": "Monique Larsen",
        "3": "Monique Dubois",
        "4": "Ada · b. 1950",
        "5": "Ada · partner of Tom",
        "6": "Tom Hale",
        "7": "Ruth Hale",
        "12": "Ada",
    }
    assert written(data, ["10", "11"]) == [
        "Monique Dubois · Death · Feb 2011",
        "Tom · Death · Feb 2012",
    ]


def test_each_scribe_call_writes_a_ledger_row_for_the_coder_and_their_record(
    coder, cut, turns
):
    # R-0270, R-0388
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("add_person", {"name": "James Cooper"})], said="Added him.")
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
        [("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "1"})]
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
        Scripted([("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1971-01-01", "person": "1"})]),
        "Marcus moved to Ohio in 1971",
    )
    scribe(
        coder,
        coding,
        turns[0],
        Scripted([("add_noted", {"date_certainty": "certain", "title": "Moved to Ohio", "description": "moved to Ohio", "date": "1972-01-01", "person": "1"})]),
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


class Endless:
    """A model that never ends in words: every step adds one more person."""

    def __init__(self):
        self.step = 0

    def turn(self, system, messages, tools, turn_id=""):
        if False:
            yield
        self.step += 1
        call = ToolCall(
            id=f"call-{self.step}", name="add_person", args={"name": f"Person {self.step}"}
        )
        return ModelTurn(calls=[call], blocks=[], served=HAIKU)


def test_running_out_of_steps_shows_a_row_for_each_entry_that_went_in(coder, cut, turns):
    # R-0411, R-0883
    """What was written stays, one row each, and no sentence comes with it."""
    coding = coded(coder.user, cut, {"people": []}, done=False)
    response = scribe(coder, coding, turns[0], Endless(), "a sentence that never ends")
    assert response.status_code == 200
    assert response.json["lines"] == [added(f"Person {n}") for n in range(1, 9)]

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
    # R-0326, R-0883
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
        [("add_bond", {"couple": [1, 2], "married": "yes"})],
        [("add_couple_event", {"kind": "married", "couple": [1, 2], "date": "1970-06-01", "date_certainty": "certain"})],
        [("add_person", {"name": "Corinne", "sex": "female", "parents": [1, 2]})],
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
        added("Corinne · daughter of Marcus & Delphine"),
        added("Marcus & Delphine · Married · 1 Jun 1970"),
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
        [("add_shift", {"date_certainty": "certain", "anxiety": "up", "date": "1971-01-01", "person": "1", "title": "Got anxious", "description": "got anxious"})]
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
    first = Scripted([("add_person", {"name": "James Cooper"})], said="Added him.")
    assert scribe(coder, coding, turns[0], first, "James Cooper came to stay").status_code == 200

    model = Versioned(
        [
            ("change_event", {"id": 2, "title": "Drank much more"}),
            ("change_event", {"id": 3, "title": "Slept much less"}),
        ]
    )
    response = scribe(coder, coding, turns[0], model, "both got worse")
    assert response.status_code == 200

    events = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"]
    assert [e["title"] for e in events] == ["Drank much more", "Slept much less"]


SHIFT = {"date_certainty": "certain", "description": "could not sleep", "symptom": "up", "date": "2010-01-01", "person": "1"}


def test_a_refused_entry_comes_back_as_a_row_beside_the_ones_that_went_in(coder, cut, turns):
    # R-0883, R-0302
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("add_person", {"name": "James Cooper"}), ("add_shift", SHIFT)],
        said="I need to see the updated record to write this change with the current version number.",
    )
    response = scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    assert response.status_code == 200
    assert (response.json["lines"], response.json["refused"]) == (
        [added("James Cooper")],
        [added("Marcus · could not sleep · 1 Jan 2010")],
    )
    shown = response.get_data(as_text=True)
    assert not [words for words in ("went in", "did not", "again", "version") if words in shown]


def test_an_event_refused_before_its_person_was_added_is_not_shown_unsaved_once_it_went_in(coder, cut, turns):
    # R-0883, R-0884
    coding = coded(coder.user, cut, {"people": []}, done=False)
    undated = {key: value for key, value in SHIFT.items() if key != "date"}
    model = Scripted(
        [("add_shift", dict(undated, title="Sleep trouble began", description="in high school", person=-1))],
        [
            ("add_person", {"name": "Client", "sex": "female", "ref": -1}),
            ("add_shift", dict(SHIFT, title="Sleep trouble", description="began in high school", person=-1)),
        ],
    )
    response = scribe(coder, coding, turns[0], model, "Her sleep trouble started in 2010.")
    assert response.status_code == 200
    assert (response.json["lines"], response.json["refused"]) == (
        [added("Client"), added("Client · Sleep trouble · 1 Jan 2010")],
        [],
    )


def test_a_second_event_of_the_same_kind_really_lost_still_shows_unsaved(coder, cut, turns):
    # R-0883, R-0884
    coding = coded(coder.user, cut, {"people": []}, done=False)
    model = Scripted(
        [
            ("add_shift", dict(SHIFT, title="Sleep trouble began", person=-1)),
            ("add_shift", dict(SHIFT, title="Stopped eating", description="stopped eating", person=-1)),
        ],
        [
            ("add_person", {"name": "Client", "sex": "female", "ref": -1}),
            ("add_shift", dict(SHIFT, title="Sleep trouble began", person=-1)),
        ],
    )
    response = scribe(coder, coding, turns[0], model, "Her sleep trouble began and she stopped eating.")
    assert response.status_code == 200
    assert (response.json["lines"], response.json["refused"]) == (
        [added("Client"), added("Client · Sleep trouble began · 1 Jan 2010")],
        [added("someone · Stopped eating · 1 Jan 2010")],
    )


def test_a_statement_nothing_of_goes_in_is_all_refused_rows(coder, cut, turns):
    # R-0883
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    response = scribe(coder, coding, turns[0], Scripted([("add_shift", SHIFT)]), "Marcus could not sleep")
    assert response.status_code == 200
    assert (response.json["lines"], response.json["refused"]) == (
        [],
        [added("Marcus · could not sleep · 1 Jan 2010")],
    )


def test_the_scribe_fixes_its_own_refused_call_after_stopping_on_words(coder, cut, turns):
    # R-0883
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        [("add_shift", SHIFT)],
        "I could not write that.",
        [("add_shift", dict(SHIFT, title="Could not sleep"))],
    )
    response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert (response.json["lines"], response.json["refused"]) == (
        [added("Marcus · Could not sleep · 1 Jan 2010")],
        [],
    )


def test_the_scribe_talking_instead_of_writing_saves_nothing_and_its_words_come_back(coder, cut, turns):
    # R-0883, R-0942
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(said="Which night does the coder mean?")
    response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert response.status_code == 200
    assert (response.json["lines"], response.json["refused"], response.json["choices"]) == ([], [], [])
    assert response.json["reply"] == "Which night does the coder mean?"
    assert adapter.record_of(adapter.diagram_of(coding.diagram_id)).get("events", []) == []


def test_a_question_is_answered_in_words_and_writes_nothing(coder, cut, turns):
    # R-0942
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(said="No, the diagram holds no birth for Marcus yet.")
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, "Do you have a birthdate for him yet?")
    assert len(heard.call_args_list) == 1
    assert (response.json["lines"], response.json["reply"]) == (
        [],
        "No, the diagram holds no birth for Marcus yet.",
    )
    assert Change.query.filter_by(diagram_id=coding.diagram_id).count() == 0


def test_words_after_a_write_that_worked_are_not_a_reply(coder, cut, turns):
    # R-0942
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("add_shift", dict(SHIFT, title="Could not sleep"))], said="Added it.")
    response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert (response.json["lines"], response.json["reply"]) == (
        [added("Marcus · Could not sleep · 1 Jan 2010")],
        "",
    )


def test_a_reopened_thread_carries_what_the_scribe_said_back(coder, cut, turns):
    # R-0942
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    scribe(coder, coding, turns[0], Scripted(said="Not yet."), "Do you have a birthdate for him yet?")
    scribe(coder, coding, turns[0], Scripted([("add_shift", dict(SHIFT, title="Could not sleep"))]), "Marcus could not sleep")
    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert [(one["text"], one["reply"]) for one in said[turns[0].id]] == [
        ("Do you have a birthdate for him yet?", "Not yet."),
        ("Marcus could not sleep", ""),
    ]


def test_two_people_the_words_fit_come_back_as_choices(coder, cut, turns):
    # R-0270, R-0883
    people = [person(1, "Marcus Smith"), person(2, "Marcus Jones")]
    coding = coded(coder.user, cut, {"people": people}, done=False)
    model = Scripted([("add_shift", dict(SHIFT, title="Could not sleep"))])
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert response.status_code == 200
    assert heard.call_count == 1
    assert response.json["choices"] == [
        {"id": 1, "name": "Marcus Smith"},
        {"id": 2, "name": "Marcus Jones"},
    ]
    assert adapter.record_of(adapter.diagram_of(coding.diagram_id)).get("events", []) == []
    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    assert [t["said"] for t in thread["turns"] if t["said"]] == []


def test_a_bug_note_naming_two_parents_reaches_the_scribe_and_is_offered_as_a_report(coder, cut, turns):
    # R-0946, R-0270
    people = [
        {"id": 1, "name": "Patrick", "gender": "male", "parents": 4},
        {"id": 2, "name": "Patrick's father", "gender": "male"},
        {"id": 3, "name": "Patrick's mother", "gender": "female"},
    ]
    record = {"people": people, "pair_bonds": [{"id": 4, "person_a": 2, "person_b": 3}], "lastItemId": 4}
    coding = coded(coder.user, cut, record, done=False)
    words = "This is a bug: the father and mother have no last name"
    model = Scripted([("report", {"kind": "bug", "words": words})], said="Thanks, noted.")
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, words)
    assert heard.called
    assert (response.json["choices"], response.json["report"]) == ([], {"kind": "bug", "words": words})


def test_the_buttons_carry_the_whole_name_the_diagram_holds(coder, cut, turns):
    # R-0883
    people = [
        {"id": 1, "name": "Monique", "last_name": "Larsen"},
        {"id": 2, "name": "Monique", "last_name": "Dubois"},
    ]
    coding = coded(coder.user, cut, {"people": people}, done=False)
    model = Scripted([("add_shift", dict(SHIFT, title="Could not sleep"))])
    response = scribe(coder, coding, turns[0], model, "Monique could not sleep")
    assert [one["name"] for one in response.json["choices"]] == ["Monique Larsen", "Monique Dubois"]


ROBERTS = [
    {"id": 1, "name": "Robert", "last_name": "Stinson"},
    {"id": 2, "name": "Robert", "last_name": "Hale"},
]


def test_a_full_name_one_person_holds_asks_nothing():
    # R-0270
    assert scribe_module.unclear("Robert Stinson was born in 1948", ROBERTS) is None


def test_a_first_name_two_people_share_still_asks():
    # R-0270
    assert scribe_module.unclear("Robert was born in 1948", ROBERTS) == ROBERTS


def test_the_person_tapped_settles_which_one_and_the_words_go_in(coder, cut, turns):
    # R-0270, R-0883
    people = [person(1, "Marcus Smith"), person(2, "Marcus Jones")]
    coding = coded(coder.user, cut, {"people": people}, done=False)
    model = Scripted([("add_shift", dict(SHIFT, title="Could not sleep", person=2))])
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, "Marcus could not sleep", chosen=2)
    assert response.json["lines"] == [added("Marcus Jones · Could not sleep · 1 Jan 2010")]
    assert "2 Marcus Jones" in heard.call_args_list[0].args[1][0]["content"]


def test_a_shift_reads_as_its_title():
    # R-0681, R-0869
    data = {
        "people": [person(1, "Ann")],
        "events": [dict(shift(2, 1, "could not sleep", date="1990-01-01"), title="Sleep problems began")],
    }
    assert written(data, ["2"]) == ["Ann · Sleep problems began · Jan 1990"]


def test_a_pronoun_with_nobody_in_the_diagram_goes_to_the_scribe_and_is_written(coder, cut, turns):
    # R-0884, R-0883
    coding = coded(coder.user, cut, {"people": []}, done=False)
    model = Scripted([("add_person", {"name": "Client"})])
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, "Her sleep trouble started in high school.")
    assert heard.called
    assert (response.json["lines"], response.json["choices"]) == ([added("Client")], [])
    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    assert [p["name"] for p in record["people"]] == ["Client"]


def test_a_pronoun_two_people_could_mean_still_asks(coder, cut, turns):
    # R-0270, R-0883
    people = [
        {"id": 1, "name": "Ann", "gender": "female"},
        {"id": 2, "name": "Beth", "gender": "female"},
    ]
    coding = coded(coder.user, cut, {"people": people}, done=False)
    model = Scripted([("add_shift", dict(SHIFT, title="Sleep trouble started", person=2))])
    response = scribe(coder, coding, turns[0], model, "Her sleep trouble started in high school.")
    assert [one["id"] for one in response.json["choices"]] == [1, 2]


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
    model = Scripted([("add_shift", SHIFT)], [("add_person", {"name": "James Cooper"})])
    scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    kept = TurnEvent.query.order_by(TurnEvent.seq).all()
    assert [(e.kind, e.payload["name"], bool(e.payload["refusal"])) for e in kept] == [
        ("tool_call", "edit_event", True),
        ("tool_call", "edit_person", False),
    ]
    assert {e.discussion_id for e in kept} == {turns[0].discussion_id}
    assert len({e.turn_id for e in kept}) == 1


def test_an_earlier_statement_keeps_its_line_after_a_later_one_changes_the_event(coder, cut, turns):
    # R-0270, R-0883
    coding = coded(coder.user, cut, {"people": [person(1, "Tom")]}, done=False)
    moved = {"date_certainty": "certain", "title": "Moved to Glasgow", "description": "moved", "date": "2006-09-01", "person": "1"}
    scribe(coder, coding, turns[0], Scripted([("add_noted", moved)]), "Tom moved to Glasgow in 2006")
    event_id = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"][0]["id"]
    later = Versioned([("change_event", {"id": event_id, "date": "2007-09-01", "date_certainty": "certain"})])
    fixed = scribe(coder, coding, turns[1], later, "it was 2007, not 2006")
    assert fixed.status_code == 200, fixed.get_data(as_text=True)

    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert said[turns[0].id][0]["lines"] == [added("Tom · Moved to Glasgow · 1 Sep 2007")]
    assert said[turns[1].id][0]["lines"] == [changed("Tom · Moved to Glasgow · 1 Sep 2007")]
    assert fixed.json["lines"] == said[turns[1].id][0]["lines"]


def test_a_refused_scribe_call_is_written_down_as_the_coachs_are(coder, cut, turns):
    # R-0871, R-0517
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted([("add_shift", SHIFT)], [("add_person", {"name": "James Cooper"})])
    scribe(coder, coding, turns[0], model, "James Cooper came and Marcus could not sleep")
    rows = Observation.query.all()
    assert [(r.kind, r.diagram_id, r.detail["tool"], r.detail["retried"]) for r in rows] == [
        (ObservationKind.ToolRefused, coding.diagram_id, "edit_event", False)
    ]


def test_the_same_statement_sent_twice_saves_nothing_the_second_time(coder, cut, turns):
    # R-0883
    coding = coded(coder.user, cut, {"people": [person(1, "Elizabeth"), dict(person(2, "Jim"), gender="male")]}, done=False)
    married = {"kind": "married", "date": "1999-06-01", "date_certainty": "certain", "couple": ["1", "2"]}
    said = "Elizabeth and Jim married in June 1999."
    first = scribe(coder, coding, turns[0], Scripted([("add_couple_event", married)]), said)
    assert first.json["lines"] == [added("Elizabeth & Jim · Married · 1 Jun 1999")]
    diagram = adapter.diagram_of(coding.diagram_id)
    event_id, version = adapter.record_of(diagram)["events"][0]["id"], diagram.version

    again = scribe(coder, coding, turns[0], Versioned([("change_event", dict(married, id=event_id))]), said)
    assert (again.json["lines"], again.json["refused"], again.json["made"]) == ([], [], [])
    assert adapter.diagram_of(coding.diagram_id).version == version


def test_a_birth_is_entered_on_the_person_born(coder, cut, turns):
    # R-0886, R-0884
    coding = coded(coder.user, cut, {"people": [person(1, "Robert")]}, done=False)
    born = {"date": "1948-01-01", "date_certainty": "approximate"}
    model = Scripted([("add_birth", dict(born, child="1", person="1", title="Born in 1948"))])
    response = scribe(coder, coding, turns[0], model, "Robert was born in 1948.", chosen=1)
    assert (response.json["lines"], response.json["refused"]) == ([added("Robert · Birth · 1948")], [])


def test_words_with_no_tool_call_are_the_answer_and_the_model_is_not_asked_again(coder, cut, turns):
    # R-0942
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    model = Scripted(
        "Marcus could not sleep is already in the diagram.",
        [("add_shift", dict(SHIFT, title="Could not sleep"))],
    )
    with patch.object(model, "turn", wraps=model.turn) as heard:
        response = scribe(coder, coding, turns[0], model, "Marcus could not sleep")
    assert len(heard.call_args_list) == 1
    assert (response.json["lines"], response.json["reply"]) == (
        [],
        "Marcus could not sleep is already in the diagram.",
    )


def test_a_birth_has_no_person_and_a_couple_event_no_title_to_fill():
    # R-0886
    tools = {tool["name"]: tool["input_schema"] for tool in ScribeTools(None).tools}
    assert not {"person", "title", "description"} & set(tools["add_birth"]["properties"])
    assert not {"title", "description"} & set(tools["add_couple_event"]["properties"])
    assert "child" in tools["add_birth"]["required"]


COUPLE = {
    "people": [
        {"id": 1, "name": "Elizabeth", "gender": "female"},
        {"id": 2, "name": "Jim", "gender": "male"},
    ],
    "lastItemId": 2,
}
WED = {"kind": "married", "couple": [1, 2], "date": "1999-06-01", "date_certainty": "certain"}


def test_a_marriage_given_a_title_naming_the_spouse_is_entered_once(coder, cut, turns):
    # R-0886, R-0884
    coding = coded(coder.user, cut, COUPLE, done=False)
    model = Scripted([("add_couple_event", dict(WED, title="Married Jim"))])
    response = scribe(coder, coding, turns[0], model, "Elizabeth married Jim in June 1999")
    assert (response.json["lines"], response.json["refused"]) == (
        [added("Elizabeth & Jim · Married · 1 Jun 1999")],
        [],
    )


def test_a_second_marriage_on_the_same_day_is_refused(coder, cut, turns):
    # R-0884
    coding = coded(coder.user, cut, COUPLE, done=False)
    scribe(coder, coding, turns[0], Scripted([("add_couple_event", WED)]), "Elizabeth and Jim married in June 1999")
    again = scribe(coder, coding, turns[1], Scripted([("add_couple_event", WED)]), "Elizabeth and Jim married in June 1999")
    assert again.json["refused"] == [added("Elizabeth & Jim · Married · 1 Jun 1999")]

    events = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"]
    assert [e["kind"] for e in events] == ["married"]


def test_a_person_and_their_birth_go_in_from_one_answer(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, COUPLE, done=False)
    model = Scripted(
        [
            ("add_person", {"name": "Robert", "sex": "male", "ref": -1}),
            ("add_birth", {"child": -1, "parents": [1, 2], "date": "1948-01-01", "date_certainty": "approximate"}),
            ("add_person", {"name": "Ruth", "sex": "female", "parents": [1, 2], "birth_date": "1950-01-01", "birth_date_certainty": "approximate"}),
        ]
    )
    response = scribe(coder, coding, turns[0], model, "Robert was born in 1948 and Ruth in 1950")
    assert response.json["lines"] == [
        added("Robert · son of Elizabeth & Jim"),
        added("Ruth · daughter of Elizabeth & Jim"),
        added("Elizabeth & Jim · Together · no date yet"),
        added("Robert · Birth · 1948"),
        added("Ruth · Birth · 1950"),
    ]


def test_a_ref_nothing_was_added_under_is_refused(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, COUPLE, done=False)
    model = Scripted([("add_birth", {"child": -1, "date": "1948-01-01", "date_certainty": "approximate"})])
    response = scribe(coder, coding, turns[0], model, "Robert was born in 1948")
    assert response.json["lines"] == []
    assert adapter.record_of(adapter.diagram_of(coding.diagram_id)).get("events") in (None, [])


FAMILY = {
    "people": [
        {"id": 1, "name": "Liam", "gender": "male", "parents": 4},
        {"id": 2, "name": "Owen", "gender": "male"},
        {"id": 3, "name": "Maeve", "gender": "female"},
        {"id": 6, "name": "Declan", "gender": "male"},
    ],
    "pair_bonds": [{"id": 4, "person_a": 2, "person_b": 3}],
    "events": [
        {"id": 5, "kind": "birth", "child": 1, "person": 2, "spouse": 3, "dateTime": "1980-01-01", "dateCertainty": "approximate"}
    ],
    "lastItemId": 6,
}


def parents_of_liam(coding) -> tuple:
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    liam = next(p for p in data["people"] if p["id"] == 1)
    bond = next(b for b in data["pair_bonds"] if b["id"] == liam["parents"])
    birth = next(e for e in data["events"] if e["id"] == 5)
    return {bond["person_a"], bond["person_b"]}, {birth["person"], birth["spouse"]}


def test_a_corrected_father_on_the_birth_moves_the_child_too(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, FAMILY, done=False)
    model = Versioned([("change_event", {"id": 5, "parents": [6]})])
    response = scribe(coder, coding, turns[0], model, "Liam's father was Declan, not Owen")
    assert response.json["refused"] == []
    assert parents_of_liam(coding) == ({6, 3}, {6, 3})


def test_a_changed_birth_said_to_the_day_reads_the_day(coder, cut, turns):
    # R-0896, R-0883
    family = dict(FAMILY, events=[dict(FAMILY["events"][0], dateTime="1980-05-11", dateCertainty="certain", datePrecision="day")])
    coding = coded(coder.user, cut, family, done=False)
    model = Versioned([("change_event", {"id": 5, "parents": [6]})])
    response = scribe(coder, coding, turns[0], model, "Liam's father was Declan, not Owen")
    assert changed("Liam · Birth · 11 May 1980") in response.json["lines"]


def test_a_corrected_father_on_the_child_moves_the_birth_too(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, FAMILY, done=False)
    model = Versioned([("change_person", {"id": 1, "parents": [6]})])
    response = scribe(coder, coding, turns[0], model, "Liam's father was Declan, not Owen")
    assert response.json["refused"] == []
    assert parents_of_liam(coding) == ({6, 3}, {6, 3})


def test_one_parent_given_to_a_birth_adds_the_other(coder, cut, turns):
    # R-0886, R-0325
    record = {
        "people": [{"id": 1, "name": "Liam", "gender": "male"}, {"id": 2, "name": "Owen", "gender": "male"}],
        "events": [{"id": 3, "kind": "birth", "child": 1, "dateTime": "1980-01-01", "dateCertainty": "approximate"}],
        "lastItemId": 3,
    }
    coding = coded(coder.user, cut, record, done=False)
    scribe(coder, coding, turns[0], Versioned([("change_event", {"id": 3, "parents": [2]})]), "Owen is his father")
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    birth = data["events"][0]
    assert (birth["person"], birth["spouse"] is not None) == (2, True)
    assert next(p for p in data["people"] if p["id"] == birth["spouse"])["name"] == "Liam's mother"


def test_unmarried_is_stored_as_not_married(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, COUPLE, done=False)
    scribe(coder, coding, turns[0], Scripted([("add_bond", {"couple": [1, 2], "married": "no"})]), "Elizabeth and Jim never married")
    bonds = adapter.record_of(adapter.diagram_of(coding.diagram_id))["pair_bonds"]
    assert [b["married"] for b in bonds] == [False]


def test_not_married_is_refused_while_the_couple_has_a_marriage(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, COUPLE, done=False)
    scribe(coder, coding, turns[0], Scripted([("add_couple_event", WED)]), "Elizabeth and Jim married in June 1999")
    bond = adapter.record_of(adapter.diagram_of(coding.diagram_id))["pair_bonds"][0]
    response = scribe(coder, coding, turns[1], Versioned([("change_bond", {"id": bond["id"], "married": "no"})]), "Elizabeth and Jim never married")
    assert response.json["lines"] == []
    assert adapter.record_of(adapter.diagram_of(coding.diagram_id))["pair_bonds"][0]["married"] is True


def test_a_person_on_a_birth_is_refused_before_the_record(coder, cut, turns):
    # R-0886
    coding = coded(coder.user, cut, FAMILY, done=False)
    response = scribe(coder, coding, turns[0], Versioned([("change_event", {"id": 5, "person": 6})]), "Declan was born then")
    assert response.json["lines"] == []
    assert parents_of_liam(coding) == ({2, 3}, {2, 3})
    kept = TurnEvent.query.one().payload
    assert (kept["name"], kept["scribe"], bool(kept["refusal"])) == ("edit_event", "change_event", True)


def test_the_scribe_runs_on_gemini_flash():
    # R-0885
    with patch.dict(os.environ, {"BTCOPILOT_MODEL_PROVIDER": "anthropic", "BTCOPILOT_LOCAL_URL": ""}):
        model = adapter.scribe_model(scribe_module.MODEL)
    assert (type(model).__name__, model.model) == ("GeminiModel", "gemini-3.8-flash")


def test_the_scribe_fails_plainly_on_bedrock():
    # R-0885
    with patch.dict(os.environ, {"BTCOPILOT_MODEL_PROVIDER": "bedrock", "BTCOPILOT_LOCAL_URL": ""}):
        with pytest.raises(NotOnBedrockError):
            adapter.scribe_model(scribe_module.MODEL)


def test_two_people_who_share_a_first_name_both_named_in_full_ask_nothing():
    # R-0270
    said = "Patrick's father was Robert Hale, not Robert Stinson."
    assert scribe_module.unclear(said, ROBERTS + [person(3, "Patrick")]) is None


def test_a_corrected_father_reads_as_whose_child_they_now_are(coder, cut, turns):
    # R-0883, R-0886
    coding = coded(coder.user, cut, FAMILY, done=False)
    model = Versioned([("change_event", {"id": 5, "parents": [6]})])
    sent = scribe(coder, coding, turns[0], model, "Liam's father was Declan, not Owen")
    assert changed("Liam · son of Declan & Maeve") in sent.json["lines"]

    thread = coder.get(f"/review/codings/{coding.id}/thread").json
    said = {turn["id"]: turn["said"] for turn in thread["turns"]}
    assert said[turns[0].id][0]["lines"] == sent.json["lines"]


def test_a_year_the_coder_says_alone_is_kept_and_read_back_as_the_year(coder, cut, turns):
    # R-0896
    coding = coded(coder.user, cut, dict(STRUCTURE, events=[]), done=False)
    model = Scripted(
        [("add_couple_event", {"kind": "married", "couple": [1, 2], "date": "1970", "date_certainty": "certain"})],
    )
    response = scribe(coder, coding, turns[0], model, "Marcus married Delphine in 1970")
    assert response.status_code == 200
    assert response.json["lines"] == [added("Marcus & Delphine · Married · 1970")]
    (married,) = db.session.get(Diagram, coding.diagram_id).get_diagram_data().events
    assert (married["dateTime"], married["datePrecision"]) == ("1970-01-01", "year")


def test_the_page_waits_for_the_scribe_as_long_as_the_server_can_take():
    # R-0869, R-0883
    """A slow scribe that still writes is never shown to the coder as not saved."""
    api = (REPO / "web" / "src" / "api.ts").read_text()
    longest = scribe_module.MAX_STEPS * GEMINI_TIMEOUT_MS // 1000 + 30
    assert scribe_module.MODEL.startswith("gemini")
    assert f"SCRIBE_WAIT_S = {longest};" in api


def test_each_message_carries_the_coders_earlier_statements_on_the_coding(coder, cut, turns):
    # R-0941
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    first = Scripted()
    with patch.object(first, "turn", wraps=first.turn) as heard:
        scribe(coder, coding, turns[0], first, "Marcus could not sleep")
    assert "earlier" not in heard.call_args_list[0].args[1][0]["content"]
    second = Scripted()
    with patch.object(second, "turn", wraps=second.turn) as heard:
        scribe(coder, coding, turns[1], second, "Marcus was born in 1980")
    sent = heard.call_args_list[0].args[1][0]["content"]
    assert sent.startswith(
        "What the coder said earlier on this coding, oldest first, each with what it produced:\n"
        "- Marcus could not sleep → nothing written\n\n"
    )
    assert sent.endswith("Marcus was born in 1980\n")


def test_each_earlier_statement_carries_what_it_produced(coder, cut, turns):
    # R-0946, R-0941
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    scribe(coder, coding, turns[0], Scripted([("add_person", {"name": "Paul"})]), "Add Marcus's father Paul")
    asked = Scripted(said="The first statement added him.")
    with patch.object(asked, "turn", wraps=asked.turn) as heard:
        scribe(coder, coding, turns[1], asked, "How was Paul added?")
    assert "- Add Marcus's father Paul → added Paul\n" in heard.call_args_list[0].args[1][0]["content"]
    after = Scripted()
    with patch.object(after, "turn", wraps=after.turn) as heard:
        scribe(coder, coding, turns[1], after, "Paul was born in 1950")
    assert "- How was Paul added? → answered: The first statement added him.\n" in (
        heard.call_args_list[0].args[1][0]["content"]
    )


def test_earlier_statements_read_only_the_changes_their_own_turns_made(coder, cut, turns):
    # R-0946, R-0941
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    adapter.commit(coding.diagram_id, [], coder.user.id, "another-turn")
    first = scribe(coder, coding, turns[0], Scripted([("add_person", {"name": "Paul"})]), "Add Marcus's father Paul")
    after = Scripted()
    with patch.object(adapter, "deltas_by_turn", wraps=adapter.deltas_by_turn) as read:
        with patch.object(after, "turn", wraps=after.turn) as heard:
            scribe(coder, coding, turns[1], after, "Paul was born in 1950")
    assert "- Add Marcus's father Paul → added Paul\n" in heard.call_args_list[0].args[1][0]["content"]
    assert read.call_args.args == (coding.diagram_id, {first.json["turn_id"]})
    logged = {c.turn_id for c in Change.query.filter_by(diagram_id=coding.diagram_id)}
    assert "another-turn" in logged
    assert set(adapter.deltas_by_turn(coding.diagram_id, {first.json["turn_id"]})) == {first.json["turn_id"]}


AGED = {"person": "1", "title": "Anxiety started", "description": "at 16", "symptom": "up"}


def test_an_age_with_no_birth_in_the_diagram_is_written_with_no_date(coder, cut, turns):
    # R-0943
    coding = coded(coder.user, cut, {"people": [person(1, "Ann")]}, done=False)
    response = scribe(coder, coding, turns[0], Scripted([("add_shift", AGED)]), "Ann's anxiety started at 16")
    assert (len(response.json["lines"]), response.json["refused"]) == (1, [])
    (event,) = adapter.record_of(adapter.diagram_of(coding.diagram_id))["events"]
    assert (event["kind"], event.get("dateTime")) == ("shift", None)


def test_an_age_with_a_birth_in_the_diagram_is_written_dated(coder, cut, turns):
    # R-0943, R-0940
    born = {"id": 2, "kind": "birth", "child": 1, "dateTime": "1980-01-01"}
    coding = coded(coder.user, cut, {"people": [person(1, "Ann")], "events": [born]}, done=False)
    aged = dict(AGED, date="1996", date_certainty="approximate")
    response = scribe(coder, coding, turns[0], Scripted([("add_shift", aged)]), "Ann's anxiety started at 16")
    assert (response.json["lines"], response.json["refused"]) == ([added("Ann · Anxiety started · 1996")], [])


def test_a_note_about_the_app_is_offered_as_a_report_and_writes_nothing(coder, cut, turns):
    # R-0946, R-0056
    coding = coded(coder.user, cut, {"people": [person(1, "Marcus")]}, done=False)
    words = "this is a bug, the parents were added though never mentioned"
    before = adapter.diagram_of(coding.diagram_id).version
    model = Scripted([("report", {"kind": "bug", "words": words})], said="Thanks, noted.")
    response = scribe(coder, coding, turns[0], model, words)
    assert response.json["report"] == {"kind": "bug", "words": words}
    assert (response.json["lines"], response.json["refused"]) == ([], [])
    assert adapter.diagram_of(coding.diagram_id).version == before
