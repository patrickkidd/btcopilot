"""People on the user's own diagram: the same command log the coach writes
through, authored by the user."""

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Author, Change
from btcopilot.schema import Person, PersonKind, asdict
from btcopilot.tests.personal.conftest import csrf_token


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren", gender=PersonKind.Female))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def people(diagram):
    db.session.refresh(diagram)
    return diagram.get_diagram_data().people


def test_adding_someone_writes_them_and_logs_it_as_the_user(web, family):
    token = csrf_token(web)
    added = web.post(
        "/personal/people",
        json={"name": "Bo", "gender": "male"},
        headers={"X-CSRFToken": token},
    )
    assert added.status_code == 201
    assert added.get_json()["name"] == "Bo"

    stored = [p for p in people(family) if p["name"] == "Bo"]
    assert len(stored) == 1
    assert Change.query.order_by(Change.id.desc()).first().author is Author.User


def test_changing_someone_keeps_their_id(web, family):
    token = csrf_token(web)
    changed = web.patch(
        "/personal/people/1",
        json={"name": "Wren", "last_name": "Ellis"},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert changed == {
        "id": 1,
        "name": "Wren",
        "last_name": "Ellis",
        "gender": "female",
        "notes": None,
    }


def test_a_field_the_record_has_no_room_for_is_refused(web, family):
    token = csrf_token(web)
    refused = web.patch(
        "/personal/people/1",
        json={"birthDate": "1980-01-01"},
        headers={"X-CSRFToken": token},
    )
    assert refused.status_code == 400
    assert "birthDate" in refused.get_data(as_text=True)


def test_removing_someone_takes_them_off_the_record(web, family):
    token = csrf_token(web)
    gone = web.delete("/personal/people/1", headers={"X-CSRFToken": token})
    assert gone.status_code == 204
    assert people(family) == []
