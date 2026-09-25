"""The coach gets first name, last name and birth date before anything else
(Patrick, 2026-09-21), and the account row mirrors what the record holds."""

import pytest

from btcopilot.extensions import db
from btcopilot import profile
from btcopilot.coachturn import CoachTurn
from btcopilot.toolbox import ToolName
from btcopilot.schema import DateCertainty, EventKind
from btcopilot.tests.conftest import Model, called, said, version


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture(autouse=True)
def own_person(test_user):
    """What the first session does: the person's own entry, named "User"."""
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.ensure_chat_defaults()
    diagram.set_diagram_data(data)
    db.session.commit()


def test_an_empty_record_is_missing_all_three(test_user):
    # R-0360
    data = test_user.free_diagram.get_diagram_data()
    assert profile.missing(data) == [
        profile.Required.FirstName,
        profile.Required.LastName,
        profile.Required.BirthDate,
    ]


def test_the_coach_is_told_what_to_get_first(discussion):
    # R-0360
    model = Model(said("What is your name?"))
    CoachTurn(discussion, "I have not been sleeping", model=model).run()
    assert "FIRST, BEFORE ANYTHING ELSE" in model.systems[0]
    assert "first name, last name, birth date" in model.systems[0]


def test_a_complete_profile_lifts_the_gate_and_reaches_the_account(discussion, test_user):
    # R-0360
    model = Model(
        called(
            ToolName.EditPerson,
            id=1,
            name="Wren",
            last_name="Hale",
            version=version(discussion.diagram),
        ),
        called(
            ToolName.EditEvent,
            kind=EventKind.Birth.value,
            child=1,
            date="1980-03-04",
            date_certainty=DateCertainty.Certain.value,
        ),
        said("Thank you, Wren. Now, the sleep."),
    )
    CoachTurn(discussion, "Wren Hale, born 4 March 1980", model=model).run()

    data = test_user.free_diagram.get_diagram_data()
    assert profile.missing(data) == []
    assert (test_user.first_name, test_user.last_name) == ("Wren", "Hale")
    assert test_user.birthdate.isoformat() == "1980-03-04"

    model = Model(said("Tell me about the sleep."))
    CoachTurn(discussion, "It started in college", model=model).run()
    assert "FIRST, BEFORE ANYTHING ELSE" not in model.systems[0]
