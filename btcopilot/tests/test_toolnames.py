from btcopilot.schema import DiagramData
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
    assert added(kind="death", person=1) == "Wrenn's death"
