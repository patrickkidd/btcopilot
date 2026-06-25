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
from btcopilot.familygraph import (
    bond_endpoints,
    components,
    default_ids,
    lcc_percent,
    person_id,
    person_parents,
)
from btcopilot.schema import DiagramData
from btcopilot import pdp as pdp_mod

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
    disc_ids = sorted(
        {
            fb.statement.discussion_id
            for fb in query.all()
            if fb.statement and fb.statement.discussion_id
        }
    )

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
    Accumulate real-chat discussions in order, then measure LCC on the final
    committed state. Delegates to personal.deepreextract.accumulate_discussions.

    Returns the lcc_percent stats dict for the final accumulated diagram.
    """
    from btcopilot.personal.deepreextract import accumulate_discussions

    print(f"Accumulating {len(disc_ids)} discussions in order: {disc_ids}\n")
    diagram_data = accumulate_discussions(disc_ids)
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
        all_pdp_ids += [
            pb.id for pb in ai_pdp.pair_bonds if pb.id is not None and pb.id < 0
        ]
        if all_pdp_ids:
            try:
                diagram_data.commit_pdp_items(all_pdp_ids)
            except Exception as e:
                print(f"  Disc {disc_id}: COMMIT FAILED — {e}")

    # Find connected components and list the disconnected people
    comps = components(diagram_data.people, diagram_data.pair_bonds)
    default = default_ids(diagram_data.people)
    nd_nodes = {pid for comp in comps for pid in comp} - default
    if not nd_nodes:
        print("No non-default people found.")
        return

    person_by_id = {
        person_id(p): p for p in diagram_data.people if person_id(p) is not None
    }

    print(f"\nTotal non-default people: {len(nd_nodes)}")
    print(f"Components: {len(comps)}, LCC size: {len(comps[0] - default)}")
    print(f"\nDisconnected components (not in LCC):")
    for comp in comps[1:]:
        members = sorted(comp - default)
        if not members:
            continue
        print(f"\n  Component size {len(members)}:")
        for pid in members:
            p = person_by_id.get(pid, {})
            name = (
                p.get("name") or p.get("firstName", "")
                if isinstance(p, dict)
                else getattr(p, "name", "?")
            )
            pb_id = person_parents(p)
            bonds = [
                pb for pb in diagram_data.pair_bonds if pid in (bond_endpoints(pb))
            ]
            print(
                f"    id={pid} name={name!r} parents_bond={pb_id} pair_bonds={len(bonds)}"
            )


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
