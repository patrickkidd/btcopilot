import re

import pytest

from btcopilot import fdcoding, prompts
from btcopilot.promptdir import key_present
from btcopilot.schema import from_dict

PLAIN = """---
name: import_coding
---
{% include "fragments/agent_record_contract.md" %}
WHO: {{ who }}
{{ people }}
{{ events }}
{{ texts }}
{{ meanings }}
"""


@pytest.fixture(autouse=True)
def plain(tmp_path, monkeypatch):
    """A plain stand-in for the private prompt, so the pass runs without a key."""
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "agent_record_contract.md").write_text(
        "THE COACH'S RULES"
    )
    (tmp_path / "import_coding.prompty").write_text(PLAIN)
    monkeypatch.setenv("FD_PRIVATE_PROMPTS", str(tmp_path))
    prompts.files.cache_clear()
    yield
    prompts.files.cache_clear()


class Model:
    """Answers each person's call with what the test gave for them."""

    def __init__(self, answers: dict | None = None):
        self.answers = answers or {}
        self.prompts = []

    def __call__(self, prompt, response_format, schema, limit):
        self.prompts.append(prompt)
        who = re.search(r"WHO: (.*)", prompt).group(1)
        return from_dict(response_format, self.answers.get(who, {}))


def diagram(events=(), notes=None) -> dict:
    ada = {"id": 1, "name": "Ada", "last_name": "Lund", "parents": 10}
    if notes:
        ada["notes"] = notes
    return {
        "people": [
            ada,
            {"id": 3, "name": "Bo", "last_name": "Lund", "parents": 10},
            {"id": 4, "name": "Cy", "last_name": "Lund"},
            {"id": 5, "name": "Dan", "last_name": "Lund"},
        ],
        "pair_bonds": [{"id": 10, "person_a": 4, "person_b": 5}],
        "events": list(events),
    }


def shift(id, **more) -> dict:
    return {"id": id, "kind": "shift", "person": 1, "dateCertainty": "unknown", **more}


def by_id(data: dict) -> dict:
    return {event["id"]: event for event in data["events"]}


def test_a_value_coded_by_hand_is_never_changed():
    # R-0859, R-0868
    data = diagram([shift(30, symptom="up", description="Drinking again")])
    model = Model(
        {
            "Ada Lund": {
                "codings": [
                    {
                        "event": "30",
                        "kind": "shift",
                        "title": "Drinking again",
                        "symptom": "down",
                        "anxiety": "up",
                        "quote": "Drinking again",
                    }
                ]
            }
        }
    )
    event = by_id(fdcoding.code(data, model)[0])[30]
    assert (event["symptom"], event["title"]) == ("up", "Drinking again")
    assert "anxiety" not in event


def test_a_shift_is_coded_from_its_description_and_each_change_says_why():
    # R-0860, R-0868
    data = diagram([shift(31, description="Lost her job at the mill")])
    model = Model(
        {
            "Ada Lund": {
                "codings": [
                    {
                        "event": "31",
                        "kind": "shift",
                        "title": "Lost her job",
                        "functioning": "down",
                        "quote": "lost her job",
                    }
                ]
            }
        }
    )
    coded, decisions = fdcoding.code(data, model)
    event = by_id(coded)[31]
    assert (event["title"], event["functioning"]) == ("Lost her job", "down")
    assert {(d.item, d.field, d.after) for d in decisions} == {
        ("event 31", "title", "Lost her job"),
        ("event 31", "functioning", "down"),
    }
    assert all('"lost her job"' in d.reason for d in decisions)
    assert data["events"][0] == shift(31, description="Lost her job at the mill")


def test_a_dated_happening_in_notes_becomes_an_event_on_its_person_and_a_fact_a_noted_event():
    # R-0860, R-0870
    data = diagram(
        notes="In 1972 Bo was hospitalized for depression. Worked as a nurse in Fairbanks."
    )
    model = Model(
        {
            "Ada Lund": {
                "additions": [
                    {
                        "source": "person 1 notes",
                        "person": "Bo Lund",
                        "kind": "shift",
                        "title": "Hospitalized for depression",
                        "description": "hospitalized for depression",
                        "symptom": "up",
                        "dateTime": "1972-01-01",
                        "dateCertainty": "approximate",
                        "quote": "In 1972 Bo was hospitalized for depression",
                    },
                    {
                        "source": "person 1 notes",
                        "person": "Ada Lund",
                        "kind": "noted",
                        "item": "work",
                        "title": "Worked as nurse",
                        "description": "worked as a nurse in Fairbanks",
                        "dateCertainty": "unknown",
                        "quote": "Worked as a nurse in Fairbanks",
                    },
                ]
            }
        }
    )
    coded, decisions = fdcoding.code(data, model)
    stay, work = coded["events"]
    assert (stay["person"], stay["symptom"], stay["dateTime"]) == (
        3,
        "up",
        "1972-01-01",
    )
    assert (work["person"], work["kind"], work["item"]) == (1, "noted", "work")
    assert "dateTime" not in work
    assert [(d.item, d.field, d.after) for d in decisions] == [
        ("person 1", "notes", "a new shift event: Hospitalized for depression"),
        ("person 1", "notes", "a new noted event: Worked as nurse"),
    ]


def test_a_shift_the_text_does_not_code_becomes_a_noted_event():
    # R-0868
    data = diagram([shift(32, description="Visited the coast")])
    model = Model(
        {
            "Ada Lund": {
                "codings": [
                    {
                        "event": "32",
                        "kind": "noted",
                        "title": "Visited the coast",
                        "quote": "Visited the coast",
                    }
                ]
            }
        }
    )
    event = by_id(fdcoding.code(data, model)[0])[32]
    assert (event["kind"], event["title"]) == ("noted", "Visited the coast")


def test_an_invalid_answer_is_refused_by_name_and_the_shift_kept_as_noted():
    # R-0868
    data = diagram([shift(33, description="Fought with Bo")], notes="Moved to Nome.")
    model = Model(
        {
            "Ada Lund": {
                "codings": [
                    {
                        "event": "33",
                        "kind": "shift",
                        "title": "Fought with brother",
                        "relationship": "anger",
                        "relationshipTargets": ["Bo Lund"],
                        "quote": "Fought with Bo",
                    }
                ],
                "additions": [
                    {
                        "source": "person 1 notes",
                        "person": "Zed Lund",
                        "kind": "noted",
                        "item": "places",
                        "title": "Moved to Nome",
                        "description": "moved to Nome",
                        "dateCertainty": "unknown",
                        "quote": "Moved to Nome",
                    }
                ],
            }
        }
    )
    coded, decisions = fdcoding.code(data, model)
    event = by_id(coded)[33]
    assert (event["kind"], event["title"], event.get("relationship")) == (
        "noted",
        "Fought with Bo",
        None,
    )
    assert len(coded["events"]) == 1
    reasons = " ".join(d.reason for d in decisions)
    assert "relationships" in reasons
    assert "Zed Lund" in reasons


def test_a_description_naming_its_person_is_reworded_and_a_missing_third_person_filled():
    # R-0869
    data = diagram(
        [
            shift(
                34,
                relationship="inside",
                relationshipTargets=[3],
                description="Ada told Bo about Mother's drinking",
            )
        ]
    )
    model = Model(
        {
            "Ada Lund": {
                "codings": [
                    {
                        "event": "34",
                        "kind": "shift",
                        "title": "Told about the drinking",
                        "description": "told about their mother's drinking",
                        "relationship": "conflict",
                        "relationshipTriangles": ["Cy Lund"],
                        "quote": "told Bo about Mother's drinking",
                    }
                ]
            }
        }
    )
    event = by_id(fdcoding.code(data, model)[0])[34]
    assert (event["relationship"], event["relationshipTargets"]) == ("inside", [3])
    assert event["relationshipTriangles"] == [4]
    assert event["description"] == "told about their mother's drinking"
    assert event["notes"] == "Ada told Bo about Mother's drinking"


def test_a_clinicians_guess_codes_nothing():
    # R-0860, R-0868
    data = diagram(notes="Probably a cutoff from her mother.")
    model = Model()
    assert fdcoding.code(data, model) == (data, [])
    assert "Probably a cutoff from her mother." in model.prompts[0]


def test_the_prompt_carries_the_coachs_rules_and_the_rule_against_guesses(monkeypatch):
    # R-0860
    if not key_present():
        pytest.skip("no key opens the private prompts")
    monkeypatch.delenv("FD_PRIVATE_PROMPTS")
    prompts.files.cache_clear()
    data = diagram(notes="Probably a cutoff from her mother.")
    batch = fdcoding.batches(data)[0]
    said = fdcoding.prompt(batch, fdcoding.labels(data))
    assert prompts.files().fragment("agent_record_contract") in said
    assert (
        "A clinician's guess, hypothesis or question is not something that happened"
        in said
    )


def test_a_move_nobody_could_complete_keeps_its_names_with_the_files_values():
    # R-0868, R-0869
    data = diagram(
        [
            shift(
                35,
                description="",
                relationshipTargets=[3],
                fileValues={"relationship": "inside"},
            )
        ]
    )
    coded, decisions = fdcoding.code(data, Model())
    event = by_id(coded)[35]
    assert (event["kind"], event.get("relationshipTargets")) == ("noted", None)
    assert event["fileValues"] == {
        "relationship": "inside",
        "relationshipTargets": "Bo Lund",
    }
    assert ("relationshipTargets", "Bo Lund") in [
        (d.field, d.before) for d in decisions
    ]


def test_people_share_a_call_up_to_its_size_in_file_order(monkeypatch):
    # R-0860
    data = diagram()
    for person in data["people"][:3]:
        person["notes"] = f"{person['name']} kept bees."
    model = Model()
    fdcoding.code(data, model)
    assert [re.search(r"WHO: (.*)", p).group(1) for p in model.prompts] == [
        "Ada Lund; Bo Lund; Cy Lund"
    ]
    monkeypatch.setattr(fdcoding, "PER_CALL", 2)
    model = Model()
    fdcoding.code(data, model)
    assert [re.search(r"WHO: (.*)", p).group(1) for p in model.prompts] == [
        "Ada Lund; Bo Lund",
        "Cy Lund",
    ]


def test_without_the_sops_key_the_open_source_prompt_codes_the_import(
    monkeypatch, tmp_path
):
    # R-0451
    monkeypatch.setenv(prompts.OPEN, "1")
    monkeypatch.delenv("FD_PRIVATE_PROMPTS")
    monkeypatch.delenv("SOPS_AGE_KEY", raising=False)
    monkeypatch.setenv("SOPS_AGE_KEY_FILE", str(tmp_path / "keys.txt"))
    prompts.files.cache_clear()
    said = []

    def model(prompt, response_format, schema, limit):
        said.append(prompt)
        return response_format()

    data = diagram([shift(36, description="Fought with Bo")])
    coded, _ = fdcoding.code(data, model)
    assert prompts.files().dirs == [prompts.PUBLIC]
    [prompt] = said
    assert "**Whose text this is:** Ada Lund" in prompt
    assert "[event 36 description]\nFought with Bo" in prompt
    assert by_id(coded)[36]["kind"] == "noted"
