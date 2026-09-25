"""The live venue: one real coach turn on the private prompts, and the record it
leaves behind. It costs money and needs the prompts' key, so it never runs on CI
(R-0451). It always spends on ANTHROPIC_TESTING_KEY, never ANTHROPIC_API_KEY
(production's key); there is no fallback to the production key. Run it by hand:

    SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt uv run pytest \
        btcopilot/btcopilot/tests/live --e2e

Without --e2e every test here is skipped; with it and no key (either key), every
test fails.
"""

import os
from pathlib import Path

import pytest

from btcopilot.extensions import db
from btcopilot.promptdir import key_present
from btcopilot.schema import DiagramData
from btcopilot.tests.conftest import csrf_token, replied

HERE = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    for item in items:
        if HERE in Path(item.path).parents:
            item.add_marker(pytest.mark.live)
            item.add_marker(pytest.mark.e2e)


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
        assert key_present(), "the live venue runs the private prompts; set SOPS_AGE_KEY_FILE"


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
ME = {"id": 1, "name": "Wren", "last_name": "Hale", "gender": "female", "primary": True, "parents": 10}
MOTHER = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female"}
FATHER = {"id": 3, "name": "Hugh", "last_name": "Hale", "gender": "male"}
PARENTS = {"id": 10, "person_a": 2, "person_b": 3, "married": True}
BORN = {"id": 30, "kind": "birth", "person": 2, "spouse": 3, "child": 1, "dateTime": "1985-04-12"}


class Coach:
    """The signed-in user's record, and one real turn on it."""

    def __init__(self, web, token, user):
        self.web, self.token, self.user = web, token, user

    def record(self, people=(), pair_bonds=(), events=()) -> None:
        """The speaker, their parents and their birth, plus what the test adds."""
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

    def say(self, statement: str) -> str:
        response = self.web.post(
            "/app/chat",
            json={"statement": statement},
            headers={"X-CSRFToken": self.token},
        )
        assert response.status_code == 202, response.get_data(as_text=True)
        return replied(response)["statement"]


@pytest.fixture
def coach(web, token, test_user):
    return Coach(web, token, test_user)
