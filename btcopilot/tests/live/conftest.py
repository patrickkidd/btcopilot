"""The live venue: one real coach turn on the private prompts, and the record it
leaves behind. It costs money and needs the prompts' key, so it never runs on CI
(R-0451). It always spends on ANTHROPIC_TESTING_KEY, never ANTHROPIC_API_KEY
(production's key); there is no fallback to the production key. Run it by hand:

    SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt uv run pytest \
        btcopilot/btcopilot/tests/live --e2e

Without --e2e every test here is skipped; with it and no key (either key), every
test fails.

A run checks the balance with one 1-token call first, charges every model call
at the app's own prices, stops at its cap, prints what it spent and leaves one
results file; `python -m btcopilot.tests.live.passrate` reads them back.
"""

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import event

from btcopilot.coachmodel import CoachModel
from btcopilot import turnlog
from btcopilot.extensions import db
from btcopilot.models import ModelCall
from btcopilot.promptdir import key_present
from btcopilot.schema import DiagramData
from btcopilot.tests.conftest import csrf_token, replied
from btcopilot.tests.live.criterion import WAITING
from btcopilot.tests.live.run import Outcome, Run

HERE = Path(__file__).parent
RUN = pytest.StashKey[Run]()


def pytest_collection_modifyitems(config, items):
    live = [item for item in items if HERE in Path(item.path).parents]
    undeclared = [item.name for item in live if not hasattr(item.function, "criterion")]
    if undeclared:
        raise pytest.UsageError(f"live cases without a pass criterion: {undeclared}")
    for item in live:
        item.add_marker(pytest.mark.live)
        item.add_marker(pytest.mark.e2e)
        if item.get_closest_marker("waiting"):
            item.add_marker(pytest.mark.skip(reason=WAITING))


@pytest.fixture(scope="session", autouse=True)
def run(request):
    """The run's meter: opened with a balance check before any spend, and
    charged for every model call the app writes down."""
    if not request.config.getoption("--e2e"):
        pytest.skip("need --e2e option to run")
    git = subprocess.run(
        ["git", "-C", str(HERE), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    opened = request.config.stash[RUN] = Run(CoachModel().model, git)
    opened.open(require_testing_key())
    charged = opened.recorded
    event.listen(ModelCall, "after_insert", charged)
    yield opened
    event.remove(ModelCall, "after_insert", charged)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    run = item.config.stash.get(RUN, None)
    if run is None:
        return report
    if report.when == "setup":
        run.begin(item.name, str(item.function.criterion))
    if report.when == "call" or not report.passed:
        run.end(item.name, Outcome(report.outcome))
    if run.reason:
        item.session.shouldstop = f"live run stopped: {run.reason}"
    return report


def pytest_sessionfinish(session, exitstatus):
    run = session.config.stash.get(RUN, None)
    if run is not None:
        run.finish(exitstatus)


def pytest_terminal_summary(terminalreporter, config):
    run = config.stash.get(RUN, None)
    if run is not None:
        terminalreporter.write_line(run.summary())


def require_testing_key() -> str:
    key = os.environ.get("ANTHROPIC_TESTING_KEY")
    assert key, (
        "the live venue makes real model calls; set ANTHROPIC_TESTING_KEY "
        "(never ANTHROPIC_API_KEY, which is production's key; there is no fallback)"
    )
    return key


@pytest.fixture(autouse=True)
def testing_key(request, monkeypatch):
    """The live venue's own key, never production's: set ANTHROPIC_API_KEY from
    ANTHROPIC_TESTING_KEY for this test only, and fail loudly if it is unset."""
    if request.config.getoption("--e2e"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", require_testing_key())


@pytest.fixture(autouse=True)
def private_prompts(request):
    if request.config.getoption("--e2e"):
        assert (
            key_present()
        ), "the live venue runs the private prompts; set SOPS_AGE_KEY_FILE"


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    """Naming the session is its own model call, and not what is under test."""
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def token(web):
    return csrf_token(web)


# The speaker's own place in the record is complete, so the coach's first turn
# goes to what is said rather than to intake questions about the speaker.
ME = {
    "id": 1,
    "name": "Wren",
    "last_name": "Hale",
    "gender": "female",
    "primary": True,
    "parents": 10,
}
MOTHER = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female"}
FATHER = {"id": 3, "name": "Hugh", "last_name": "Hale", "gender": "male"}
PARENTS = {"id": 10, "person_a": 2, "person_b": 3, "married": True}
BORN = {
    "id": 30,
    "kind": "birth",
    "person": 2,
    "spouse": 3,
    "child": 1,
    "dateTime": "1985-04-12",
}


class Coach:
    """The signed-in user's record, and one real turn on it."""

    def __init__(self, web, token, user):
        self.web, self.token, self.user = web, token, user

    def record(self, people=(), pair_bonds=(), events=()) -> None:
        """The speaker, their parents and their birth, plus what the test adds,
        in a new session, so a case run again starts from nothing said."""
        response = self.web.post(
            "/app/sessions", json={}, headers={"X-CSRFToken": self.token}
        )
        assert response.status_code == 201, response.get_data(as_text=True)
        people = [ME, MOTHER, FATHER, *people]
        pair_bonds = [PARENTS, *pair_bonds]
        events = [BORN, *events]
        ids = [item["id"] for item in (*people, *pair_bonds, *events)]
        self.user.free_diagram.set_diagram_data(
            DiagramData(
                people=people, pair_bonds=pair_bonds, events=events, lastItemId=max(ids)
            )
        )
        db.session.commit()

    @property
    def events(self) -> list[dict]:
        db.session.expire_all()
        return self.user.free_diagram.get_diagram_data().events

    @property
    def people(self) -> list[dict]:
        db.session.expire_all()
        return self.user.free_diagram.get_diagram_data().people

    def turn(self, statement: str) -> list[dict]:
        """Everything one real turn told the page, in order, ending in its reply."""
        response = self.web.post(
            "/app/chat",
            json={"statement": statement},
            headers={"X-CSRFToken": self.token},
        )
        assert response.status_code == 202, response.get_data(as_text=True)
        replied(response)
        return [e for _, e in turnlog.read_from(response.get_json()["turn_id"], 0)]

    def say(self, statement: str) -> str:
        return self.turn(statement)[-1]["statement"]


@pytest.fixture
def coach(web, token, test_user):
    return Coach(web, token, test_user)
