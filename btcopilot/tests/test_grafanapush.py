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

    def urlopen(request):
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
    def urlopen(request):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(grafanapush, "urlopen", urlopen)
    monkeypatch.setenv("GRAFANA_URL", "https://stack.grafana.net")
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "token")
    with pytest.raises(urllib.error.HTTPError):
        grafanapush.main()


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
