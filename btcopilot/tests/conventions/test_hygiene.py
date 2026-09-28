"""Hygiene guards of the rulings store: what keeps it true as it grows without
limit (private/oracle README, Hygiene). Each prints the offending ids."""

import itertools
import re
from datetime import date, timedelta

import pytest

from btcopilot import oracle
from btcopilot.oracle import Status, Tag

pytestmark = pytest.mark.conventions

NEAR = 0.5
WIDTH = 160
STALE = timedelta(days=90)
WORD = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    "a an the and or of to in on is it its be by for with as at from that this which who what "
    "when where not no never every each his her their he she they them one all any than then "
    "there are was were has have had do does into out up so if but only also same own more most "
    "just can may must should would will".split()
)
RETIRES = re.compile(r"\b(?:[Ss]upersed(?:es|ing)|[Ss]ucceeds|[Rr]eplaces|[Rr]etires)\s+(R-\d{4})\b(?!['’]s)")
STAMP = re.compile(r"^Last consolidation: (\d{4}-\d{2}-\d{2})", re.M)


def words(text: str) -> frozenset[str]:
    found = (w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1)
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in found)


def test_every_tag_has_one_topic():
    # R-0447, R-0042
    assert sorted(t.value for t in Tag if t not in oracle.TOPIC) == []
    assert sum(len(tags) for tags in oracle.GROUPS.values()) == len(oracle.TOPIC), "a tag sits in two topics"


def test_no_two_active_statements_are_near_copies():
    # R-0447, R-0042
    live = {r.id: words(r.statement) for r in oracle.rulings().values() if r.status is Status.Ok}
    near = [
        f"{a} {b} {len(live[a] & live[b]) / len(live[a] | live[b]):.2f}"
        for a, b in itertools.combinations(live, 2)
        if len(live[a] & live[b]) >= NEAR * len(live[a] | live[b])
    ]
    assert near == [], f"statement word overlap at or over {NEAR}: merge one into the other (DUPLICATE) or reword"


def test_a_ruling_named_as_replaced_is_marked_superseded():
    # R-0447, R-0042
    found = oracle.rulings()
    live = sorted(
        f"{m.group(1)} by {r.id}"
        for r in found.values()
        for m in RETIRES.finditer(r.statement)
        if found[m.group(1)].status is Status.Ok
    )
    assert live == [], "mark each SUPERSEDED, naming the ruling that replaced it"


def test_no_index_line_is_over_its_cap():
    # R-0447, R-0042
    long = [l.split(" | ")[0] for l in oracle.index().splitlines() if len(l.encode()) > WIDTH]
    assert long == [], f"index lines over {WIDTH} bytes"


def test_the_store_was_consolidated_within_90_days():
    # R-0447, R-0042
    m = STAMP.search(oracle.decrypt(oracle.README))
    assert m, "the store README has no 'Last consolidation: YYYY-MM-DD' line"
    age = date.today() - date.fromisoformat(m.group(1))
    assert age <= STALE, f"last consolidation {m.group(1)}, {age.days} days ago: audit the store, apply Patrick's answers, move the stamp"
