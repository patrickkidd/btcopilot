"""bin/t maps a changed path to the suites that cover it, and nothing more."""

import importlib.util

from btcopilot.tests.repo import REPO

spec = importlib.util.spec_from_loader(
    "t", importlib.machinery.SourceFileLoader("t", str(REPO / "bin" / "t"))
)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def test_a_review_change_runs_only_review():
    chosen = t.route(["btcopilot/review/routes.py"])
    assert list(chosen) == [t.Suite.Review]


def test_a_pro_change_runs_nothing_of_the_chats():
    chosen = t.route(["btcopilot/pro/models/license.py"])
    assert list(chosen) == [t.Suite.Pro]


def test_a_screen_change_runs_the_front_end_and_its_walks():
    chosen = t.route(["web/src/meeting.ts"])
    assert set(chosen) == {t.Suite.Web, t.Suite.Walks}


def test_the_shared_fixtures_run_every_python_suite():
    chosen = t.route(["btcopilot/tests/fixtures.py"])
    assert set(chosen) == {t.Suite.Chat, t.Suite.Pro, t.Suite.Training}


def test_a_path_no_suite_covers_runs_nothing():
    assert t.route(["doc/chat-first/STATE.md"]) == {}
