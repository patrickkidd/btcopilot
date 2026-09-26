"""The live venue's spend and results, on stand-ins: no call reaches the API."""

import json
from decimal import Decimal

import anthropic
import httpx
import pytest

from btcopilot.coachmodel import Spent
from btcopilot.tests.live import passrate
from btcopilot.tests.live import test_coachturn as coachturn
from btcopilot.tests.live.criterion import Criterion, passes
from btcopilot.tests.live.run import RUN_CAP, Outcome, Run

MODEL = "claude-opus-5-5"
GIT = "0123456789abcdef"


class Refused:
    """The API turning the balance check away, as it does on an empty balance."""

    def __init__(self, api_key):
        self.messages = self

    def create(self, **kwargs):
        raise anthropic.BadRequestError(
            "Your credit balance is too low to access the Anthropic API.",
            response=httpx.Response(
                400,
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
            ),
            body=None,
        )


class Turns:
    """A coach that counts its turns and leaves the record and reply it is given."""

    def __init__(self, people, reply):
        self.people = people
        self.reply = reply
        self.turns = 0

    def record(self, *args, **kwargs):
        pass

    def say(self, statement):
        self.turns += 1
        return self.reply


def test_a_run_over_its_cap_stops_and_is_recorded_stopped(tmp_path, monkeypatch):
    # R-0507
    run = Run(MODEL, GIT, tmp_path)
    run.begin("a case", "once")
    run.charge(Spent(input=1000), RUN_CAP + Decimal("0.01"))
    run.end("a case", Outcome.Passed)
    assert "run cap" in run.reason
    assert run.finish(pytest.ExitCode.OK)["status"] == "stopped"
    monkeypatch.setattr(
        anthropic, "Anthropic", lambda **kwargs: pytest.fail("the API was called")
    )
    with pytest.raises(pytest.exit.Exception, match="today's cap"):
        Run(MODEL, GIT, tmp_path).open("key")


def test_a_run_writes_one_results_row(tmp_path):
    # R-0507
    run = Run(MODEL, GIT, tmp_path)
    run.begin("passes", "once")
    run.charge(Spent(input=100, output=10, cache_read=50), Decimal("0.25"))
    run.end("passes", Outcome.Passed)
    run.begin("misses", "2 of 3")
    run.charge(Spent(input=200, output=20), Decimal("0.50"))
    run.end("misses", Outcome.Failed)
    run.finish(pytest.ExitCode.TESTS_FAILED)
    (path,) = tmp_path.glob("????-??-??T*.json")
    row = json.loads(path.read_text())
    assert {k: row[k] for k in ("model", "git", "status", "reason", "cost")} == {
        "model": MODEL,
        "git": GIT,
        "status": "failed",
        "reason": None,
        "cost": 0.75,
    }
    assert row["tokens"] == {
        "input": 300,
        "output": 30,
        "cache_creation": 0,
        "cache_read": 50,
    }
    assert row["cases"] == [
        {
            "case": "passes",
            "criterion": "once",
            "outcome": "passed",
            "tokens": {
                "input": 100,
                "output": 10,
                "cache_creation": 0,
                "cache_read": 50,
            },
            "cost": 0.25,
        },
        {
            "case": "misses",
            "criterion": "2 of 3",
            "outcome": "failed",
            "tokens": {
                "input": 200,
                "output": 20,
                "cache_creation": 0,
                "cache_read": 0,
            },
            "cost": 0.5,
        },
    ]
    assert json.loads((tmp_path / "daily.json").read_text()) == {run.day: "0.75"}
    seen = passrate.rates(tmp_path)[MODEL]
    assert dict(seen["cases"]) == {"passes": [1, 1], "misses": [0, 1]}


def test_a_merged_case_runs_one_turn_for_both_assertions():
    # R-0441
    tom = [{"id": 14, "name": "Tom"}]
    coach = Turns(tom, "And Tom, where is he now?")
    coachturn.test_a_complete_list_removes_no_one_and_the_coach_asks_about_the_one_left_out(
        coach
    )
    assert coach.turns == 1
    with pytest.raises(AssertionError):
        coachturn.test_a_complete_list_removes_no_one_and_the_coach_asks_about_the_one_left_out(
            Turns(tom, "Who else is in the family?")
        )


def test_k_of_n_passes_at_k_and_fails_below_it():
    runs = iter([False, True, True, True, False, False])

    @passes(2, of=3)
    def case():
        assert next(runs)

    case()
    with pytest.raises(AssertionError, match="1 of 3 runs passed, 2 needed"):
        case()
    assert case.criterion == Criterion(2, 3)


def test_a_refused_balance_check_stops_the_run(tmp_path, monkeypatch):
    # R-0507
    monkeypatch.setattr(anthropic, "Anthropic", Refused)
    run = Run(MODEL, GIT, tmp_path)
    with pytest.raises(
        pytest.exit.Exception, match="balance check was refused.*credit balance"
    ):
        run.open("key")
    assert run.finish(pytest.ExitCode.INTERRUPTED)["status"] == "stopped"
