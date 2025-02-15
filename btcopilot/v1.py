import logging
import json

from flask import (
    Blueprint,
    request,
    current_app,
)

_log = logging.getLogger(__name__)


def init_app(app):
    app.register_blueprint(bp)


bp = Blueprint("v1", __name__, url_prefix="/v1")


@bp.route("/chat", methods=["POST"])
@bp.route("/chat/<int:conversation_id>", methods=["POST"])
def chat(conversation_id: int = None):
    args = request.json

    if not "question" in args:
        return ("The parameter 'question' is required", 400)

    response = current_app.engine.ask(args["question"])

    return {
        "conversation_id": conversation_id,
        "response": response.answer,
        "sources": response.sources,
    }


# @bp.route("/conversations/<int:conversation_id>", methods=("GET", "DELETE"))
# def copilot_conversations(conversation_id: int = None):

#     if request.method == "POST":

#         chain = conversation_chains[conversation_id]

#     else:  # delete
#         conversation = Conversation.query.get(id)
#         if not conversation:
#             return ("Not Found", 404)
#         elif request.method == "DELETE":
#             db.session.delete(conversation)
#     db.session.commit()
#     if request.method != "DELETE":
#         db.session.refresh(conversation)
#     return pickle.dumps(conversation.as_dict())
