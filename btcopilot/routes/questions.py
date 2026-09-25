"""The user dismisses a question the coach asked: it is closed as declined by
them, never removed, and the coach sees it on the map (R-0077). The record
refuses anything else a user writes on a question."""

from flask import abort, jsonify, request

from btcopilot.routes import asked_diagram, bp, delta, edit
from btcopilot.schema import ItemKind

WRITABLE = ("state", "outcome")


def _find(question_id: str) -> dict:
    for question in asked_diagram().get_diagram_data().questions:
        if question["id"] == question_id:
            return question
    abort(404, description=f"No question {question_id} on this diagram")


@bp.route("/questions/<question_id>", methods=["PATCH"])
def update_question(question_id: str):
    body = request.get_json()
    unknown = set(body) - set(WRITABLE)
    if unknown:
        raise ValueError(f"Unknown question field(s): {', '.join(sorted(unknown))}")
    _find(question_id)
    edit([delta(ItemKind.Question, question_id, field, value) for field, value in body.items()])
    question = _find(question_id)
    return jsonify({field: question[field] for field in ("id", *WRITABLE)})
