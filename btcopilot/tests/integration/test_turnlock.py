"""A coach turn on Postgres, the database production runs: a write the record
refuses leaves the record's row free, so the model call after it can write its
ledger row on its own connection. SQLite has no row locks, so only Postgres
shows a turn that waits on itself."""

from types import SimpleNamespace

import pytest

from btcopilot.coachturn import CoachTurn
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Purpose
from btcopilot.schema import Person, asdict
from btcopilot.tables import TABLES
from btcopilot.tests.conftest import Model, called, said, wrote
from btcopilot.tests.fixtures import make_app
from btcopilot.toolbox import ToolName

pytestmark = pytest.mark.integration


@pytest.fixture
def flask_app(tmp_path, postgres):
    # a turn that waits on itself fails here in seconds instead of hanging
    waits = {"connect_args": {"options": "-c lock_timeout=5s"}}
    app = make_app(
        SimpleNamespace(
            param={"SQLALCHEMY_DATABASE_URI": postgres, "SQLALCHEMY_ENGINE_OPTIONS": waits}
        ),
        tmp_path,
        TABLES,
    )
    yield next(app)
    # the database is dropped whole; dropping its tables one by one trips on
    # the cycle between sessions and speakers
    db.session.remove()
    db.engine.dispose()
    app.close()


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


@pytest.fixture
def wren(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_a_refused_write_does_not_stall_the_next_model_call(discussion, wren):
    # R-0388, R-0597, R-0628
    reply = CoachTurn(
        discussion,
        "My dad moved out in 1994.",
        purpose=Purpose.Replay,
        model=Model(
            called(
                ToolName.EditEvent,
                kind="shift",
                date="1994-12-01",
                description="moved out",
                person=1,
                date_certainty="certain",
            ),
            said("What changed for you when he left?"),
        ),
        scratch=True,
    ).run()
    assert reply["statement"] == "What changed for you when he left?"
    # the coach's two calls, then the session's title and summary
    assert ModelCall.query.filter_by(purpose=Purpose.Replay).count() == 4
