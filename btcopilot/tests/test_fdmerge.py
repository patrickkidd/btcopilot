import pytest

from btcopilot import fdmerge, prompts
from btcopilot.schema import from_dict

PLAIN = """---
name: import_merge
---
FILE {{ file }}
DIAGRAM {{ diagram }}
PEOPLE {{ people }}
EVENTS {{ events }}
"""


@pytest.fixture(autouse=True)
def plain(tmp_path, monkeypatch):
    """A plain stand-in for the private prompt, so the pass runs without a key."""
    (tmp_path / "import_merge.prompty").write_text(PLAIN)
    monkeypatch.setenv("FD_PRIVATE_PROMPTS", str(tmp_path))
    prompts.files.cache_clear()
    yield
    prompts.files.cache_clear()


class Model:
    def __init__(self, answer: dict | None = None):
        self.answer = answer or {}
        self.prompts = []
        self.schemas = []

    def __call__(self, prompt, response_format, schema, limit):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return from_dict(response_format, self.answer)


def birth(id, child, day, person=None, spouse=None, **more) -> dict:
    event = {
        "id": id,
        "kind": "birth",
        "child": child,
        "dateTime": day,
        "dateCertainty": "certain",
        **more,
    }
    if person is not None:
        event.update(person=person, spouse=spouse)
    return event


def existing(events=()) -> dict:
    """The diagram from the conversation: Ada, her father and her mother not
    yet named."""
    return {
        "people": [
            {
                "id": 3,
                "name": "Ada",
                "last_name": "Lund",
                "gender": "female",
                "parents": 6,
                "primary": True,
            },
            {"id": 4, "name": "Cy", "last_name": "Lund", "gender": "male"},
            {"id": 5, "name": "Ada's mother", "gender": "female"},
        ],
        "pair_bonds": [{"id": 6, "person_a": 4, "person_b": 5, "married": True}],
        "events": [birth(7, 3, "1980-03-01", 4, 5), *events],
        "questions": [],
        "lastItemId": 7,
    }


def imported(events=()) -> dict:
    """The desktop file: Ada, her parents by name, and a brother."""
    return {
        "tags": ["family"],
        "people": [
            {
                "id": 3,
                "name": "Ada",
                "last_name": "Lund",
                "gender": "female",
                "parents": 7,
                "primary": True,
                "nickName": "Addy",
            },
            {"id": 4, "name": "Cy", "last_name": "Lund", "gender": "male"},
            {"id": 5, "name": "Eva", "last_name": "Berg", "gender": "female"},
            {
                "id": 6,
                "name": "Bo",
                "last_name": "Lund",
                "gender": "male",
                "parents": 7,
            },
        ],
        "pair_bonds": [
            {
                "id": 7,
                "person_a": 4,
                "person_b": 5,
                "married": True,
                "notes": "Met at school",
            }
        ],
        "events": [
            birth(8, 3, "1980-03-02", 4, 5, notes="Born at home"),
            birth(9, 6, "1983-06-01", 4, 5),
            *events,
        ],
    }


def person(data: dict, name: str) -> dict:
    return next(p for p in data["people"] if p.get("name") == name)


def verdict(person, candidate, said, reason="Their family fits.") -> dict:
    return {"person": person, "candidate": candidate, "verdict": said, "reason": reason}


def test_the_rules_join_a_matched_person_and_add_the_rest():
    # R-0851, R-0853, R-0850
    model = Model({"people": [verdict("file 10", "diagram 5", "different")]})
    data, decisions, held = fdmerge.merge(existing(), imported(), model)
    names = sorted(p["name"] for p in data["people"])
    assert names == ["Ada", "Ada's mother", "Bo", "Cy", "Eva"]
    ada = person(data, "Ada")
    assert (ada["id"], ada["nickName"]) == (3, "Addy")
    assert min(p["id"] for p in data["people"] if p["name"] in ("Bo", "Eva")) > 7
    births = [e for e in data["events"] if e["kind"] == "birth" and e["child"] == 3]
    assert len(births) == 1
    assert (births[0]["dateTime"], births[0]["notes"]) == ("1980-03-01", "Born at home")
    assert any(
        d.item == "event 8" and d.field == "dateTime" and d.before == "1980-03-02"
        for d in decisions
    )
    assert held == []


def test_a_person_placed_by_position_is_asked_once_per_family_and_takes_the_files_name():
    # R-0851, R-0853, R-0867
    model = Model({"people": [verdict("file 10", "diagram 5", "same")]})
    data, decisions, held = fdmerge.merge(existing(), imported(), model)
    assert len(model.prompts) == 1
    assert "Eva Berg" in model.prompts[0] and "Ada's mother" in model.prompts[0]
    mother = next(p for p in data["people"] if p["id"] == 5)
    assert (mother["name"], mother["last_name"]) == ("Eva", "Berg")
    assert any(
        d.field == "name" and d.after == "Eva" and 'only "Ada\'s mother"' in d.reason
        for d in decisions
    )
    assert [b["notes"] for b in data["pair_bonds"]] == ["Met at school"]
    bo = person(data, "Bo")
    assert bo["parents"] == 6
    assert any("Judged the same person" in d.reason for d in decisions)
    assert held == []


def test_an_unsure_person_becomes_a_held_question_naming_the_candidate():
    # R-0851, R-0852
    model = Model({"people": [verdict("file 10", "diagram 5", "unsure")]})
    data, decisions, held = fdmerge.merge(existing(), imported(), model)
    eva = person(data, "Eva")
    assert [(q["text"], q["item_kind"], q["item_id"], q["state"]) for q in held] == [
        (
            "Is your mother the Eva Berg, partner of Cy Lund, in the file?",
            "person",
            str(eva["id"]),
            "held",
        )
    ]
    assert person(data, "Ada's mother")["id"] == 5


def test_an_answer_it_was_not_asked_is_refused_by_name_and_counts_as_unsure():
    # R-0851, R-0453, R-0579
    model = Model({"people": [verdict("file 10", "diagram 4", "same")]})
    data, decisions, held = fdmerge.merge(existing(), imported(), model)
    assert len(held) == 1
    assert any(
        d.item == "person 5"
        and "was refused: it judged file 10 against diagram 4" in d.reason
        for d in decisions
    )


def shift(id, person, day, **more) -> dict:
    return {
        "id": id,
        "kind": "shift",
        "person": person,
        "dateTime": day,
        "dateCertainty": "certain",
        **more,
    }


@pytest.mark.parametrize("said, count", [("same", 1), ("different", 2)])
def test_same_day_events_of_a_matched_person_are_judged_by_their_words(said, count):
    # R-0851, R-0877, R-0874
    ours = shift(
        20,
        3,
        "2001-05-01",
        symptom="up",
        title="Panic attacks",
        description="Panic attacks",
        notes="At work",
    )
    theirs = shift(
        30,
        3,
        "2001-05-01",
        anxiety="up",
        title="Anxious at work",
        description="Anxious at work",
        notes="Boss left",
    )
    model = Model(
        {
            "people": [verdict("file 23", "diagram 5", "unsure")],
            "events": [
                {
                    "event": "file event 28",
                    "other": "diagram event 20",
                    "verdict": said,
                    "reason": "Both tell of work.",
                }
            ],
        }
    )
    data, decisions, held = fdmerge.merge(existing([ours]), imported([theirs]), model)
    shifts = [e for e in data["events"] if e["kind"] == "shift"]
    assert len(model.prompts) == 1
    assert len(shifts) == count
    if said == "same":
        assert (shifts[0]["symptom"], shifts[0]["anxiety"], shifts[0]["notes"]) == (
            "up",
            "up",
            "At work\n\nBoss left",
        )


@pytest.mark.parametrize("said, count", [("same", 1), ("unsure", 2)])
def test_a_couple_event_is_one_only_once_the_couple_is(said, count):
    # R-0851
    ours = {
        "id": 8,
        "kind": "married",
        "person": 4,
        "spouse": 5,
        "dateTime": "1975-01-01",
        "dateCertainty": "approximate",
    }
    theirs = {
        "id": 20,
        "kind": "married",
        "person": 4,
        "spouse": 5,
        "dateTime": "1975-06-01",
        "dateCertainty": "certain",
    }
    model = Model({"people": [verdict("file 11", "diagram 5", said)]})
    data, decisions, held = fdmerge.merge(existing([ours]), imported([theirs]), model)
    married = [e for e in data["events"] if e["kind"] == "married"]
    assert len(married) == count
    assert len(held) == count - 1


def test_the_model_reads_an_approximate_date_as_about_its_year():
    # R-0851, R-0877
    ours = shift(
        20,
        3,
        "2001-05-01",
        dateCertainty="approximate",
        symptom="up",
        title="Panic attacks",
        description="Panic attacks",
    )
    theirs = shift(
        30,
        3,
        "2001-05-01",
        anxiety="up",
        title="Anxious at work",
        description="Anxious at work",
    )
    eva = birth(31, 5, "1955-01-01", dateCertainty="approximate")
    model = Model({"people": [verdict("file 23", "diagram 5", "unsure")]})
    fdmerge.merge(existing([ours]), imported([theirs, eva]), model)
    [prompt] = model.prompts
    assert "shift about 2001;" in prompt and "shift on 2001-05-01;" in prompt
    assert "born about 1955" in prompt and "born 1980-03-01" in prompt


def test_words_naming_a_joined_person_by_the_diagrams_name_go_to_the_notes():
    # R-0457, R-0851
    fought = shift(
        20,
        6,
        "2001-05-01",
        relationship="conflict",
        relationshipTargets=[4],
        title="Fought with Cy",
        description="Fought with Cy",
    )
    file = imported([fought])
    file["people"][1].update(name="Cyrus", nickName="Cy")
    data, decisions, held = fdmerge.merge(existing(), file, Model())
    [event] = [e for e in data["events"] if e["kind"] == "shift"]
    assert event["relationshipTargets"] == [4]
    assert "Cy" not in event["title"] + event["description"]
    assert event["notes"] == "Fought with Cy"
    assert {d.field for d in decisions if d.item == "event 20"} >= {"title", "notes"}


def test_the_question_names_what_tells_the_two_apart():
    # R-0852, R-0851
    ours = existing([birth(8, 5, "1959-01-01", dateCertainty="approximate")])
    ours["people"][2]["name"] = "Karen"
    file = imported([birth(31, 5, "1961-04-01")])
    file["people"][2].update(name="Karen", last_name="Smith")
    model = Model({"people": [verdict("file 11", "diagram 5", "unsure")]})
    data, decisions, held = fdmerge.merge(ours, file, model)
    assert [q["text"] for q in held] == [
        "Is your mother Karen, born 1959, the Karen Smith born 1961 in the file?"
    ]


@pytest.mark.parametrize(
    "pairing, count",
    [(fdmerge.Pairing.SameDay, 2), (fdmerge.Pairing.TwoYears, 1)],
)
def test_events_of_a_joined_person_within_two_years_of_any_kind_go_to_the_model(
    pairing, count
):
    # R-0877, R-0874, R-0851
    ours = shift(20, 3, "2001-05-01", title="Panic attacks", notes="At work")
    theirs = {
        "id": 30,
        "kind": "noted",
        "person": 3,
        "dateTime": "2002-02-01",
        "dateCertainty": "certain",
        "description": "Panic attacks at the office",
        "notes": "Boss left",
    }
    model = Model(
        {
            "events": [
                {
                    "event": "file event 28",
                    "other": "diagram event 20",
                    "verdict": "same",
                    "reason": "Both tell of the panic attacks.",
                }
            ]
        }
    )
    data, decisions, held = fdmerge.merge(
        existing([ours]), imported([theirs]), model, pairing=pairing
    )
    told = [e for e in data["events"] if e["kind"] in ("shift", "noted")]
    assert len(told) == count
    assert ("file event 28" in "".join(model.prompts)) is (count == 1)
    if count == 1:
        assert told[0]["notes"] == "At work\n\nBoss left"


@pytest.mark.parametrize("shown", list(fdmerge.Shown))
def test_more_shows_notes_events_grandparents_why_and_the_persons_own_words(shown):
    # R-0851, R-0853
    file = imported([shift(30, 5, "1979-06-01", title="Moved to Oslo")])
    file["people"][2]["notes"] = "Grew up in Bergen"
    model = Model()
    fdmerge.merge(
        existing(),
        file,
        model,
        shown=shown,
        statements=["My dad Cy drove trucks. I loved the summers."],
    )
    said = "".join(model.prompts)
    more = [
        'notes: "Grew up in Bergen"',
        "events: 1979 Moved to Oslo",
        "the rules were unsure because: only their place in the family fits",
        "in the conversation they are the person's father",
        'the person said: "My dad Cy drove trucks."',
    ]
    assert [w in said for w in more] == [shown is fdmerge.Shown.More] * len(more)
    assert "I loved the summers" not in said


@pytest.mark.parametrize("said, count", [("same", 1), ("different", 2)])
def test_an_event_the_file_tells_twice_is_judged_first(said, count):
    # R-0877, R-0874
    lost = shift(30, 6, "1990-03-01", title="Lost his job at the mill", notes="Shut")
    again = shift(31, 6, "1990-09-01", title="Lost the mill job", notes="Moved home")
    model = Model(
        {
            "events": [
                {
                    "event": "file event 16",
                    "other": "file event 15",
                    "verdict": said,
                    "reason": "One job lost.",
                }
            ]
        }
    )
    data, decisions, held = fdmerge.merge(existing(), imported([lost, again]), model)
    assert "against file event 15" in model.prompts[0]
    told = [e for e in data["events"] if e["kind"] == "shift"]
    assert len(told) == count
    if count == 1:
        assert told[0]["notes"] == "Shut\n\nMoved home"


def test_the_stand_in_takes_the_files_main_person_and_keeps_the_mark():
    # R-0871, R-0851
    stand_in = {
        "people": [{"id": 1, "name": "User", "primary": True}],
        "pair_bonds": [],
        "events": [],
        "questions": [],
        "lastItemId": 1,
    }
    data, decisions, held = fdmerge.merge(stand_in, imported(), Model())
    [you] = [p for p in data["people"] if p.get("primary")]
    assert (you["id"], you["name"]) == (1, "Ada")
    assert not [d for d in decisions if d.field == "primary"]
    assert any(
        d.after == "person 1"
        and d.reason
        == "The app's stand-in for the person takes the desktop file's main person."
        for d in decisions
    )


def test_the_files_main_person_loses_the_mark_to_a_named_one_they_are_not():
    # R-0851
    other = existing()
    other["people"][0].update(name="Wren", last_name="Hale")
    data, decisions, held = fdmerge.merge(other, imported(), Model())
    assert [p["name"] for p in data["people"] if p.get("primary")] == ["Wren"]
    assert any(
        d.field == "primary" and d.reason == "The diagram already says who it is about."
        for d in decisions
    )
