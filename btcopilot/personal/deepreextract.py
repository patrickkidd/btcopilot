"""
Deep re-extraction: run K independent from-empty accumulations and merge via
match_people consensus into a PDP delta relative to the committed diagram.

The K runs never write to the DB — all DiagramData mutations are in-memory.
"""

import asyncio
import copy
import logging
import math

import nest_asyncio

from btcopilot.schema import DiagramData, PDP, PDPDeltas, Person, PairBond, from_dict
from btcopilot import pdp as pdp_mod
from btcopilot.training.connectivity_check import _default_ids
from btcopilot.training.f1_metrics import match_people

_log = logging.getLogger(__name__)


# Valid values for K. K=8 is the shipping default ("max fidelity"): K=6 ceilings
# at the >=90% LCC line, K=8 reliably clears it (see decisions/log.md 2026-06-03).
class RunCount:
    Four = 4
    Eight = 8


VALID_K = {RunCount.Four, RunCount.Eight}
# Default is the faster/cheaper K=4 tier; "max fidelity" (K=8) is opt-in.
DEFAULT_K = RunCount.Four

# Per-run resilience: each from-empty accumulation makes ~13 LLM calls, any of
# which can transiently time out or yield a momentarily invalid PDP. Retry a
# failed run, and tolerate a few permanent losses — consensus only needs enough
# samples to cover the variance-distributed bridges.
RUN_ATTEMPTS = 3
MIN_RUNS = 3

# Cooperative cancel: the client's status poll refreshes a short-lived redis
# "alive" key; the task checks it between windows and aborts if the user
# cancelled or the key expired (app quit). Avoids killing the worker and stops
# orphaned background rebuilds. Heartbeat TTL > client poll interval (~1s).
REBUILD_ALIVE_TTL = 30


class RebuildCancelled(Exception):
    """Raised to abort deep_reextract when the client cancelled or vanished."""


def _rebuild_redis():
    from btcopilot.extensions import celery

    backend = getattr(celery, "backend", None)
    return getattr(backend, "client", None)


def mark_rebuild_alive(task_id: str) -> None:
    import redis as _redis

    r = _rebuild_redis()
    if r is None:
        return
    try:
        r.setex(f"rebuild:alive:{task_id}", REBUILD_ALIVE_TTL, "1")
    except _redis.exceptions.RedisError:
        pass


def request_rebuild_cancel(task_id: str) -> None:
    import redis as _redis

    r = _rebuild_redis()
    if r is None:
        return
    try:
        r.setex(f"rebuild:cancel:{task_id}", 600, "1")
    except _redis.exceptions.RedisError:
        pass


def rebuild_should_abort(task_id: str) -> bool:
    """True if the user cancelled (explicit flag) or stopped polling (the alive
    key expired). Redis errors degrade to 'keep going' — a heartbeat blip must
    not kill a long rebuild."""
    import redis as _redis

    r = _rebuild_redis()
    if r is None:
        return False
    try:
        if r.exists(f"rebuild:cancel:{task_id}"):
            return True
        return not r.exists(f"rebuild:alive:{task_id}")
    except _redis.exceptions.RedisError:
        return False


# ── accumulation helper (shared with connectivity_check) ─────────────────────


def _discussion_window_count(disc) -> int:
    """How many extraction windows a from-empty extract_full of disc will run."""
    n = len(disc.statements)
    return math.ceil(n / pdp_mod.WINDOW_SIZE) if n else 0


def accumulate_discussions(disc_ids: list[int], on_window=None) -> DiagramData:
    """Fresh from-empty accumulation of disc_ids (in order). DB read-only —
    extracted_through_order is mutated in memory only; no db.session.commit.
    Returns the final DiagramData with all items committed to positive IDs.
    on_window(), forwarded to extract_full, fires once per extraction window
    for fine-grained progress."""
    from btcopilot.personal.models import Discussion

    nest_asyncio.apply()
    diagram_data = DiagramData()

    for disc_id in disc_ids:
        disc = Discussion.query.get(disc_id)
        if disc is None:
            _log.warning(f"accumulate_discussions: disc {disc_id} not found, skipping")
            continue
        # In-memory only — never persisted
        disc.extracted_through_order = None

        ai_pdp, _ = asyncio.run(
            pdp_mod.extract_full(disc, diagram_data, on_window=on_window)
        )
        diagram_data.pdp = ai_pdp

        neg_ids = [p.id for p in ai_pdp.people if p.id is not None and p.id < 0]
        neg_ids += [e.id for e in ai_pdp.events if e.id < 0]
        neg_ids += [
            pb.id for pb in ai_pdp.pair_bonds if pb.id is not None and pb.id < 0
        ]
        if neg_ids:
            diagram_data.commit_pdp_items(neg_ids)

    return diagram_data


# ── merge / reconcile ─────────────────────────────────────────────────────────


def _people_from_diagram(diagram_data: DiagramData) -> list[Person]:
    return [
        from_dict(Person, p) for p in diagram_data.people if p.get("id") is not None
    ]


def _bonds_from_diagram(diagram_data: DiagramData) -> list[PairBond]:
    return [
        from_dict(PairBond, pb)
        for pb in diagram_data.pair_bonds
        if pb.get("id") is not None
    ]


def _next_neg(existing_ids: set[int]) -> int:
    """Return the next available negative ID not in existing_ids."""
    n = -1
    while n in existing_ids:
        n -= 1
    return n


def _bond_dyad(pb: PairBond) -> tuple[int, int] | None:
    if pb.person_a is not None and pb.person_b is not None:
        return tuple(sorted([pb.person_a, pb.person_b]))
    return None


def merge_runs(
    runs: list[DiagramData],
    committed: DiagramData,
) -> tuple[PDP, PDPDeltas]:
    """
    Merge K run DiagramDatas against committed, producing a PDP delta.

    Seeded with committed people+bonds (positive IDs). For each run, map
    run people → accumulator via match_people; new run people → append with
    fresh negative IDs. Same for pair_bonds. After all runs, delta = entries
    with negative IDs relative to original_committed_ids.

    Returns (PDP, PDPDeltas) both containing only the new/edited items
    (negative IDs for new; positive-ID Person edits for parent links).
    """
    # Seed accumulator from committed state
    acc_people: list[Person] = _people_from_diagram(committed)
    acc_bonds: list[PairBond] = _bonds_from_diagram(committed)
    original_committed_ids: set[int] = {p.id for p in acc_people if p.id is not None}
    original_bond_ids: set[int] = {pb.id for pb in acc_bonds if pb.id is not None}

    # Default people (User + Assistant) are excluded from name-matching to prevent
    # "User matches any name" special-case in match_people from mapping real people
    # from the run to the placeholder client/assistant entries.
    default_acc_ids: set[int] = _default_ids(committed.people)

    # Tracks IDs allocated so far (positive + any negatives we'll add)
    all_ids: set[int] = set(original_committed_ids) | set(original_bond_ids)

    # Parent-link edits: committed person id → bond id to set as parents
    parent_edits: dict[int, int] = {}

    for run_dd in runs:
        run_people = _people_from_diagram(run_dd)
        run_bonds = _bonds_from_diagram(run_dd)

        # Exclude default acc people from matching to prevent User/Assistant from
        # absorbing real family members via the "User matches anything" rule.
        matchable_acc = [p for p in acc_people if p.id not in default_acc_ids]

        # match run people → accumulator people (non-default only)
        _, id_map = match_people(run_people, matchable_acc, run_bonds, acc_bonds)

        # Append unmatched run people as new negative-id entries
        matched_run_ids = set(id_map.keys())
        for rp in run_people:
            if rp.id in matched_run_ids:
                continue
            neg = _next_neg(all_ids)
            all_ids.add(neg)
            new_p = copy.copy(rp)
            new_p.id = neg
            new_p.parents = None  # will fix below after bond merging
            acc_people.append(new_p)
            id_map[rp.id] = neg

        # Now handle pair bonds
        # Build accumulator dyad → bond id index
        acc_dyads: dict[tuple[int, int], int] = {}
        for pb in acc_bonds:
            dyad = _bond_dyad(pb)
            if dyad is not None:
                acc_dyads[dyad] = pb.id

        # remap run bond endpoints via id_map
        for rb in run_bonds:
            mapped_a = (
                id_map.get(rb.person_a, rb.person_a)
                if rb.person_a is not None
                else None
            )
            mapped_b = (
                id_map.get(rb.person_b, rb.person_b)
                if rb.person_b is not None
                else None
            )
            if mapped_a is None or mapped_b is None:
                continue
            dyad = tuple(sorted([mapped_a, mapped_b]))
            if dyad in acc_dyads:
                # Bond already exists — record the bond id for use in id_map of bonds
                id_map[rb.id] = acc_dyads[dyad]
                continue
            # New bond
            neg = _next_neg(all_ids)
            all_ids.add(neg)
            new_pb = PairBond(id=neg, person_a=mapped_a, person_b=mapped_b)
            acc_bonds.append(new_pb)
            acc_dyads[dyad] = neg
            id_map[rb.id] = neg

        # Set parents on new accumulator people based on run's parent links
        for rp in run_people:
            acc_id = id_map.get(rp.id)
            if acc_id is None or rp.parents is None:
                continue
            # Never set parents on default people (User/Assistant)
            if acc_id in default_acc_ids:
                continue
            # Find the accumulator person
            acc_p = next((p for p in acc_people if p.id == acc_id), None)
            if acc_p is None:
                continue
            # Map run bond id → accumulator bond id
            mapped_bond = id_map.get(rp.parents)
            if mapped_bond is None:
                continue
            if acc_p.parents is None:
                acc_p.parents = mapped_bond
                # If the person was originally committed and now gets a parent link, record edit
                if acc_id in original_committed_ids:
                    parent_edits[acc_id] = mapped_bond

    # Build delta: new people/bonds (negative IDs) + positive-ID parent edits
    new_people = [
        p for p in acc_people if p.id is not None and p.id not in original_committed_ids
    ]
    new_bonds = [
        pb for pb in acc_bonds if pb.id is not None and pb.id not in original_bond_ids
    ]

    # Parent edits: build minimal Person edits (positive id, parents only)
    edit_people = [
        Person(id=committed_id, parents=bond_id)
        for committed_id, bond_id in parent_edits.items()
    ]

    delta_pdp = PDP(
        people=new_people + edit_people,
        events=[],
        pair_bonds=new_bonds,
    )
    delta_pdp_deltas = PDPDeltas(
        people=new_people + edit_people,
        events=[],
        pair_bonds=new_bonds,
    )
    return delta_pdp, delta_pdp_deltas


# ── main entry point ──────────────────────────────────────────────────────────


def deep_reextract(
    discussion_id: int,
    k: int,
    on_progress=None,
    cancel_check=None,
) -> tuple[PDP, PDPDeltas]:
    """
    Run K independent from-empty accumulations over all discussions sharing
    the diagram of discussion_id, merge via match_people consensus, and return
    the delta PDP relative to the current committed diagram.

    DB is read-only throughout. No db.session.commit is called.

    Args:
        discussion_id: any discussion whose diagram to re-extract
        k: number of independent runs (must be in VALID_K)
        on_progress: optional callback(current, total, label)

    Returns:
        tuple[PDP, PDPDeltas] — the consensus delta
    """
    if k not in VALID_K:
        raise ValueError(f"k must be in {VALID_K}, got {k}")

    from btcopilot.personal.models import Discussion
    from btcopilot.pro.models.diagram import Diagram

    disc = Discussion.query.get(discussion_id)
    if disc is None:
        raise ValueError(f"Discussion {discussion_id} not found")
    if disc.diagram_id is None:
        raise ValueError(f"Discussion {discussion_id} has no diagram")

    # All discussions sharing the same diagram, ordered deterministically
    sibling_discs = (
        Discussion.query.filter_by(diagram_id=disc.diagram_id)
        .order_by(Discussion.id)
        .all()
    )
    disc_ids = [d.id for d in sibling_discs]

    committed_diagram = Diagram.query.get(disc.diagram_id)
    if committed_diagram is None:
        raise ValueError(f"Diagram {disc.diagram_id} not found")
    committed_dd = committed_diagram.get_diagram_data()

    # Progress ticks per extraction WINDOW (each ~20-30s) across all passes so
    # the bar keeps moving and never looks stuck. Windows are pre-counted for a
    # sensible percent; the label is user-facing, not internal "run i/k" jargon.
    windows_per_pass = sum(_discussion_window_count(d) for d in sibling_discs)
    total = k * max(1, windows_per_pass) + 1  # +1 for the final merge step
    progress = {"done": 0}
    runs: list[DiagramData] = []

    for i in range(k):
        label = f"Finding missing people and connections… (pass {i + 1} of {k})"

        def tick(_label=label):
            if cancel_check and cancel_check():
                raise RebuildCancelled()
            progress["done"] += 1
            if on_progress:
                on_progress(min(progress["done"], total - 1), total, _label)

        run_dd = None
        for attempt in range(1, RUN_ATTEMPTS + 1):
            try:
                run_dd = accumulate_discussions(disc_ids, on_window=tick)
                break
            except RebuildCancelled:
                raise
            except Exception as e:
                _log.warning(
                    f"deep_reextract: pass {i + 1} attempt {attempt} failed — {e}"
                )
        if run_dd is None:
            _log.warning(
                f"deep_reextract: pass {i + 1} dropped after {RUN_ATTEMPTS} attempts"
            )
            continue
        runs.append(run_dd)
        _log.info(
            f"deep_reextract: pass {i + 1}/{k} done — "
            f"{len(run_dd.people)} people, {len(run_dd.pair_bonds)} bonds"
        )

    if len(runs) < MIN_RUNS:
        raise RuntimeError(
            f"deep_reextract: only {len(runs)}/{k} runs succeeded "
            f"(min {MIN_RUNS}); transient extraction failures too frequent"
        )

    if on_progress:
        on_progress(total - 1, total, "Merging the results…")

    delta_pdp, delta_pdp_deltas = merge_runs(runs, committed_dd)

    if on_progress:
        on_progress(total, total, "Done")

    return delta_pdp, delta_pdp_deltas
