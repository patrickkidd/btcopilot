"""The cost dashboards add up to the model-calls ledger: one panel sums every
row, and a panel that prices tokens itself carries the app's own price list,
so no model's rows drop out of it unseen."""

import json
import re
from decimal import Decimal

import pytest
import yaml

from btcopilot import flow, topics
from btcopilot.pricing import PRICES
from btcopilot.tests import grafanasql
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
        model: (p.input, p.output, p.cache_write, p.cache_read)
        for model, p in PRICES.items()
    }


def test_one_panel_sums_every_row_of_the_ledger():
    # R-0628, R-0389
    (total,) = [p for b, p in panels() if p["title"] == "All model spend"]
    (by_purpose,) = [
        p for b, p in panels() if p["title"] == "All model spend, by purpose"
    ]
    for panel in (total, by_purpose):
        words = sql(panel)
        assert "sum(mc.cost_usd)" in words
        assert "scratch" not in words.split("where", 1)[1]
        assert "purpose <>" not in words and "not like 'claude-test" not in words
    assert "claude-test account" in sql(by_purpose)


def test_no_cost_panel_charges_a_replay_to_a_person():
    # R-0389
    (panel,) = [
        p for b, p in panels() if p["title"] == "Cost per person per feature share"
    ]
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


# The first wave of boards about users and the coach [R-0814]: each carries its
# panels, says its rule, reads one Postgres source, leaves out the test account
# and scratch records, and keeps its copies of the topic map and the objection
# phrases equal to the app's own.

FIRST_WAVE = {
    "fd-people": (
        "Topics placed in the record, share of sittings by week",
        "Topics placed in the record: sittings and writes per topic",
        "Top topics per record",
        "Which relatives come up: share of messages naming each",
        "Most-named people per record",
        "Pushback per 100 messages, by week: words (tentative) and taps",
        "Pushback: the counts behind the rate",
        "Pushback: the objection phrases found",
        "Fact questions by item: what the coach recorded and what people tapped",
        "Fact questions by generation and side",
        "What people correct, per 100 coach writes, by field",
        "Picture opened in a sitting, and taps followed by talk",
        "Picture taps by name and by item kind",
        "Share of people who used the picture, by week",
        "How far each record got, at the last sitting",
        "Coverage at the last sitting: active and silent people",
    ),
    "fd-coach": (
        "Share of coach turns that wrote to the record, by week and prompt version",
        "Coach turns that wrote, by turn index and prompt version",
        "Record tools per 100 coach turns, by tool",
        "Beside the write share: duplicates and hand corrections per 100 coach writes",
        "Faults per 100 coach turns, by kind",
        "Faults ranked by the share of people who sent nothing more",
        "Faults per 100 coach turns, by prompt version",
        "Fact questions the coach asked, by item",
        "Fact questions the coach asked, by generation and side",
        "Fact questions per 100 coach turns, by prompt version",
        "Guesses voiced per 100 coach turns, by week",
        "How the coach's guesses fared",
        "Guesses by prompt version",
        "Reply length and shape by turn index and prompt version",
        "Words per coach reply, weekly median and 90th percentile",
    ),
    "fd-return": (
        "Return within a week",
        "From invitation to second sitting",
        "Second sitting within 7 days, by what the first sitting did",
        "How sittings end",
        "The last thing before silence",
        "Active, silent, left",
        "People active each week: first week and returning",
        "Days between sittings",
        "Days between sittings by cohort month",
    ),
}
SOURCE = {"type": "grafana-postgresql-datasource", "uid": "ffz1wy7unkdfke"}
# up to the "))" that closes the last row and the list
TOPIC_MAP = re.compile(
    r"topic_map\s*\(hook,\s*topic\)\s*as\s*\(\s*values\s*(.*?\))\s*\)", re.S | re.I
)
PAIR = re.compile(r"\('([^']+)',\s*'([^']+)'\)")
OBJECTION = re.compile(
    r"objection\s*\(phrase\)\s*as\s*\(\s*values\s*(.*?\))\s*\)", re.S | re.I
)
PHRASE = re.compile(r"\('((?:[^']|'')+)'\)")


def built() -> list[tuple[str, dict]]:
    return [
        (name, json.loads((GRAFANA / f"{name}.json").read_text()))
        for name in FIRST_WAVE
        if (GRAFANA / f"{name}.json").exists()
    ]


def wave() -> list[tuple[str, dict]]:
    return [
        (name, p) for name, b in built() for p in b["panels"] if p.get("type") != "row"
    ]


def label(x):
    return x if isinstance(x, str) else x.get("title", "")


def phrases(found: re.Match) -> tuple[str, ...]:
    return tuple(p.replace("''", "'") for p in PHRASE.findall(found.group(1)))


@pytest.mark.parametrize("name, board", built(), ids=label)
def test_a_first_wave_board_carries_its_panels_and_no_id(name, board):
    # R-0814
    assert board["uid"] == name and "id" not in board
    titles = [p["title"] for p in board["panels"] if p.get("type") != "row"]
    assert sorted(titles) == sorted(FIRST_WAVE[name])
    ids = [p["id"] for p in board["panels"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name, panel", wave(), ids=label)
def test_a_first_wave_panel_reads_one_source_and_says_its_rule(name, panel):
    # R-0814
    assert panel["datasource"] == SOURCE
    assert all(t["datasource"] == SOURCE for t in panel["targets"])
    assert panel.get("description", "").strip()


@pytest.mark.parametrize("name, panel", wave(), ids=label)
def test_a_first_wave_query_leaves_out_the_test_account_and_scratch(name, panel):
    # R-0814, R-0517
    words = sql(panel)
    assert "claude-test" in words and "scratch" in words


@pytest.mark.parametrize(
    "name, panel", [x for x in wave() if "topic_map" in sql(x[1])], ids=label
)
def test_a_topic_panel_carries_the_app_topic_map(name, panel):
    # R-0814
    found = list(TOPIC_MAP.finditer(sql(panel)))
    assert found
    for each in found:
        assert PAIR.findall(each.group(1)) == list(topics.TOPICS)


@pytest.mark.parametrize(
    "name, panel", [x for x in wave() if "objection(" in sql(x[1])], ids=label
)
def test_a_pushback_panel_carries_the_app_objection_phrases(name, panel):
    # R-0814, R-0517
    found = list(OBJECTION.finditer(sql(panel)))
    assert found
    for each in found:
        assert phrases(each) == flow.OBJECTION


@pytest.mark.parametrize(
    "name, panel", [x for x in wave() if grafanasql.by_version(sql(x[1]))], ids=label
)
def test_a_panel_by_prompt_version_holds_back_a_version_under_30_people(name, panel):
    # R-0814
    assert re.search(r">=\s*30\b", sql(panel))


def test_a_bracket_inside_a_quoted_literal_does_not_hide_the_final_select():
    # R-0814
    words = (
        "with t as (select prompt_version, text from statements"
        " where text ~ '[.?!)]' and text <> 'it''s )' group by prompt_version, text)"
        " select count(*) from t group by text"
    )
    assert grafanasql.final(words).startswith("select count(*)")
    assert not grafanasql.by_version(words)


def test_the_shared_tables_carry_the_app_objection_phrases():
    # R-0814, R-0517
    assert phrases(OBJECTION.search(grafanasql.FRAGMENTS)) == flow.OBJECTION


def test_the_first_wave_has_forty_panels():
    # R-0814
    assert sum(map(len, FIRST_WAVE.values())) == 40
