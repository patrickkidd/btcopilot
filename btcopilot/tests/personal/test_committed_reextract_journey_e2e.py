"""E2E journey: extract -> accept-all, three sessions in a row.

The FD-319 acceptance criterion: a user returning across multiple discussion
sessions sees only additive growth — no committed person/relationship is
duplicated, and accepting a later session's items never alters or removes what
was committed earlier.

Real Gemini, production commit path (repair on), repeated commit cycles.
Requires GOOGLE_GEMINI_API_KEY.
"""

import asyncio

import pytest

from btcopilot.schema import DiagramData, get_all_pdp_item_ids
from btcopilot.pdp import import_text


SESSIONS = [
    # session text, expected cumulative committed person names after commit
    (
        "My name is David Hill. My wife is Lisa Hill. We got married in 2010.",
        {"david", "lisa"},
    ),
    (
        "David and Lisa Hill have a son, Sam, born in 2015. David and Lisa are "
        "still happily married.",
        {"david", "lisa", "sam"},
    ),
    (
        "David Hill's father is Robert Hill. David also mentioned his wife Lisa "
        "and their son Sam again.",
        {"david", "lisa", "sam", "robert"},
    ),
]


def _ident(p):
    """Identity for this controlled test: first-name token, lowercased."""
    name = (p.get("name") or "").strip().lower()
    return name.split()[0] if name else ""


def _name_counts(dd):
    counts = {}
    for p in dd.people:
        key = _ident(p)
        counts[key] = counts.get(key, 0) + 1
    return counts


@pytest.mark.e2e
def test_three_session_accept_journey_is_additive():
    dd = DiagramData()
    prior_ids = {}  # name -> committed id captured the cycle it first appears

    for cycle, (text, expected_names) in enumerate(SESSIONS, start=1):
        pdp, _ = asyncio.run(import_text(dd, text))
        dd.pdp = pdp

        staged = sorted(i for i in get_all_pdp_item_ids(dd.pdp) if i < 0)
        dd.commit_pdp_items(staged)

        counts = _name_counts(dd)

        # AC: no committed person is duplicated
        dupes = {n: c for n, c in counts.items() if n and c > 1}
        assert not dupes, f"cycle {cycle}: duplicated committed people {dupes}"

        # AC: only genuinely new entities — committed names stay within the
        # expected cumulative set (no spurious or re-created people)
        committed_names = {n for n in counts if n}
        unexpected = committed_names - expected_names
        assert not unexpected, (
            f"cycle {cycle}: unexpected committed people {unexpected}; "
            f"expected subset of {expected_names}"
        )

        # AC: accepting this session's items did not alter or remove anything
        # committed in an earlier session — same id, same name, still present
        by_id = {p["id"]: _ident(p) for p in dd.people}
        for name, pid in prior_ids.items():
            assert pid in by_id, (
                f"cycle {cycle}: previously committed '{name}' (id {pid}) "
                f"disappeared after accepting later items"
            )
            assert by_id[pid] == name, (
                f"cycle {cycle}: committed id {pid} changed identity "
                f"'{name}' -> '{by_id[pid]}'"
            )

        # Capture ids for names first committed this cycle
        seen = set(prior_ids.values())
        for p in dd.people:
            n = _ident(p)
            if n and n not in prior_ids and p["id"] not in seen:
                prior_ids[n] = p["id"]
