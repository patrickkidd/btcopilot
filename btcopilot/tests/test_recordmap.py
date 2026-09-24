"""The coach is handed a map of the record rather than the record, and reads
what it needs: chosen events with the words they came from, and the latest
changes. Invented names only."""

import pytest

from btcopilot import recordtext
from btcopilot.coachturn import CoachTurn
from btcopilot.extensions import db
from btcopilot.schema import DiagramData, Person, asdict
from btcopilot.toolbox import ToolName, Toolbox
from btcopilot.tests.conftest import Model, called, said, version


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren")), asdict(Person(id=2, name="Bo"))]
    data.events = [{"id": 3, "kind": "noted", "person": 1, "dateTime": "1990-01-01"}]
    data.lastItemId = 3
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_the_map_shows_who_and_when_but_not_what_happened():
    # R-0479
    data = DiagramData(
        people=[
            {"id": 1, "name": "Wren"},
            {"id": 2, "name": "Bo"},
            {"id": 3, "name": "Ash"},
        ],
        pair_bonds=[{"id": 4, "person_a": 1, "person_b": 3, "married": True}],
        events=[
            {"id": 5, "kind": "birth", "child": 2, "dateTime": "1960-02-01"},
            {"id": 6, "kind": "death", "person": 2, "dateTime": "2010-03-01"},
            {
                "id": 7,
                "kind": "shift",
                "person": 1,
                "relationshipTargets": [3],
                "dateTime": "1994-06-01",
                "description": "moved out",
            },
            {"id": 8, "kind": "noted", "person": 1, "description": "a quiet year"},
        ],
        clusters=[
            {"id": "c1", "name": "Leaving", "source": "user", "eventIds": [6, 7]}
        ],
    )
    text = recordtext.outline(data, 7, speaker=1)
    lines = text.splitlines()
    assert f"1 Wren events=2{recordtext.SPEAKER}" in lines
    assert "2 Bo born=1960 died=2010 events=2" in lines
    assert "3 Ash events=1" in lines
    assert "4 1+3 married" in lines
    assert 'c1 "Leaving" (user) 1994-2010 events=2' in lines
    assert "1960s 1, 1990s 1, 2010s 1, undated 1" in lines
    assert lines[-1] == "Record version 7."
    assert "moved out" not in text and "quiet" not in text


def test_the_coach_reads_chosen_events_with_the_words_they_came_from(
    discussion, family
):
    # R-0479
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    db.session.commit()
    CoachTurn(
        discussion,
        "My dad left in 1994.",
        model=Model(
            called(
                ToolName.EditEvent,
                kind="noted",
                person=2,
                date="1994-06-01",
                date_certainty="certain",
                description="left",
                notes="He took the car",
            ),
            said("I put that down."),
        ),
    ).run()
    CoachTurn(
        discussion,
        "Actually it was 1995.",
        model=Model(
            called(
                ToolName.EditEvent,
                id=4,
                date="1995-06-01",
                version=version(family),
            ),
            said("Changed it."),
        ),
    ).run()

    tools = Toolbox(family.id, "t3")
    text, _ = tools.call(
        ToolName.ReadEvents.value, {"ids": [4], "words": True, "notes": True}
    )
    assert text.splitlines()[:3] == [
        '4 1995-06-01 [noted] person=2 "left" (has notes)',
        "  words: My dad left in 1994.",
        "  notes: He took the car",
    ]
    bare, _ = tools.call(ToolName.ReadEvents.value, {"ids": [4]})
    assert bare.splitlines()[1] == ""


def test_the_latest_changes_come_newest_first_with_the_version_each_made(family):
    # R-0479, R-0480
    tools = Toolbox(family.id, "t1")
    for name in ("Ada", "Ada Hale"):
        tools.call(
            ToolName.EditPerson.value,
            {"id": 1, "name": name, "version": version(family)},
        )
    now = version(family)

    text, _ = tools.call(ToolName.ReadChanges.value, {"limit": 1})
    assert text.splitlines() == [
        f'Version {now}, coach: person 1 name="Ada Hale"',
        "",
        f"Record version {now}.",
    ]
    every, _ = tools.call(ToolName.ReadChanges.value, {})
    assert every.splitlines()[1] == f'Version {now - 1}, coach: person 1 name="Ada"'


def test_an_empty_record_still_carries_its_version():
    # R-0479
    assert recordtext.outline(DiagramData(), 0) == "Record version 0."
