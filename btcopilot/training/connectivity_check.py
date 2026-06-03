"""
Connectivity check — measures LCC % of extracted family trees.

LCC % = largest connected component / total non-default people.
Nodes: people. Edges: pair_bonds (person_a--person_b) + parent-child
links resolved through pair_bonds.

Default people (User id=1 / primary=True, Assistant id=2) are excluded.

Usage:
    # Measure over GT discussions (fresh extraction):
    uv run python -m btcopilot.training.connectivity_check

    # Measure a single GT discussion:
    uv run python -m btcopilot.training.connectivity_check --discussion 50

    # Measure a server diagram from the DB (committed state, no extraction):
    uv run python -m btcopilot.training.connectivity_check --diagram 1924

    # Accumulate real-chat discussions in order (mimics live diagram growth):
    uv run python -m btcopilot.training.connectivity_check --accumulate 55,58,60
    uv run python -m btcopilot.training.connectivity_check --accumulate 28,57
"""

import argparse
import asyncio

import nest_asyncio

from btcopilot.app import create_app
from btcopilot.schema import DiagramData, PDP, Person, PairBond
from btcopilot import pdp as pdp_mod


# ── graph helpers ─────────────────────────────────────────────────────────────

def _default_ids(people: list) -> set[int]:
    """IDs of User (primary or id=1) and Assistant (id=2) people."""
    ids: set[int] = set()
    for p in people:
        if isinstance(p, dict):
            pid = p.get("id")
            if p.get("primary") or pid == 1 or pid == 2:
                if pid is not None:
                    ids.add(pid)
        elif isinstance(p, Person):
            if p.id in (1, 2) or getattr(p, "primary", False):
                if p.id is not None:
                    ids.add(p.id)
    return ids


def _person_id(p) -> int | None:
    return p.get("id") if isinstance(p, dict) else p.id


def _bond_endpoints(pb) -> tuple[int | None, int | None]:
    if isinstance(pb, dict):
        return pb.get("person_a"), pb.get("person_b")
    return pb.person_a, pb.person_b


def _person_parents(p) -> int | None:
    return p.get("parents") if isinstance(p, dict) else p.parents


def _assistant_ids(people: list) -> set[int]:
    """ID(s) of the Assistant (id=2) — the AI is never part of the family graph."""
    return {_person_id(p) for p in people if _person_id(p) == 2}


def lcc_percent(people: list, pair_bonds: list) -> dict:
    """
    LCC% of the family tree, EXCLUDING the User and Assistant from the count but
    keeping the User as a CONNECTING node. In a Personal-app diagram the User is
    the proband: spouse, children, parents and siblings all connect through them,
    so deleting the User node fragments correctly-extracted families. The Assistant
    (id=2) is the AI and is dropped from the graph entirely.

    Returns:
        total: int — non-default people count (excludes User + Assistant)
        components: int — number of connected components (User-as-connector graph)
        lcc: int — non-default members of the largest component
        lcc_pct: float — lcc / total * 100 (0.0 if total == 0)
    """
    default = _default_ids(people)           # User + Assistant — excluded from the count
    assistant = _assistant_ids(people)       # Assistant only — excluded from the graph
    nodes = {_person_id(p) for p in people
             if _person_id(p) is not None and _person_id(p) not in assistant}

    total = sum(1 for p in people if _person_id(p) is not None and _person_id(p) not in default)
    if not nodes or total == 0:
        return {"total": total, "components": 0, "lcc": 0, "lcc_pct": 0.0}

    # adjacency
    adj: dict[int, set[int]] = {n: set() for n in nodes}

    bond_by_id: dict[int, tuple[int | None, int | None]] = {}
    for pb in pair_bonds:
        a, b = _bond_endpoints(pb)
        pb_id = pb.get("id") if isinstance(pb, dict) else pb.id
        if pb_id is not None:
            bond_by_id[pb_id] = (a, b)
        if a in nodes and b in nodes:
            adj[a].add(b)
            adj[b].add(a)

    # parent-child edges: child → each parent via PairBond
    for p in people:
        pid = _person_id(p)
        if pid not in nodes:
            continue
        pb_id = _person_parents(p)
        if pb_id is None or pb_id not in bond_by_id:
            continue
        pa, pb_p = bond_by_id[pb_id]
        for parent in (pa, pb_p):
            if parent in nodes:
                adj[pid].add(parent)
                adj[parent].add(pid)

    # DFS connected components; size each by its NON-DEFAULT members only
    visited: set[int] = set()
    component_sizes: list[int] = []
    for start in nodes:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        nd_size = 0
        while queue:
            cur = queue.pop()
            if cur not in default:
                nd_size += 1
            for nb in adj[cur]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        component_sizes.append(nd_size)

    lcc = max(component_sizes) if component_sizes else 0
    return {
        "total": total,
        "components": len(component_sizes),
        "lcc": lcc,
        "lcc_pct": round(lcc / total * 100, 1) if total else 0.0,
    }


# ── extraction-based measurement ──────────────────────────────────────────────

def _measure_gt_discussions(discussion_id=None):
    nest_asyncio.apply()

    from btcopilot.training.models import Feedback
    from btcopilot.personal.models import Statement, Discussion

    query = (
        Feedback.query.join(Statement, Feedback.statement_id == Statement.id)
        .filter(Feedback.approved == True)
        .filter(Feedback.feedback_type == "extraction")
    )
    if discussion_id:
        query = query.filter(Statement.discussion_id == discussion_id)
    disc_ids = sorted({
        fb.statement.discussion_id
        for fb in query.all()
        if fb.statement and fb.statement.discussion_id
    })

    if not disc_ids:
        print("No GT discussions found.")
        return

    print(f"Measuring connectivity on {len(disc_ids)} GT discussion(s)...\n")
    totals = []
    for disc_id in disc_ids:
        disc = Discussion.query.get(disc_id)
        diagram_data = DiagramData()
        try:
            ai_pdp, _ = asyncio.run(pdp_mod.extract_full(disc, diagram_data))
        except Exception as e:
            print(f"  Disc {disc_id}: EXTRACTION FAILED — {e}")
            continue
        stats = lcc_percent(ai_pdp.people, ai_pdp.pair_bonds)
        print(
            f"  Disc {disc_id} ({disc.summary or ''}): "
            f"{stats['total']} people, {stats['components']} components, "
            f"LCC {stats['lcc_pct']}%"
        )
        totals.append(stats)

    if len(totals) > 1:
        avg_lcc = round(sum(s["lcc_pct"] for s in totals) / len(totals), 1)
        print(f"\nAverage LCC: {avg_lcc}%  ({len(totals)} discussions)")


def _measure_accumulated_discussions(disc_ids: list[int]) -> dict:
    """
    Accumulate real-chat discussions in created_at order, carrying diagram_data
    forward (each discussion sees the committed output of prior ones), then
    measure LCC on the final committed state.

    This mirrors how a live Personal-app diagram grows: discussion N sees all
    people/pair_bonds committed from discussions 1..N-1.

    Returns the lcc_percent stats dict for the final accumulated diagram.
    """
    nest_asyncio.apply()

    from btcopilot.personal.models import Discussion

    print(f"Accumulating {len(disc_ids)} discussions in order: {disc_ids}\n")

    diagram_data = DiagramData()

    for disc_id in disc_ids:
        disc = Discussion.query.get(disc_id)
        if disc is None:
            print(f"  Disc {disc_id}: NOT FOUND — skipping")
            continue
        disc.extracted_through_order = None
        print(f"  Disc {disc_id} ({disc.summary or ''}, {len(disc.statements)} stmts)...", end=" ", flush=True)
        try:
            ai_pdp, _ = asyncio.run(pdp_mod.extract_full(disc, diagram_data))
        except Exception as e:
            print(f"EXTRACTION FAILED — {e}")
            continue

        # Point diagram_data.pdp at the extraction result so commit_pdp_items
        # can find the items (extract_full resets diagram_data.pdp to PDP()
        # at the start and never writes the final result back).
        diagram_data.pdp = ai_pdp

        # Commit all new PDP items (negative IDs) to diagram_data so the next
        # discussion sees them as committed (positive-ID) context.
        all_pdp_ids = [p.id for p in ai_pdp.people if p.id is not None and p.id < 0]
        all_pdp_ids += [e.id for e in ai_pdp.events if e.id < 0]
        all_pdp_ids += [pb.id for pb in ai_pdp.pair_bonds if pb.id is not None and pb.id < 0]

        if all_pdp_ids:
            try:
                id_mapping = diagram_data.commit_pdp_items(all_pdp_ids)
                print(f"committed {len(id_mapping)} items")
            except Exception as e:
                print(f"COMMIT FAILED — {e}")
        else:
            print("no new PDP items")

    stats = lcc_percent(diagram_data.people, diagram_data.pair_bonds)
    print(
        f"\nFinal accumulated state: {stats['total']} people, "
        f"{stats['components']} components, LCC {stats['lcc_pct']}%"
    )
    return stats


def _dump_disconnected(disc_ids: list[int]) -> None:
    """
    Accumulate discussions and print disconnected people for failure-mode
    classification: (a) duplicate, (b) implicit-spouse missing PairBond,
    (c) truly isolated.
    """
    nest_asyncio.apply()

    from btcopilot.personal.models import Discussion

    diagram_data = DiagramData()

    for disc_id in disc_ids:
        disc = Discussion.query.get(disc_id)
        if disc is None:
            print(f"  Disc {disc_id}: NOT FOUND — skipping")
            continue
        disc.extracted_through_order = None
        try:
            ai_pdp, _ = asyncio.run(pdp_mod.extract_full(disc, diagram_data))
        except Exception as e:
            print(f"  Disc {disc_id}: EXTRACTION FAILED — {e}")
            continue
        diagram_data.pdp = ai_pdp
        all_pdp_ids = [p.id for p in ai_pdp.people if p.id is not None and p.id < 0]
        all_pdp_ids += [e.id for e in ai_pdp.events if e.id < 0]
        all_pdp_ids += [pb.id for pb in ai_pdp.pair_bonds if pb.id is not None and pb.id < 0]
        if all_pdp_ids:
            try:
                diagram_data.commit_pdp_items(all_pdp_ids)
            except Exception as e:
                print(f"  Disc {disc_id}: COMMIT FAILED — {e}")

    # Find connected components and list the disconnected people
    default_ids = _default_ids(diagram_data.people)
    nodes = {
        _person_id(p)
        for p in diagram_data.people
        if _person_id(p) not in default_ids and _person_id(p) is not None
    }

    bond_by_id: dict[int, tuple] = {}
    for pb in diagram_data.pair_bonds:
        a, b = _bond_endpoints(pb)
        pb_id = pb.get("id") if isinstance(pb, dict) else pb.id
        if pb_id is not None:
            bond_by_id[pb_id] = (a, b)

    adj: dict[int, set[int]] = {n: set() for n in nodes}
    for pb in diagram_data.pair_bonds:
        a, b = _bond_endpoints(pb)
        if a in nodes and b in nodes:
            adj[a].add(b)
            adj[b].add(a)
    for p in diagram_data.people:
        pid = _person_id(p)
        if pid not in nodes:
            continue
        pb_id = _person_parents(p)
        if pb_id is None or pb_id not in bond_by_id:
            continue
        pa, pb_p = bond_by_id[pb_id]
        for parent in (pa, pb_p):
            if parent in nodes:
                adj[pid].add(parent)
                adj[parent].add(pid)

    visited: set[int] = set()
    components: list[set[int]] = []
    for start in nodes:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        comp: set[int] = set()
        while queue:
            cur = queue.pop()
            comp.add(cur)
            for nb in adj[cur]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        components.append(comp)

    if not components:
        print("No non-default people found.")
        return

    lcc_size = max(len(c) for c in components)
    person_by_id = {_person_id(p): p for p in diagram_data.people if _person_id(p) is not None}

    print(f"\nTotal non-default people: {len(nodes)}")
    print(f"Components: {len(components)}, LCC size: {lcc_size}")
    print(f"\nDisconnected components (not in LCC):")
    for comp in sorted(components, key=len, reverse=True):
        if len(comp) == lcc_size:
            continue  # skip the LCC
        print(f"\n  Component size {len(comp)}:")
        for pid in sorted(comp):
            p = person_by_id.get(pid, {})
            name = p.get("name") or p.get("firstName", "") if isinstance(p, dict) else getattr(p, "name", "?")
            pb_id = _person_parents(p)
            bonds = [pb for pb in diagram_data.pair_bonds if pid in (_bond_endpoints(pb))]
            print(f"    id={pid} name={name!r} parents_bond={pb_id} pair_bonds={len(bonds)}")


def _measure_diagram(diagram_id: int):
    from btcopilot.pro.models.diagram import Diagram

    diagram = Diagram.query.get(diagram_id)
    if diagram is None:
        print(f"Diagram {diagram_id} not found.")
        return
    dd = diagram.get_diagram_data()
    stats = lcc_percent(dd.people, dd.pair_bonds)
    print(
        f"Diagram {diagram_id} ({diagram.name or ''}): "
        f"{stats['total']} people, {stats['components']} components, "
        f"LCC {stats['lcc_pct']}%"
    )


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--discussion", type=int)
    parser.add_argument("--diagram", type=int)
    parser.add_argument(
        "--accumulate",
        type=str,
        help="Comma-separated discussion IDs to accumulate in order (e.g. 55,58,60)",
    )
    parser.add_argument(
        "--dump-disconnected",
        type=str,
        help="Comma-separated discussion IDs; accumulate then dump disconnected people",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.diagram:
            _measure_diagram(args.diagram)
        elif args.accumulate:
            disc_ids = [int(x.strip()) for x in args.accumulate.split(",")]
            _measure_accumulated_discussions(disc_ids)
        elif args.dump_disconnected:
            disc_ids = [int(x.strip()) for x in args.dump_disconnected.split(",")]
            _dump_disconnected(disc_ids)
        else:
            _measure_gt_discussions(args.discussion)


if __name__ == "__main__":
    main()