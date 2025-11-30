import logging
import base64
from flask import Blueprint, request, jsonify, abort
from sqlalchemy.orm import subqueryload
from sqlalchemy.exc import NoResultFound

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, AccessRight
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal.models.speaker import Speaker

_log = logging.getLogger(__name__)


diagrams_bp = Blueprint("diagrams", __name__, url_prefix="/diagrams")


@diagrams_bp.route("/<int:diagram_id>")
def get(diagram_id):
    user = auth.current_user()

    diagram = Diagram.query.get(diagram_id)
    if not diagram:
        abort(404)

    if diagram.user_id != user.id and not user.has_role(btcopilot.ROLE_ADMIN):
        abort(403)

    ret = diagram.as_dict(
        include={
            "discussions": {"include": ["statements", "speakers"]},
            "access_rights": {},
        },
        exclude="data",
    )
    ret["data"] = base64.b64encode(diagram.data).decode("utf-8")

    _log.info(f"Fetched diagram {diagram.id}, version: {diagram.version}")
    return jsonify(ret)


@diagrams_bp.route("/<int:diagram_id>", methods=["PUT"])
def update(diagram_id):
    """
    Sibling to /v1/diagrams/<diagram_id> PUT endpoint, but with personal
    edition, i.e. JSON.body.
    """
    user = auth.current_user()

    diagram = Diagram.query.get(diagram_id)
    if not diagram:
        abort(404)

    if not diagram.check_write_access(user):
        abort(403)

    if request.json is None:
        _log.error(
            f"request.json is None. Content-Type: {request.content_type}, "
            f"Content-Length: {request.content_length}, Data: {request.data[:100] if request.data else 'None'}"
        )
        return jsonify(error="Invalid JSON or missing Content-Type header"), 400

    expected_version = request.json.get("expected_version")
    data_b64 = request.json.get("data")

    if data_b64 is not None:
        new_data = base64.b64decode(data_b64)
    else:
        new_data = None

    success, new_version = diagram.update_with_version_check(
        expected_version, new_data=new_data
    )

    if not success:
        return (
            jsonify(
                version=diagram.version,
                data=base64.b64encode(diagram.data).decode("utf-8"),
            ),
            409,
        )
    else:
        _log.info(f"Updated diagram {diagram.id} new_version: {new_version}")

    db.session.commit()

    return jsonify(success=True, version=new_version)


@diagrams_bp.route("/<int:diagram_id>/discussions")
def discussions(diagram_id):
    user = auth.current_user()

    diagram = Diagram.query.get(diagram_id)
    if not diagram:
        abort(404)

    if diagram.user_id != user.id:
        abort(403)

    discussions = (
        Discussion.query.options(subqueryload(Discussion.statements))
        .filter_by(diagram_id=diagram_id)
        .all()
    )
    return jsonify(
        [
            discussion.as_dict(include=["statements", "speakers"])
            for discussion in discussions
        ]
    )
