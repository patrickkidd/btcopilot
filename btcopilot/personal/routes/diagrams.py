import logging
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
from btcopilot.schema import asdict, PDP, Event, DiagramData, from_dict

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
    ret["diagram_data"] = asdict(diagram.get_diagram_data())

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

    expected_version = request.json.get("expected_version")
    data = request.json.get("diagram_data")

    if data is not None:
        diagram_data = from_dict(DiagramData, data)
    else:
        diagram_data = None

    success, new_version = diagram.update_with_version_check(
        expected_version, diagram_data=diagram_data
    )

    if not success:
        return (
            jsonify(
                version=diagram.version, diagram_data=asdict(diagram.get_diagram_data())
            ),
            409,
        )

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
