"""The one-shot import from the old Pro database, against a stand-in dump built
to the old shape — no birthdate, no preferences, no current diagram."""

import pickle
import sqlite3

import pytest

from btcopilot import diagramjson, proimport
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, User

WHITLOCK = {"people": [{"name": "Marcus Whitlock", "birth": 1951}]}


@pytest.fixture
def dump(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        "create table users (id integer primary key, username text, active boolean,"
        " status text, roles text, first_name text, last_name text, stripe_id text,"
        " free_diagram_id integer)"
    )
    old.execute(
        "create table diagrams (id integer primary key, user_id integer, name text,"
        " alias text, use_real_names boolean, require_password_for_real_names boolean,"
        " version integer, data blob, created_at datetime, updated_at datetime)"
    )
    old.execute(
        "insert into users values (7, 'marcus@fd362-fixture.invalid', 1, 'confirmed',"
        " 'subscriber', 'Marcus', 'Whitlock', null, 11)"
    )
    old.execute(
        "insert into diagrams values (11, 7, 'The Whitlocks', null, 1, 0, 1, ?,"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')",
        (pickle.dumps(WHITLOCK),),
    )
    old.execute(
        "insert into diagrams values (12, 99, 'Nobody''s', null, 1, 0, 1, ?,"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')",
        (pickle.dumps(WHITLOCK),),
    )
    old.execute(
        "insert into diagrams values (13, 7, 'Broken', null, 1, 0, 1, x'00ff',"
        " '2026-01-01 00:00:00', '2026-01-02 00:00:00')"
    )
    old.commit()
    old.close()
    return f"sqlite:///{path}"


def test_dry_run_counts_and_writes_nothing(flask_app, dump):
    result = proimport.run(dump, apply=False)
    assert (result.users.read, result.users.written) == (1, 1)
    assert (result.diagrams.read, result.diagrams.written) == (3, 1)
    assert (result.diagrams.skipped, result.diagrams.failed) == (1, 1)
    assert db.session.query(User).count() == 0


def test_every_failure_is_named_with_its_reason(flask_app, dump):
    result = proimport.run(dump, apply=False)
    assert len(result.failures) == 1
    assert result.failures[0].startswith("diagram 13:")


def test_apply_writes_the_person_their_diagram_as_json(flask_app, dump):
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
    proimport.run(dump, apply=True)
    again = proimport.run(dump, apply=True)
    assert (again.users.skipped, again.users.written) == (1, 0)
    assert db.session.query(User).count() == 1
