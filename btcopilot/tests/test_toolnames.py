import pytest

from btcopilot.schema import DiagramData
from btcopilot.timeline import event_label
from btcopilot.toolbox import ToolName
from btcopilot.toolnames import names

DATA = DiagramData(people=[{"id": 1, "name": "Wrenn"}, {"id": 2, "name": "Bo"}])


def added(**args) -> str:
    return names(DATA, ToolName.EditEvent.value, args)["it"]


def test_an_event_with_no_words_is_named_by_its_kind_and_who_it_is_about():
    # R-0478
    assert added(kind="noted", person=1) == "a note about Wrenn"
    assert added(kind="shift", person=1, spouse=2) == "a shift about Wrenn & Bo"
    assert added(person=1) == "an event about Wrenn"
    assert added(kind="shift", person=1, symptom="up") == "Wrenn's symptoms got worse"
    assert added(kind="noted", person=1, description="Moved to Leeds") == "Moved to Leeds"


def test_a_tool_line_names_an_event_the_way_the_list_does():
    # R-0478
    people = {1: DATA.people[0]}
    for event in (
        {"kind": "noted", "person": 1, "description": "Moved to Leeds"},
        {"kind": "shift", "person": 1, "description": "Stopped sleeping", "symptom": "up"},
    ):
        assert added(**event) == event_label(event, people)


@pytest.mark.parametrize(
    "event, line",
    [
        ({"kind": "death", "person": 1}, "Wrenn \u00b7 died"),
        (
            {"kind": "death", "person": 1, "description": "died, possibly around July 4"},
            "Wrenn \u00b7 died, possibly around July 4",
        ),
        ({"kind": "birth", "child": 1}, "Wrenn \u00b7 born"),
        ({"kind": "married", "person": 1, "spouse": 2}, "Wrenn & Bo \u00b7 married"),
        (
            {"kind": "married", "person": 1, "spouse": 2, "description": "in Reno"},
            "Wrenn & Bo \u00b7 married \u00b7 in Reno",
        ),
        ({"kind": "bonded", "person": 1, "spouse": 2}, "Wrenn & Bo \u00b7 bonded"),
        ({"kind": "divorced", "person": 1, "spouse": 2}, "Wrenn & Bo \u00b7 divorced"),
        ({"kind": "separated", "person": 1, "spouse": 2}, "Wrenn & Bo \u00b7 separated"),
        ({"kind": "adopted", "child": 1}, "Wrenn \u00b7 adopted"),
    ],
)
def test_a_tool_line_names_a_kind_event_by_who_and_the_shared_label(event, line):
    # R-0478
    people = {p["id"]: p for p in DATA.people}
    assert added(**event) == line
    assert line.endswith(event_label(event, people))
