import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

import pytest

PATH = Path(__file__).parents[2] / "bin" / "subscribe.py"
loader = importlib.machinery.SourceFileLoader("subscribe", str(PATH))
spec = importlib.util.spec_from_loader("subscribe", loader)
subscribe = importlib.util.module_from_spec(spec)
loader.exec_module(subscribe)


def chained(monkeypatch, asked):
    """A run that asks, round after round, for the calls `asked` names: each
    list is what one round dumps, and an answered call is not asked again
    unless `asked` says so."""
    rounds = iter(asked)
    answers = []

    def dumped(args, requests):
        for name in next(rounds, []):
            requests.mkdir(parents=True, exist_ok=True)
            (requests / name).write_text("{}")
        return subprocess.CompletedProcess(args, 0, stdout="1 passed", stderr="")

    def answered(request, work):
        answers.append(request.name)
        return request.name

    monkeypatch.setattr(subscribe, "dumped", dumped)
    monkeypatch.setattr(subscribe, "answered", answered)
    return answers


def test_a_case_longer_than_twelve_calls_is_answered_in_one_run(monkeypatch):
    # R-0568
    chain = [[f"call{i}-0.json"] for i in range(30)]
    answers = chained(monkeypatch, chain)
    assert subscribe.main([]) == 0
    assert answers == [c[0] for c in chain]


def test_a_call_asked_again_after_its_answer_stops_the_run_naming_it(monkeypatch):
    # R-0568
    chained(monkeypatch, [["a-0.json", "b-0.json"], ["b-0.json"]])
    with pytest.raises(SystemExit, match="answered but not replayed: \\['b-0.json'\\]"):
        subscribe.main([])


def test_a_run_past_the_round_cap_names_the_calls_still_coming(monkeypatch):
    # R-0568
    monkeypatch.setattr(subscribe, "ROUNDS", 3)
    chained(monkeypatch, [[f"call{i}-0.json"] for i in range(5)])
    with pytest.raises(
        SystemExit, match="after 3 rounds; the last answered: \\['call2-0.json'\\]"
    ):
        subscribe.main([])
