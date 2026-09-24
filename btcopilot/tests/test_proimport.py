"""The import module: the one-shot read of the old Pro database, against a
stand-in dump built to the old shape — no birthdate, no preferences, no current
diagram — and the in-place conversion of this database's pickled rows."""

import importlib.util
import pickle

import pytest

from btcopilot import diagramjson, proimport
from btcopilot.extensions import db
from btcopilot.models import Diagram, User
from btcopilot.personal.recordtext import render
from btcopilot.tests.olddump import WHITLOCK, build


@pytest.fixture
def dump(tmp_path):
    return f"sqlite:///{build(tmp_path / 'old.db')}"


def test_dry_run_counts_and_writes_nothing(flask_app, dump):
    # R-0327
    result = proimport.run(dump, apply=False)
    assert (result.users.read, result.users.written) == (1, 1)
    assert (result.diagrams.read, result.diagrams.written) == (3, 1)
    assert (result.diagrams.skipped, result.diagrams.failed) == (1, 1)
    assert db.session.query(User).count() == 0


def test_every_failure_is_named_with_its_reason(flask_app, dump):
    # R-0327
    result = proimport.run(dump, apply=False)
    assert len(result.failures) == 1
    assert result.failures[0].startswith("diagram 13:")


def test_apply_writes_the_person_their_diagram_as_json(flask_app, dump):
    # R-0327
    proimport.run(dump, apply=True)
    user = db.session.query(User).one()
    assert user.username == "marcus@fd362-fixture.invalid"
    assert user.password == ""
    diagram = db.session.query(Diagram).one()
    assert diagram.user_id == user.id
    assert diagramjson.is_json(diagram.data)
    assert diagramjson.loads(diagram.data) == WHITLOCK
    assert user.free_diagram_id == diagram.id


def test_a_second_run_writes_nobody_twice(flask_app, dump):
    # R-0327
    proimport.run(dump, apply=True)
    again = proimport.run(dump, apply=True)
    assert (again.users.skipped, again.users.written) == (1, 0)
    assert db.session.query(User).count() == 1


OLD = {
    "people": [
        {"id": 1, "name": "Ada", "parents": 30},
        {"id": 2, "name": "Ben"},
        {"id": 3, "name": "Cass"},
        {"id": 4, "name": "Dov"},
    ],
    "pair_bonds": [{"id": 30, "person_a": 2, "person_b": 3, "married": True}],
    "events": [
        {"id": 12, "kind": "shift", "person": 1, "dateTime": "2011-05-01",
         "description": "moved away", "anxiety": "up", "functioning": "down",
         "relationship": "distance", "relationshipTargets": [2, 3]},
        {"id": 13, "kind": "shift", "person": 1, "dateTime": "2012-01-15",
         "description": "took his side", "relationship": "inside",
         "relationshipTargets": [2], "relationshipTriangles": [3, 4]},
    ],
    "lastItemId": 30,
}


def _migrated(user) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Old")
    diagram.data = pickle.dumps(OLD)
    db.session.add(diagram)
    db.session.commit()
    proimport.convert_rows()
    return diagram


def test_an_old_diagrams_timeline_moves_come_across_and_the_coach_reads_them(test_user):
    # R-0052
    diagram = _migrated(test_user)
    assert diagramjson.is_json(diagram.data)
    record = render(diagram.get_diagram_data())
    assert (
        '12 2011-05-01 [shift] person=1 "moved away" anxiety=up functioning=down '
        "relationship=distance targets=[2, 3]"
    ) in record
    assert "relationship=inside targets=[2] triangles=[3, 4]" in record


def test_an_old_diagrams_families_and_bonds_come_across(test_user):
    # R-0052
    diagram = _migrated(test_user)
    record = render(diagram.get_diagram_data())
    assert "1 Ada parents=30" in record
    assert "30 2+3 married" in record


def test_the_old_reader_and_the_row_converter_are_one_module():
    # R-0422
    assert importlib.util.find_spec("btcopilot.diagrams") is None
    assert callable(proimport.run) and callable(proimport.convert_rows)

