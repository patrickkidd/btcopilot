import pytest

from btcopilot.schema import DiagramData
from btcopilot.timeline import event_label
from btcopilot.toolbox import ToolName
from btcopilot.toolnames import names

DATA = DiagramData(people=[{"id": 1, "name": "Wrenn"}, {"id": 2, "name": "Bo"}])


def added(**args) -> str:
    return names(DATA, ToolName.EditEvent.value, args)["it"]


def test_an_event_with_no_description_is_named_by_its_title():
    # R-0478, R-0681
    assert added(kind="noted", person=1, title="Moved to Leeds") == "Moved to Leeds"
    assert added(kind="shift", person=1, spouse=2, title="Grew apart") == "Grew apart"
    assert added(kind="shift", person=1, symptom="up", title="Stopped sleeping") == "Stopped sleeping"


def test_a_tool_line_names_an_event_the_way_the_list_does():
    # R-0478
    people = {1: DATA.people[0]}
    for event in (
        {"kind": "noted", "person": 1, "title": "Moved to Leeds", "description": "Took the job up north"},
        {"kind": "shift", "person": 1, "title": "Stopped sleeping", "description": "Lay awake most nights", "symptom": "up"},
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
