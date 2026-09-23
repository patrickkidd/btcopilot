"""bin/t maps a changed path to the suites that cover it, and nothing more."""

import importlib.util

import pytest

from btcopilot.tests.repo import REPO

# bin/t lives beside the package in a checkout; the installed copy has no bin
if not (REPO / "bin" / "t").is_file():
    pytest.skip("no checkout: bin/t is not installed", allow_module_level=True)

spec = importlib.util.spec_from_loader(
    "t", importlib.machinery.SourceFileLoader("t", str(REPO / "bin" / "t"))
)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def test_a_review_change_runs_only_review():
    chosen = t.route(["btcopilot/review/routes.py"])
    assert list(chosen) == [t.Suite.Review]


def test_a_screen_change_runs_the_front_end_and_its_walks():
    chosen = t.route(["web/src/meeting.ts"])
    assert set(chosen) == {t.Suite.Web, t.Suite.Walks}


def test_the_shared_fixtures_run_the_whole_python_suite():
    chosen = t.route(["btcopilot/tests/fixtures.py"])
    assert set(chosen) == {t.Suite.Chat}


def test_a_path_no_suite_covers_runs_nothing():
    assert t.route(["doc/chat-first/STATE.md"]) == {}
