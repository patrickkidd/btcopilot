import os

from flask import jsonify, render_template

from btcopilot import auth
from btcopilot.companion.blueprint import bp, current_session
from btcopilot.companion.sessions import session_payload, statements_payload
from btcopilot.companion.timeline import build_timeline
from btcopilot.personal.models import Discussion
from btcopilot.schema import DiagramData, get_all_pdp_item_ids

STATIC_VERSION = str(
    int(
        os.path.getmtime(
            os.path.join(os.path.dirname(__file__), "static", "companion.js")
        )
    )
)


@bp.route("/")
def index():
    user = auth.current_user()
    discussion = current_session(user)
    return render_template(
        "companion/index.html",
        user=user,
        session=session_payload(discussion) if discussion else None,
        version=STATIC_VERSION,
        statements=statements_payload(discussion) if discussion else [],
    )


@bp.route("/timeline")
def timeline():
    user = auth.current_user()
    diagram = user.free_diagram
    data = diagram.get_diagram_data() if diagram else DiagramData()
    payload = build_timeline(data)
    payload["extraction"] = _extraction_status(user, diagram, data)
    return jsonify(payload)


def _extraction_status(user, diagram, data: DiagramData) -> dict:
    """The picture only reflects committed diagram state; never let it look
    fresher than it is. States: extracting (a background extraction is
    running), pending_review (extracted items staged but not committed),
    chat_ahead (conversation past the extraction cursor), current."""
    state = "current"
    if diagram:
        discussions = Discussion.query.filter_by(
            user_id=user.id, diagram_id=diagram.id
        ).all()
        if any(d.extracting for d in discussions):
            state = "extracting"
        elif get_all_pdp_item_ids(data.pdp):
            state = "pending_review"
        else:
            for d in discussions:
                orders = [s.order for s in d.statements if s.order is not None]
                if orders and max(orders) > (d.extracted_through_order or 0):
                    state = "chat_ahead"
                    break
    return {"state": state, "up_to_date": state == "current"}
