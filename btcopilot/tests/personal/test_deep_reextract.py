"""
Unit tests for deep_reextract merge/reconcile core.
extract_full is mocked to return canned PDPs across K runs.

Family: 3 runs each missing a different bridge bond.
  Committed: User (id=1), Alice (id=10), Bob (id=11), Carol (id=12)
             Bond: Alice--Bob (id=100)
  Run 1: adds Dave (neg id) + Dave--Carol bond — links Carol to Alice/Bob cluster
  Run 2: adds Eve (neg id) + Eve--Carol bond — different bridge person
  Run 3: adds Dave again (same name) + Dave--Bob bond — duplicate Dave, same bond
"""

import copy
import logging
from unittest.mock import patch

import pytest
from google.genai.errors import ServerError

from btcopilot.llmutil import OutputTruncatedError
from btcopilot.schema import DiagramData, PDP, PDPDeltas, Person, PairBond, PersonKind


def _dd(people: list[dict], pair_bonds: list[dict]) -> DiagramData:
    dd = DiagramData()
    dd.people = copy.deepcopy(people)
    dd.pair_bonds = copy.deepcopy(pair_bonds)
    dd.lastItemId = max((p["id"] for p in people if p.get("id") is not None), default=0)
    return dd


COMMITTED_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
]
COMMITTED_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
]

# Run 1: Dave links Carol to the Alice-Bob cluster via Dave--Carol bond
RUN1_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 201, "name": "Dave", "gender": "male", "parents": None},
]
RUN1_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 201, "person_a": 201, "person_b": 12},
]

# Run 2: Eve provides a different bridge Carol → Alice/Bob cluster
RUN2_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 301, "name": "Eve", "gender": "female", "parents": None},
]
RUN2_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 301, "person_a": 301, "person_b": 12},
]

# Run 3: Dave again (same name) — should match Dave from run1 and not create a dupe
RUN3_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": None},
    {"id": 401, "name": "Dave", "gender": "male", "parents": None},
]
RUN3_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 401, "person_a": 401, "person_b": 11},
]


def test_merge_adds_new_people_from_runs():
    """New people from runs end up in the delta with negative IDs."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    names = {p.name for p in delta_pdp.people if p.id is not None and p.id < 0}
    # Dave and Eve are both new
    assert "Dave" in names
    assert "Eve" in names


def test_merge_deduplicates_same_person_across_runs():
    """Dave appearing in run1 and run3 should produce only one Dave in the delta."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN3_PEOPLE, RUN3_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    dave_entries = [
        p
        for p in delta_pdp.people
        if p.name == "Dave" and p.id is not None and p.id < 0
    ]
    assert len(dave_entries) == 1


def test_merge_bond_endpoints_resolve_to_valid_ids():
    """All delta bond endpoints must reference a person that exists (committed or new)."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [
        _dd(RUN1_PEOPLE, RUN1_BONDS),
        _dd(RUN2_PEOPLE, RUN2_BONDS),
        _dd(RUN3_PEOPLE, RUN3_BONDS),
    ]
    delta_pdp, _ = merge_runs(runs, committed)

    all_person_ids = {p["id"] for p in COMMITTED_PEOPLE if p.get("id") is not None} | {
        p.id for p in delta_pdp.people if p.id is not None
    }
    for pb in delta_pdp.pair_bonds:
        assert (
            pb.person_a in all_person_ids
        ), f"bond {pb.id} person_a={pb.person_a} not found"
        assert (
            pb.person_b in all_person_ids
        ), f"bond {pb.id} person_b={pb.person_b} not found"


def test_merge_preserves_unmarried_flag():
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    bonds = copy.deepcopy(RUN1_BONDS)
    bonds[1]["married"] = False
    delta_pdp, _ = merge_runs([_dd(RUN1_PEOPLE, bonds)], committed)

    dave = next(p for p in delta_pdp.people if p.name == "Dave")
    bond = next(
        pb for pb in delta_pdp.pair_bonds if dave.id in (pb.person_a, pb.person_b)
    )
    assert bond.married is False


def test_merge_produces_only_negative_id_new_entities():
    """Delta must not contain positive-ID new people or bonds (only positive-ID edits)."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    committed_person_ids = {p["id"] for p in COMMITTED_PEOPLE}
    for p in delta_pdp.people:
        if p.id is not None and p.id > 0:
            # Positive-ID people in delta are parent edits — must be committed
            assert (
                p.id in committed_person_ids
            ), f"positive-ID person {p.id} not in committed"
    for pb in delta_pdp.pair_bonds:
        assert pb.id is not None and pb.id < 0, f"bond {pb.id} in delta is not negative"


def test_delta_commits_cleanly_onto_committed_diagram():
    """Committing the delta PDP onto a copy of the committed diagram must not raise."""
    from btcopilot.personal.deepreextract import merge_runs
    from btcopilot.schema import get_all_pdp_item_ids

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [_dd(RUN1_PEOPLE, RUN1_BONDS), _dd(RUN2_PEOPLE, RUN2_BONDS)]
    delta_pdp, _ = merge_runs(runs, committed)

    # Apply delta onto a fresh copy of committed
    target = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    target.pdp = delta_pdp

    neg_ids = [p.id for p in delta_pdp.people if p.id is not None and p.id < 0]
    neg_ids += [pb.id for pb in delta_pdp.pair_bonds if pb.id is not None and pb.id < 0]
    if neg_ids:
        id_mapping = target.commit_pdp_items(neg_ids)
        assert len(id_mapping) == len(neg_ids)

    # After commit, all previously negative ids are now positive
    all_ids = {p["id"] for p in target.people} | {pb["id"] for pb in target.pair_bonds}
    for old_neg in neg_ids:
        assert old_neg not in all_ids  # original neg id gone
        assert id_mapping[old_neg] in all_ids  # new positive id present


def test_accumulate_discussions_applies_parent_edits(discussions):
    """FD-338 bug B: a positive-id parents edit staged by a later discussion's
    extraction is applied to a person committed from an earlier discussion."""
    from btcopilot.personal.deepreextract import accumulate_discussions

    async def extract(disc, diagram_data, on_window=None):
        if not diagram_data.people:
            return (
                PDP(
                    people=[
                        Person(id=-1, name="Kid"),
                        Person(id=-2, name="Mom"),
                        Person(id=-3, name="Dad"),
                    ],
                    pair_bonds=[PairBond(id=-4, person_a=-2, person_b=-3)],
                ),
                PDPDeltas(),
            )
        kid = next(p for p in diagram_data.people if p["name"] == "Kid")
        bond = diagram_data.pair_bonds[0]
        return PDP(people=[Person(id=kid["id"], parents=bond["id"])]), PDPDeltas()

    with patch("btcopilot.pdp.extract_full", extract):
        dd = accumulate_discussions([d.id for d in discussions[:2]])

    kid = next(p for p in dd.people if p["name"] == "Kid")
    assert kid["parents"] == dd.pair_bonds[0]["id"]


# Parents voting: Carol's parents split 2-1 between committed bond 100 and a
# new Dave--Eve bond; the minority run goes FIRST so first-wins != plurality.
RUN_CAROL_NEW_PARENTS_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": 500},
    {"id": 501, "name": "Dave", "gender": "male", "parents": None},
    {"id": 502, "name": "Eve", "gender": "female", "parents": None},
]
RUN_CAROL_NEW_PARENTS_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 500, "person_a": 501, "person_b": 502},
]
RUN_CAROL_COMMITTED_PARENTS_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": 100},
]
RUN_CAROL_COMMITTED_PARENTS_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
]


def test_merge_majority_vote_parents():
    """Plurality (2 votes for committed bond 100) beats the first-seen
    minority vote for the new Dave--Eve bond."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    runs = [
        _dd(RUN_CAROL_NEW_PARENTS_PEOPLE, RUN_CAROL_NEW_PARENTS_BONDS),
        _dd(RUN_CAROL_COMMITTED_PARENTS_PEOPLE, RUN_CAROL_COMMITTED_PARENTS_BONDS),
        _dd(RUN_CAROL_COMMITTED_PARENTS_PEOPLE, RUN_CAROL_COMMITTED_PARENTS_BONDS),
    ]
    delta_pdp, _ = merge_runs(runs, committed)

    edit = next(p for p in delta_pdp.people if p.id == 12)
    assert edit.parents == 100


def test_merge_k1_single_vote_parents():
    """K=1 degenerates to the single run's parent link."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    delta_pdp, _ = merge_runs(
        [_dd(RUN_CAROL_NEW_PARENTS_PEOPLE, RUN_CAROL_NEW_PARENTS_BONDS)], committed
    )

    dave = next(p for p in delta_pdp.people if p.name == "Dave")
    eve = next(p for p in delta_pdp.people if p.name == "Eve")
    bond = next(
        pb
        for pb in delta_pdp.pair_bonds
        if {pb.person_a, pb.person_b} == {dave.id, eve.id}
    )
    edit = next(p for p in delta_pdp.people if p.id == 12)
    assert edit.parents == bond.id


# Acceptance run 7 shape: the run re-extracts the primary as its own Client row
# (id=1) carrying parents and a bond to committed Simone. Without the speaker
# weld that row became a NEW delta person bridging junk into the main tree.
RUN7_PEOPLE = [
    {"id": 1, "name": "Client", "parents": 200, "primary": True},
    {"id": 2, "name": "Assistant"},
    {"id": 12, "name": "Simone", "gender": "female", "parents": None},
    {"id": 20, "name": "Garrett", "gender": "male", "parents": None},
    {"id": 21, "name": "Renee", "gender": "female", "parents": None},
]
RUN7_BONDS = [
    {"id": 200, "person_a": 20, "person_b": 21},
    {"id": 300, "person_a": 1, "person_b": 12},
]


def test_merge_welds_run_speaker_rows_onto_committed_speakers():
    """Run rows that are the run's own User/Assistant weld onto the committed
    speakers by id/primary flag — never appended as new delta people."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(
        [
            {"id": 1, "name": "User", "primary": True},
            {"id": 2, "name": "Assistant"},
            {"id": 10, "name": "Simone", "gender": "female", "parents": None},
        ],
        [],
    )
    delta_pdp, _ = merge_runs([_dd(RUN7_PEOPLE, RUN7_BONDS)], committed)

    new_names = {p.name for p in delta_pdp.people if p.id is not None and p.id < 0}
    assert new_names == {"Garrett", "Renee"}
    # The welded speaker's parents vote is dropped, never emitted as an edit
    assert all(p.id not in (1, 2) for p in delta_pdp.people)
    dyads = {tuple(sorted((pb.person_a, pb.person_b))) for pb in delta_pdp.pair_bonds}
    # The Client--Simone bond welds onto the committed primary, not a dup
    assert (1, 10) in dyads


def test_merge_welds_run_user_onto_primary_flag_id():
    """Pro-shape committed diagram: primary person has id != 1; the run's id=1
    user row still welds onto it via the primary flag."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(
        [
            {"id": 5, "name": "Patrick", "primary": True},
            {"id": 10, "name": "Simone", "gender": "female", "parents": None},
        ],
        [],
    )
    run = _dd(
        [
            {"id": 1, "name": "Client", "primary": True},
            {"id": 12, "name": "Simone", "gender": "female", "parents": None},
        ],
        [{"id": 300, "person_a": 1, "person_b": 12}],
    )
    delta_pdp, _ = merge_runs([run], committed)

    assert not [p for p in delta_pdp.people if p.id is not None and p.id < 0]
    dyads = {tuple(sorted((pb.person_a, pb.person_b))) for pb in delta_pdp.pair_bonds}
    assert dyads == {(5, 10)}


# F-003 shape: a new same-last-name sibling (Ben) appears before the committed
# person (Dennis) in the run, so the fuzzy pass consumed committed Dennis —
# Ben vanished, a duplicate Dennis was staged, and committed Dennis got a
# bogus parents edit.
F003_COMMITTED_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
    {"id": 10, "name": "Carol Park", "gender": "female", "parents": None},
    {"id": 11, "name": "Dennis Park", "gender": "male", "parents": None},
]
F003_RUN_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
    {"id": 24, "name": "Ben Park", "gender": "male", "parents": 50},
    {"id": 21, "name": "Carol Park", "gender": "female", "parents": None},
    {"id": 22, "name": "Dennis Park", "gender": "male", "parents": 50},
    {"id": 23, "name": "Frank Park", "gender": "male", "parents": None},
]
F003_RUN_BONDS = [{"id": 50, "person_a": 21, "person_b": 23}]


def test_merge_exact_name_outranks_fuzzy_crossmatch():
    """F-003: committed people weld to their exact-name counterparts; the new
    sibling stages as new instead of consuming the committed person."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(F003_COMMITTED_PEOPLE, [])
    delta_pdp, _ = merge_runs([_dd(F003_RUN_PEOPLE, F003_RUN_BONDS)], committed)

    new_names = sorted(
        p.name for p in delta_pdp.people if p.id is not None and p.id < 0
    )
    assert new_names == ["Ben Park", "Frank Park"]
    ben = next(p for p in delta_pdp.people if p.name == "Ben Park")
    frank = next(p for p in delta_pdp.people if p.name == "Frank Park")
    bond = next(
        pb
        for pb in delta_pdp.pair_bonds
        if {pb.person_a, pb.person_b} == {10, frank.id}
    )
    assert ben.parents == bond.id
    dennis_edit = next(p for p in delta_pdp.people if p.id == 11)
    assert dennis_edit.parents == bond.id


def test_merge_rejects_uncorroborated_committed_match():
    """A fuzzy last-name-only match with no structural corroboration stages a
    new person — never welds onto the committed one."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(
        [
            {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
            {"id": 11, "name": "Dennis Park", "gender": "male", "parents": None},
        ],
        [],
    )
    run = _dd(
        [
            {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
            {"id": 21, "name": "Ben Park", "gender": "male", "parents": None},
        ],
        [],
    )
    delta_pdp, _ = merge_runs([run], committed)

    new_names = [p.name for p in delta_pdp.people if p.id is not None and p.id < 0]
    assert new_names == ["Ben Park"]


def test_merge_partial_name_welds_with_structural_corroboration():
    """A first-name-only run person still welds onto the committed full-name
    person when they share a bond partner — no duplicate staged."""
    from btcopilot.personal.deepreextract import merge_runs

    committed = _dd(
        [
            {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
            {"id": 10, "name": "Carol Park", "gender": "female", "parents": None},
        ],
        [{"id": 100, "person_a": 1, "person_b": 10}],
    )
    run = _dd(
        [
            {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
            {"id": 21, "name": "Carol", "gender": "female", "parents": None},
        ],
        [{"id": 60, "person_a": 1, "person_b": 21}],
    )
    delta_pdp, _ = merge_runs([run], committed)

    assert delta_pdp.people == []
    assert delta_pdp.pair_bonds == []


def test_deep_reextract_k1(discussion):
    """K=1 passes the min-runs guard, totals windows + merge + dock ticks,
    drops the pass-counter label, reports runs_used, and the delta commits
    cleanly onto the committed diagram."""
    from btcopilot.personal import deepreextract as dre
    from btcopilot.personal import dock as dock_mod

    run = _dd(
        [
            {"id": 10, "name": "Dave", "gender": "male", "parents": None},
            {"id": 11, "name": "Eve", "gender": "female", "parents": None},
        ],
        [{"id": 100, "person_a": 10, "person_b": 11}],
    )

    def accumulate(disc_ids, on_window=None):
        if on_window:
            on_window()
        return run

    async def connected_gate_skips_llm(prompt, response_format, **kwargs):
        raise AssertionError("dock LLM called despite connected delta")

    progress = []
    with (
        patch.object(dre, "accumulate_discussions", accumulate),
        patch.object(dock_mod, "gemini_structured", connected_gate_skips_llm),
    ):
        delta_pdp, _, runs_used = dre.deep_reextract(
            discussion.id, k=1, on_progress=lambda *a: progress.append(a)
        )

    assert runs_used == 1
    total = dre._discussion_window_count(discussion) + 2
    assert progress[0] == (1, total, "Finding missing people and connections…")
    assert progress[-1] == (total, total, "Done")
    assert {p.name for p in delta_pdp.people} == {"Dave", "Eve"}

    target = DiagramData()
    target.pdp = delta_pdp
    neg_ids = [p.id for p in delta_pdp.people] + [pb.id for pb in delta_pdp.pair_bonds]
    target.commit_pdp_items(neg_ids)


# Frank has no bond — a floating component, so dock's gate fires the LLM call.
FLOATING_RUN_PEOPLE = [
    {"id": 10, "name": "Dave", "gender": "male", "parents": None},
    {"id": 11, "name": "Eve", "gender": "female", "parents": None},
    {"id": 12, "name": "Frank", "gender": "male", "parents": None},
]
FLOATING_RUN_BONDS = [{"id": 100, "person_a": 10, "person_b": 11}]


@pytest.mark.parametrize(
    "error",
    [
        ServerError(
            503, {"error": {"message": "UNAVAILABLE", "status": "UNAVAILABLE"}}
        ),
        OutputTruncatedError("LLM response truncated due to token limit."),
    ],
)
def test_deep_reextract_dock_transport_failure_keeps_undocked_delta(
    discussion, error, caplog
):
    """A dock transport failure must not kill the rebuild after the runs
    succeeded — it degrades to the un-docked delta with a loud log line."""
    from btcopilot.personal import deepreextract as dre
    from btcopilot.personal import dock as dock_mod

    run = _dd(FLOATING_RUN_PEOPLE, FLOATING_RUN_BONDS)

    async def transport_failure(prompt, response_format, **kwargs):
        raise error

    with (
        patch.object(dre, "accumulate_discussions", lambda ids, on_window=None: run),
        patch.object(dock_mod, "gemini_structured", transport_failure),
        caplog.at_level(logging.ERROR, logger="btcopilot.personal.deepreextract"),
    ):
        delta_pdp, delta_deltas, runs_used = dre.deep_reextract(discussion.id, k=1)

    assert runs_used == 1
    assert {p.name for p in delta_pdp.people} == {"Dave", "Eve", "Frank"}
    assert len(delta_pdp.pair_bonds) == 1
    assert {p.name for p in delta_deltas.people} == {"Dave", "Eve", "Frank"}
    assert any("un-docked" in rec.message for rec in caplog.records)


def test_deep_reextract_dock_validation_error_raises(discussion):
    """Only transport failures degrade — programming/validation errors from the
    dock pass still propagate."""
    from btcopilot.personal import deepreextract as dre
    from btcopilot.personal import dock as dock_mod

    run = _dd(FLOATING_RUN_PEOPLE, FLOATING_RUN_BONDS)

    async def bad_schema(prompt, response_format, **kwargs):
        raise ValueError("bad dock schema")

    with (
        patch.object(dre, "accumulate_discussions", lambda ids, on_window=None: run),
        patch.object(dock_mod, "gemini_structured", bad_schema),
    ):
        with pytest.raises(ValueError, match="bad dock schema"):
            dre.deep_reextract(discussion.id, k=1)


def test_deep_reextract_task_result_includes_runs_used(discussion):
    from types import SimpleNamespace
    from btcopilot.personal import tasks as tasks_mod

    delta = PDP(people=[Person(id=-1, name="Dave")])
    deltas = PDPDeltas(people=[Person(id=-1, name="Dave")])
    celery_self = SimpleNamespace(
        request=SimpleNamespace(id="task-1"), update_state=lambda **kw: None
    )

    with patch.object(tasks_mod, "deep_reextract", return_value=(delta, deltas, 1)):
        result = tasks_mod.deep_reextract_task(celery_self, discussion.id, 1)

    assert result["success"] is True
    assert result["k"] == 1
    assert result["runs_used"] == 1
    assert result["people_count"] == 1


def test_delta_raises_lcc_vs_committed():
    """Post-commit LCC should not decrease vs. the committed baseline."""
    from btcopilot.personal.deepreextract import merge_runs
    from btcopilot.familygraph import lcc_percent
    from btcopilot.schema import get_all_pdp_item_ids

    committed = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    baseline = lcc_percent(committed.people, committed.pair_bonds)

    runs = [
        _dd(RUN1_PEOPLE, RUN1_BONDS),
        _dd(RUN2_PEOPLE, RUN2_BONDS),
        _dd(RUN3_PEOPLE, RUN3_BONDS),
    ]
    delta_pdp, _ = merge_runs(runs, committed)

    target = _dd(COMMITTED_PEOPLE, COMMITTED_BONDS)
    target.pdp = delta_pdp
    neg_ids = [p.id for p in delta_pdp.people if p.id is not None and p.id < 0]
    neg_ids += [pb.id for pb in delta_pdp.pair_bonds if pb.id is not None and pb.id < 0]
    if neg_ids:
        target.commit_pdp_items(neg_ids)

    after = lcc_percent(target.people, target.pair_bonds)
    assert (
        after["lcc_pct"] >= baseline["lcc_pct"]
    ), f"LCC dropped after delta commit: {baseline['lcc_pct']} → {after['lcc_pct']}"
