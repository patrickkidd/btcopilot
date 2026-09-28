import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).parents[2] / "bin" / "deploy-lock"
loader = importlib.machinery.SourceFileLoader("deploylock", str(PATH))
spec = importlib.util.spec_from_loader("deploylock", loader)
deploylock = importlib.util.module_from_spec(spec)
loader.exec_module(deploylock)


def fake(monkeypatch, branches):
    state = {"policies": [{"id": i, "name": b} for i, b in enumerate(branches)], "calls": []}

    def gh(*args, body=None):
        state["calls"].append((args, body))
        if args == (deploylock.POLICIES,):
            return {"branch_policies": list(state["policies"])}
        if args[:2] == ("-X", "POST"):
            state["policies"].append({"id": 99, "name": body["name"]})
        if args[:2] == ("-X", "DELETE"):
            pid = int(args[2].rsplit("/", 1)[1])
            state["policies"] = [p for p in state["policies"] if p["id"] != pid]

    monkeypatch.setattr(deploylock, "gh", gh)
    return state


def test_set_leaves_one_branch(monkeypatch):
    # R-0530
    state = fake(monkeypatch, ["FD-363", "FD-360"])
    deploylock.set_("FD-370")
    assert [p["name"] for p in state["policies"]] == ["FD-370"]


def test_set_same_branch_unchanged(monkeypatch):
    # R-0530
    state = fake(monkeypatch, ["FD-363"])
    deploylock.set_("FD-363")
    assert state["policies"] == [{"id": 0, "name": "FD-363"}]


@pytest.mark.parametrize("branch", ["master", "FD-*", "", "a,b"])
def test_set_refuses(monkeypatch, branch):
    # R-0530
    state = fake(monkeypatch, ["FD-363"])
    with pytest.raises(SystemExit):
        deploylock.set_(branch)
    assert state["calls"] == []
