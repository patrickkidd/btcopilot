"""Every release puts the repository's dashboards to Grafana (bin/grafanapush.py)."""

import io
import json
import urllib.error

import pytest
import yaml

import bin.grafanapush as grafanapush
from btcopilot.tests.repo import REPO


def test_each_dashboard_is_put_over_what_grafana_holds(monkeypatch):
    # R-0517
    sent = []

    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"uid": "fd-quality", "version": 3}).encode())

    monkeypatch.setattr(grafanapush, "urlopen", urlopen)
    monkeypatch.setenv("GRAFANA_URL", "https://stack.grafana.net")
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "token")
    grafanapush.main()
    assert [s["dashboard"]["uid"] for s in sent] == [
        json.loads(p.read_text())["uid"] for p in sorted(grafanapush.DASHBOARDS.glob("*.json"))
    ]
    assert all(s["overwrite"] for s in sent)


def test_a_refused_dashboard_stops_the_release_step(monkeypatch):
    # R-0517
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(grafanapush, "urlopen", urlopen)
    monkeypatch.setenv("GRAFANA_URL", "https://stack.grafana.net")
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "token")
    with pytest.raises(urllib.error.HTTPError):
        grafanapush.main()


def test_a_sleeping_stack_is_waited_for(monkeypatch):
    # R-0517
    calls, sleeps = [], []

    def urlopen(request, timeout):
        calls.append(timeout)
        if len(calls) < 3:
            raise urllib.error.HTTPError(request.full_url, 503, "Loading", {"Retry-After": "7"}, None)
        return io.BytesIO(json.dumps({"uid": "fd-quality", "version": 3}).encode())

    monkeypatch.setattr(grafanapush, "urlopen", urlopen)
    monkeypatch.setattr(grafanapush.time, "sleep", sleeps.append)
    path = next(grafanapush.DASHBOARDS.glob("*.json"))
    assert grafanapush.push("https://stack.grafana.net", "token", path)["uid"] == "fd-quality"
    assert (calls, sleeps) == ([30, 30, 30], [7, 7])


def test_a_server_error_is_not_retried(monkeypatch):
    # R-0517
    calls = []

    def urlopen(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 500, "Internal Server Error", {}, None)

    monkeypatch.setattr(grafanapush, "urlopen", urlopen)
    monkeypatch.setattr(grafanapush.time, "sleep", pytest.fail)
    with pytest.raises(urllib.error.HTTPError):
        grafanapush.push("https://stack.grafana.net", "token", next(grafanapush.DASHBOARDS.glob("*.json")))
    assert len(calls) == 1


def test_the_release_pushes_the_dashboards_after_the_deploy():
    # R-0517
    steps = yaml.safe_load((REPO / ".github" / "workflows" / "release.yml").read_text())["jobs"]["deploy"]["steps"]
    names = [step.get("name") for step in steps]
    push = steps[names.index("Push the dashboards")]
    assert names.index("Pull the image and run the chain") < names.index("Push the dashboards")
    assert push["run"] == "python bin/grafanapush.py"
    assert push["env"]["GRAFANA_SA_TOKEN"] == "${{ secrets.GRAFANA_SA_TOKEN }}"


def test_the_features_dashboard_carries_a_panel_for_each_loop():
    # R-0077, R-0517
    dashboard = json.loads((grafanapush.DASHBOARDS / "fd-features.json").read_text())
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert (dashboard["uid"], "id" in dashboard) == ("fd-features", False)
    assert {
        "Feature use a day",
        "Messages the coach wrote first, by the week they were sent",
        "Bug reports and feedback the coach offered to send, per week",
        "Notices: how many people each was sent to, and how many opened it",
        "Coach edits to things an earlier sitting put down, per week",
        "Coverage curve, across all sittings",
        "Coverage curve, each sitting",
        "Coach turns to 50% coverage, by family",
    } <= titles


def test_the_cost_dashboard_carries_the_turn_cost_panels():
    # R-0595, R-0517
    dashboard = json.loads((grafanapush.DASHBOARDS / "fd-cost.json").read_text())
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert (dashboard["uid"], "id" in dashboard) == ("fd-cost", False)
    assert {
        "Cost per turn now",
        "Cost per turn, last 7 days",
        "Average cost per turn",
        "Cost per coach turn a day, warm and cold, with the 14-day mean",
        "Dollars by kind, coach calls",
        "Calls per coach turn a day",
        "Tokens written on a cold turn's first call, a day",
        "Share of coach turns that start cold, a day",
        "Coverage of the basic data over time, by family",
        "Cost per coach turn by release",
        "Replay passes",
    } <= titles
