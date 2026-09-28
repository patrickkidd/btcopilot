"""The play-by-play for one cluster of the line.

It is coach-authored (R-0074, R-0563): the coach tells the cluster as dated
snapshots through its one tool, naming only the cluster's own events. A
play-by-play is offered for the clusters the record holds, so what is asked
for here is one of those.
"""

import logging

from flask import jsonify, request

from btcopilot import auth
from btcopilot.routes import bp, current_session, writable_diagram
from btcopilot.playturn import PlayTurn, Untellable
from btcopilot.discussions import sync_chat_speakers
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)


def _cluster(data: DiagramData, cluster_id: str) -> dict:
    for cluster in data.clusters:
        if isinstance(cluster, dict) and str(cluster.get("id")) == str(cluster_id):
            return cluster
    raise ValueError(f"No cluster {cluster_id!r} on the line")


@bp.errorhandler(Untellable)
def _untellable(e):
    """The coach could not tell it: a refusal the page shows in its own words,
    never a bare server error."""
    _log.warning(f"Play not told: {e.why}")
    return str(e), 422


@bp.route("/play", methods=["POST"])
def play():
    body = request.get_json()
    unknown = set(body) - {"cluster_id"}
    if unknown:
        raise ValueError(f"Unknown play field(s): {', '.join(sorted(unknown))}")

    dia = writable_diagram()
    data = dia.get_diagram_data() if dia else DiagramData()
    discussion = current_session(auth.current_user(), create=True)
    sync_chat_speakers(discussion)
    return jsonify(
        PlayTurn(
            data, _cluster(data, body["cluster_id"]), discussion=discussion
        ).run()
    )
