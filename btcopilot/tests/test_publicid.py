"""The diagram's public id: the short random id every address and every read
of the page name a diagram by, so its row number never leaves the server.
Invented names only."""

import re

import sqlalchemy as sa
from alembic import command

from btcopilot import diagramjson
from btcopilot.admin.database import config
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.models.diagram import PUBLIC_ID_LENGTH, PUBLIC_ID_LETTERS, new_public_id
from btcopilot.tests.conftest import csrf_token
from btcopilot.tests.test_api import theirs  # noqa: F401
from btcopilot.tests.test_turnbackfill import T0, rows, seed

SHAPE = re.compile(rf"[{PUBLIC_ID_LETTERS}]{{{PUBLIC_ID_LENGTH}}}")
NOBODYS = "nope2nope2"


def another(user, name: str) -> Diagram:
    made = Diagram(user_id=user.id, name=name, data=diagramjson.dumps({}))
    db.session.add(made)
    db.session.commit()
    return made


def test_every_new_diagram_gets_a_public_id_that_is_not_its_row_number(web, test_user):
    # R-0NNN
    made = another(test_user, "Nell's family")
    assert SHAPE.fullmatch(made.public_id)
    assert made.public_id != str(made.id)
    assert len({new_public_id() for _ in range(500)}) == 500


def test_a_listed_diagram_carries_its_public_id_beside_its_row_number(web, test_user):
    # R-0NNN
    [own] = web.get("/app/diagrams").get_json()
    assert own["id"] == test_user.free_diagram_id
    assert own["public_id"] == test_user.free_diagram.public_id
    assert SHAPE.fullmatch(own["public_id"])


def test_the_page_names_the_diagram_it_reads_by_its_public_id(web, test_user, theirs):
    # R-0NNN
    key = test_user.free_diagram.public_id
    for path in ("/app/timeline", "/app/sessions", "/app/statements"):
        assert web.get(path, query_string={"diagram": key}).status_code == 200, path
        # a key no diagram has, and another person's diagram, are not found
        assert web.get(path, query_string={"diagram": NOBODYS}).status_code == 404, path
        assert web.get(path, query_string={"diagram": theirs.public_id}).status_code == 404, path


def test_the_app_is_put_on_a_diagram_by_its_public_id_never_its_row_number(web, test_user):
    # R-0NNN
    made = another(test_user, "Wren's family")
    headers = {"X-CSRFToken": csrf_token(web)}
    put = web.post(f"/app/diagrams/{made.public_id}/select", json={}, headers=headers)
    assert put.status_code == 200
    assert put.get_json()["public_id"] == made.public_id
    db.session.refresh(test_user)
    assert test_user.current_diagram_id == made.id
    assert web.post(f"/app/diagrams/{made.id}/select", json={}, headers=headers).status_code == 404
    assert web.post(f"/app/diagrams/{NOBODYS}/select", json={}, headers=headers).status_code == 404


def test_the_revision_gives_every_stored_diagram_its_own_public_id(flask_app, tmp_path):
    # R-0NNN
    seeded = {table: values for table, values in rows({}, [], []).items() if values}
    seeded["diagrams"].append(
        {"id": 2, "user_id": 1, "name": "Nell", "data": b"{}", "version": 1, "created_at": T0}
    )
    engine = seed(flask_app, tmp_path, seeded, revision="1b00000000c3")
    with flask_app.app_context():
        command.upgrade(config(), "head")
    with engine.connect() as conn:
        given = dict(
            conn.execute(sa.text("SELECT id, public_id FROM diagrams ORDER BY id")).all()
        )
    assert set(given) == {1, 2}
    assert all(SHAPE.fullmatch(key) for key in given.values())
    assert given[1] != given[2]
