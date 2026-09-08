"""The play-by-play for one cluster of the line.

It is coach-authored (R-0074): the coach picks which moves, in what order, and
writes the words around them, and every move it names is a chip it cannot
invent. The page taps either a stored cluster or a cluster the line grouped by
itself, so both resolve here to the same thing — a set of event ids and a name.
"""

from flask import jsonify, request

from btcopilot import auth
from btcopilot.personal.routes import bp, current_session, diagram
from btcopilot.personal.timeline import build_timeline
from btcopilot.personal.playturn import PlayTurn
from btcopilot.personal.discussions import sync_chat_speakers
from btcopilot.schema import ClusterSource, DiagramData


def _cluster(data: DiagramData, cluster_id: str) -> dict:
    for cluster in data.clusters:
        if isinstance(cluster, dict) and str(cluster.get("id")) == str(cluster_id):
            return cluster
    for cluster in build_timeline(data)["clusters"]:
        if cluster["id"] == cluster_id or cluster_id in cluster["cluster_ids"]:
            return {
                "id": cluster["id"],
                "name": cluster["title"],
                "title": cluster["title"],
                "summary": cluster["summary"] or "",
                "eventIds": cluster["event_ids"],
                "source": ClusterSource.Derived.value,
            }
    raise ValueError(f"No cluster {cluster_id!r} on the line")


@bp.route("/play", methods=["POST"])
def play():
    body = request.get_json()
    unknown = set(body) - {"cluster_id"}
    if unknown:
        raise ValueError(f"Unknown play field(s): {', '.join(sorted(unknown))}")

    dia = diagram()
    data = dia.get_diagram_data() if dia else DiagramData()
    discussion = current_session(auth.current_user(), create=True)
    sync_chat_speakers(discussion)
    return jsonify(
        PlayTurn(
            data, _cluster(data, body["cluster_id"]), discussion=discussion
        ).run()
    )
