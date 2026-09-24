"""The one-shot import from the old Pro database, against a stand-in dump built
to the old shape — no birthdate, no preferences, no current diagram."""

import pytest

from btcopilot import diagramjson, proimport
from btcopilot.extensions import db
from btcopilot.models import Diagram, User
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
