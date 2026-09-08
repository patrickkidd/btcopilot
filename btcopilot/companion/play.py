"""The play-by-play for one stretch of the line.

It is coach-authored (R-0074): the coach picks which moves, in what order, and
writes the words around them, and every move it names is a chip it cannot
invent. The page taps either a stored cluster or a chapter the line grouped by
itself, so both resolve here to the same thing — a set of event ids and a name.
"""

from flask import jsonify, request

from btcopilot import auth
from btcopilot.companion.blueprint import bp, current_session, diagram
from btcopilot.companion.timeline import build_timeline
from btcopilot.personal.playturn import PlayTurn
from btcopilot.personal.routes.discussions import _sync_chat_speakers
from btcopilot.schema import ClusterSource, DiagramData


def _cluster(data: DiagramData, cluster_id: str) -> dict:
    for cluster in data.clusters:
        if isinstance(cluster, dict) and str(cluster.get("id")) == str(cluster_id):
            return cluster
    for chapter in build_timeline(data)["chapters"]:
        if chapter["id"] == cluster_id or cluster_id in chapter["cluster_ids"]:
            return {
                "id": chapter["id"],
                "name": chapter["title"],
                "title": chapter["title"],
                "summary": chapter["summary"] or "",
                "eventIds": chapter["event_ids"],
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
    _sync_chat_speakers(discussion)
    return jsonify(
        PlayTurn(
            data, _cluster(data, body["cluster_id"]), discussion=discussion
        ).run()
    )
