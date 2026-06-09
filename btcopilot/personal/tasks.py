import copy
import logging

from sqlalchemy import update as sql_update

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.personal.deepreextract import (
    deep_reextract,
    mark_rebuild_alive,
    rebuild_should_abort,
    RebuildCancelled,
)
from btcopilot.schema import asdict
from btcopilot.training.connectivity_check import lcc_percent, _person_id

_log = logging.getLogger(__name__)


def deep_reextract_task(self, discussion_id: int, k: int):
    _log.info(f"deep_reextract_task() discussion={discussion_id}, k={k}")
    task_id = self.request.id
    mark_rebuild_alive(task_id)

    try:

        def on_progress(current, total, label):
            self.update_state(
                state="PROGRESS",
                meta={"current": current, "total": total, "label": label},
            )

        delta_pdp, _ = deep_reextract(
            discussion_id,
            k,
            on_progress=on_progress,
            cancel_check=lambda: rebuild_should_abort(task_id),
        )

        disc = db.session.get(Discussion, discussion_id)
        if disc is None:
            raise ValueError(f"Discussion {discussion_id} not found after extraction")
        if disc.diagram is None:
            raise ValueError(
                f"Discussion {discussion_id} has no diagram after extraction"
            )

        diagram = disc.diagram
        for _ in range(32):
            db.session.refresh(diagram)
            expected_version = diagram.version
            diagram_data = diagram.get_diagram_data()
            diagram_data.pdp = delta_pdp
            ok, _ = diagram.update_with_version_check(
                expected_version, diagram_data=diagram_data
            )
            if ok:
                break
            db.session.rollback()
        else:
            raise RuntimeError("Diagram write contention; deep_reextract_task failed")

        db.session.commit()

        # Projected connectivity if the user accepts the whole staged delta —
        # commit it onto a throwaway copy and measure. (diagram_data itself only
        # holds the delta as a pending pdp; its committed people are unchanged.)
        projected = copy.deepcopy(diagram_data)
        neg_ids = [p.id for p in delta_pdp.people if p.id is not None and p.id < 0]
        neg_ids += [
            pb.id for pb in delta_pdp.pair_bonds if pb.id is not None and pb.id < 0
        ]
        if neg_ids:
            projected.commit_pdp_items(neg_ids)
        for ep in [p for p in delta_pdp.people if p.id is not None and p.id > 0]:
            for p in projected.people:
                if _person_id(p) == ep.id:
                    p["parents"] = ep.parents
        stats = lcc_percent(projected.people, projected.pair_bonds)

        return {
            "success": True,
            "people_count": len(delta_pdp.people),
            "events_count": len(delta_pdp.events),
            "pair_bonds_count": len(delta_pdp.pair_bonds),
            "pdp": asdict(delta_pdp),
            "lcc_pct": stats["lcc_pct"],
            "k": k,
        }
    except RebuildCancelled:
        _log.info(f"deep_reextract_task cancelled (discussion={discussion_id})")
        return {"cancelled": True}
    finally:
        db.session.execute(
            sql_update(Discussion)
            .where(Discussion.id == discussion_id)
            .values(extracting=False)
        )
        db.session.commit()
