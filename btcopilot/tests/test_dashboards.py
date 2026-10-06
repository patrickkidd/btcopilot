"""The cost dashboards add up to the model-calls ledger: one panel sums every
row, and a panel that prices tokens itself carries the app's own price list,
so no model's rows drop out of it unseen."""

import json
import re
from decimal import Decimal

import pytest
import yaml

from btcopilot.pricing import PRICES
from btcopilot.tests.repo import REPO

GRAFANA = REPO / "deploy" / "grafana"
LISTED = re.compile(r"\(values (.*?)\) v\(p,i,o,w,c\)")
ROW = re.compile(r"\('([^']+)',([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)")


def panels() -> list[tuple[str, dict]]:
    return [
        (path.stem, panel)
        for path in sorted(GRAFANA.glob("*.json"))
        for panel in json.loads(path.read_text())["panels"]
    ]


def sql(panel: dict) -> str:
    return " ".join(t.get("rawSql", "") for t in panel.get("targets", []))


@pytest.mark.parametrize(
    "board, panel",
    [(b, p) for b, p in panels() if LISTED.search(sql(p))],
    ids=lambda x: x if isinstance(x, str) else x["title"],
)
def test_a_panel_that_prices_tokens_lists_every_priced_model_at_its_price(board, panel):
    # R-0628, R-0389
    listed = {
        model: tuple(Decimal(n) for n in rates)
        for model, *rates in ROW.findall(LISTED.search(sql(panel)).group(1))
    }
    assert listed == {
        model: (p.input, p.output, p.cache_write, p.cache_read) for model, p in PRICES.items()
    }


def test_one_panel_sums_every_row_of_the_ledger():
    # R-0628, R-0389
    (total,) = [p for b, p in panels() if p["title"] == "All model spend"]
    (by_purpose,) = [p for b, p in panels() if p["title"] == "All model spend, by purpose"]
    for panel in (total, by_purpose):
        words = sql(panel)
        assert "sum(mc.cost_usd)" in words
        assert "scratch" not in words.split("where", 1)[1]
        assert "purpose <>" not in words and "not like 'claude-test" not in words
    assert "claude-test account" in sql(by_purpose)


def test_no_cost_panel_charges_a_replay_to_a_person():
    # R-0389
    (panel,) = [p for b, p in panels() if p["title"] == "Cost per person per feature share"]
    assert "dg.scratch" in sql(panel)


SOURCES = REPO / "deploy" / "laptop" / "grafana" / "datasources.yml"
SERVICE = re.compile(r'"container_name", "([^"]+)"|"(\^[^"]+)" from CONTAINER_NAME')


def uids(node) -> set[str]:
    if isinstance(node, dict):
        source = node.get("datasource")
        found = {source["uid"]} if isinstance(source, dict) else set()
        return found.union(*(uids(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(uids(v) for v in node))
    return set()


def test_every_dashboard_reads_a_data_source_the_laptop_provides():
    # R-0370
    provided = {s["uid"] for s in yaml.safe_load(SOURCES.read_text())["datasources"]}
    used = set().union(*(uids(json.loads(p.read_text())) for p in GRAFANA.glob("*.json")))
    assert used <= provided


def test_box_container_panels_name_each_compose_service_across_deploys():
    # R-0370
    board = json.loads((GRAFANA / "fd-box.json").read_text())
    patterns = [
        next(g for g in m.groups() if g)
        for p in board["panels"]
        for m in [SERVICE.search(p["targets"][0]["expr"])]
        if m
    ]
    assert len(patterns) == 3
    for pattern in patterns:
        names = [
            "familydiagram-fd-app-60",
            "chat-fd-worker-15",
            "fd-postgres",
            "fd-redis",
        ]
        seen = [re.fullmatch(pattern, n).group(1) for n in names]
        assert seen == ["fd-app", "fd-worker", "fd-postgres", "fd-redis"]
