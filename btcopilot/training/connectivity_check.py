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


def lcc_percent(people: list, pair_bonds: list) -> dict:
    """
    Returns:
        total: int — non-default people count
        components: int — number of connected components
        lcc: int — size of largest connected component
        lcc_pct: float — lcc / total * 100 (0.0 if total == 0)
    """
    default = _default_ids(people)
    nodes = {_person_id(p) for p in people if _person_id(p) not in default and _person_id(p) is not None}

    if not nodes:
        return {"total": 0, "components": 0, "lcc": 0, "lcc_pct": 0.0}

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

    # BFS connected components
    visited: set[int] = set()
    component_sizes: list[int] = []
    for start in nodes:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        size = 0
        while queue:
            cur = queue.pop()
            size += 1
            for nb in adj[cur]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        component_sizes.append(size)

    lcc = max(component_sizes) if component_sizes else 0
    total = len(nodes)
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
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.diagram:
            _measure_diagram(args.diagram)
        else:
            _measure_gt_discussions(args.discussion)


if __name__ == "__main__":
    main()