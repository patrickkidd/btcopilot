"""The play-by-play for one cluster.

It is coach-authored (R-0074): the coach picks which moves, in what order, and
writes the words around them, and every move it names is a chip it cannot
invent. Until the agent loop is wired, this endpoint writes the moves in date
order with plain connecting words, which is the same shape the coach will
produce and the same markup the page already renders."""

from flask import jsonify, request

from btcopilot.companion.blueprint import bp, diagram
from btcopilot.companion.timeline import build_timeline
from btcopilot.personal.refs import RefKind
from btcopilot.schema import DiagramData

JOINS = ("It starts when ", "Then ", "After that ", "Next ", "And then ")
CLOSE = "That is the stretch. What do you remember about it?"


def _chapter(payload: dict, cluster_id: str) -> dict:
    for chapter in payload["chapters"]:
        if chapter["id"] == cluster_id or cluster_id in chapter["cluster_ids"]:
            return chapter
    raise ValueError(f"No cluster {cluster_id!r} on the line")


def _chip(event: dict) -> str:
    return f"[[{RefKind.Events.value}:{event['id']}|{event['label']}]]"


@bp.route("/play", methods=["POST"])
def play():
    body = request.get_json()
    unknown = set(body) - {"cluster_id"}
    if unknown:
        raise ValueError(f"Unknown play field(s): {', '.join(sorted(unknown))}")
    cluster_id = body["cluster_id"]

    dia = diagram()
    payload = build_timeline(dia.get_diagram_data() if dia else DiagramData())
    chapter = _chapter(payload, cluster_id)
    by_id = {event["id"]: event for event in payload["events"]}
    moves = sorted(
        (by_id[i] for i in chapter["event_ids"] if i in by_id),
        key=lambda e: (e["dateTime"] or "", e["id"]),
    )

    sentences = [
        f"{JOINS[min(index, len(JOINS) - 1)]}{_chip(event)}."
        for index, event in enumerate(moves)
    ]
    opening = f"{chapter['title']} — {len(moves)} moves. "
    return jsonify(
        {
            "cluster_id": chapter["id"],
            "statement": opening + " ".join(sentences) + " " + CLOSE,
        }
    )
