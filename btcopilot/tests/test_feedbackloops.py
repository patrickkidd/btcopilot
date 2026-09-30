"""Every kind of row and every dashboard panel that carries a signal is named in
the feedback loops ledger, so a new signal gets its loop the day it is added."""

import json

from bin.grafanapush import DASHBOARDS
from btcopilot.models.notification import NotificationKind
from btcopilot.models.observation import ObservationKind
from btcopilot.models.report import ReportKind
from btcopilot.tests.repo import REPO

LEDGER = (REPO / "doc" / "FEEDBACK_LOOPS.md").read_text()


def titles(panels):
    for panel in panels:
        yield panel["title"]
        yield from titles(panel.get("panels", []))


def test_every_kind_is_in_the_ledger():
    # R-0578, R-0517
    kinds = [k.value for k in [*ObservationKind, *ReportKind, *NotificationKind]]
    assert [k for k in kinds if f"`{k}`" not in LEDGER] == []


def test_every_panel_is_in_the_ledger():
    # R-0578, R-0517
    found = [
        t
        for path in sorted(DASHBOARDS.glob("*.json"))
        for t in titles(json.loads(path.read_text())["panels"])
    ]
    assert [t for t in found if f'"{t}"' not in LEDGER] == []
