"""What the watcher after a coach turn writes down: repeated people, repeated
events, and adds made before any read. It only writes rows; the turn is never
changed or refused.

Invented names only.
"""

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot import turns
from btcopilot.models import Observation, ObservationKind
from btcopilot.schema import DiagramData
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, csrf_token, said
from btcopilot.tests.test_turnhistory import Breaks, coach, post, resume

WREN = {"id": 1, "name": "Wren"}
NELL = {"id": 2, "name": "Nell", "last_name": "Hale"}
NELL_BORN = {"id": 3, "kind": "birth", "child": 2, "dateTime": "1990-01-04"}
MOVED = {
    "id": 4,
    "kind": "noted",
    "person": 1,
    "dateTime": "2000-03-01",
    "description": "Moved to Arizona",
}


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def token(web):
    return csrf_token(web)


def record(test_user, people=(), events=()):
    items = [WREN, *people, *events]
    test_user.free_diagram.set_diagram_data(
        DiagramData(
            people=[WREN, *people],
            events=list(events),
            lastItemId=max(item["id"] for item in items),
        )
    )
    db.session.commit()


def seen() -> list[tuple]:
    return [
        (row.kind, row.detail) for row in Observation.query.order_by(Observation.id)
    ]


def test_a_person_added_again_with_the_same_name_and_birth_year_is_written_down(
    web, token, test_user, monkeypatch
):
    # R-0481, R-0482
    record(test_user, [NELL], [NELL_BORN])
    coach(
        monkeypatch,
        Model(
            called(ToolName.ReadPeople),
            called(ToolName.EditPerson, name="Nell", last_name="Hale"),
            called(ToolName.EditEvent, kind="birth", child=4, date="1990-07-30", date_certainty="certain"),
            said("Nell is in."),
        ),
    )
    post(web, token)
    assert seen() == [
        (
            ObservationKind.DuplicatePerson,
            {"ids": [2, 4], "same": ["nell hale", "1990"]},
        )
    ]
    assert [p["id"] for p in test_user.free_diagram.get_diagram_data().people] == [
        1,
        2,
        4,
    ]


def test_an_event_changed_to_match_another_on_kind_date_and_people_is_written_down(
    web, token, test_user, monkeypatch
):
    # R-0481, R-0482
    record(test_user, events=[MOVED, dict(MOVED, id=5, dateTime="2000-09-01")])
    version = test_user.free_diagram.version
    coach(
        monkeypatch,
        Model(
            called(ToolName.ReadEvents),
            called(ToolName.EditEvent, id=5, date="2000-03-01", version=version, date_certainty="certain"),
            said("That move is in March, then."),
        ),
    )
    post(web, token, "We moved in March 2000.")
    assert [(kind, detail["ids"]) for kind, detail in seen()] == [
        (ObservationKind.DuplicateEvent, [4, 5])
    ]


def test_a_repeat_the_turn_did_not_touch_is_not_written_down_again(
    web, token, test_user, monkeypatch
):
    # R-0482
    twin = dict(NELL, id=5)
    twin_born = dict(NELL_BORN, id=6, child=5)
    record(test_user, [NELL, twin], [NELL_BORN, twin_born])
    coach(
        monkeypatch,
        Model(
            called(ToolName.ReadPeople),
            called(ToolName.EditPerson, name="Colm"),
            said("Colm is in."),
        ),
    )
    post(web, token, "My brother is Colm.")
    assert seen() == []


def test_an_add_before_any_read_is_written_down(web, token, test_user, monkeypatch):
    # R-0479, R-0482
    record(test_user)
    coach(
        monkeypatch,
        Model(
            called(ToolName.EditPerson, name="Nell"),
            called(ToolName.ReadPeople),
            said("Nell is in."),
        ),
    )
    post(web, token)
    assert seen() == [
        (
            ObservationKind.AddWithoutRead,
            {"calls": [{"name": "edit_person", "args": {"name": "Nell"}}]},
        )
    ]


def test_a_failed_turn_is_written_down_and_trying_again_does_not_write_it_twice(
    web, token, test_user, monkeypatch
):
    # R-0477, R-0482
    record(test_user)
    coach(monkeypatch, Breaks(called(ToolName.EditPerson, name="Nell")))
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token).get_json()
    with pytest.raises(RuntimeError):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert [kind for kind, _ in seen()] == [ObservationKind.AddWithoutRead]

    coach(monkeypatch, Model(said("Nell is your sister, then.")))
    resume(web, token, body["turn_id"])
    assert [kind for kind, _ in seen()] == [ObservationKind.AddWithoutRead]
