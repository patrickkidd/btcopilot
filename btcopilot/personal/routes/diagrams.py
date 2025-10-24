import logging
from dataclasses import asdict
from flask import Blueprint, request, jsonify, abort
from sqlalchemy.orm import subqueryload

import vedana
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

    if diagram.user_id != user.id and not user.has_role(vedana.ROLE_ADMIN):
        abort(403)

    ret = diagram.as_dict(
        include={
            "discussions": {"include": ["statements", "speakers"]},
            "access_rights": {},
        },
        exclude="data",
    )
    ret["database"] = asdict(diagram.get_diagram_data())

    return jsonify(ret)


@diagrams_bp.route("/<int:diagram_id>/discussions")
def discussions(diagram_id):
    user = auth.current_user()

    diagram = Diagram.query.get(diagram_id)
    if not diagram:
        abort(404)

    if diagram.id != user.id:
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


@diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/accept", methods=["POST"])
def pdp_accept(diagram_id: int, pdp_id: int):
    """
    Negative integers give a 404, so do (id * -1) before passing to endpoint and
    it will get converted.
    """
    diagram = Diagram.query.get_or_404(diagram_id)
    if not diagram:
        return jsonify(success=False, message="Diagram not found"), 404

    if diagram.user_id != auth.current_user().id:
        return jsonify(success=False, message="Unauthorized"), 401

    database = diagram.get_diagram_data()
    pdp_id = -pdp_id  # Convert to negative ID for PDP items

    def done():
        diagram.set_diagram_data(database)
        db.session.commit()
        return jsonify(success=True)

    for person in database.pdp.people:
        if person.id == pdp_id:
            _log.info(f"Accepting PDP person with id: {pdp_id}")
            database.pdp.people.remove(person)
            database.add_person(person)
            return done()

    for event in database.pdp.events:
        if event.id == pdp_id:
            _log.info(f"Accepting PDP event with id: {pdp_id}")
            database.pdp.events.remove(event)
            database.add_event(event)
            return done()

    return jsonify(success=False, message="PDP item not found"), 404


@diagrams_bp.route("/<int:diagram_id>/pdp/<int:pdp_id>/reject", methods=["POST"])
def pdp_reject(diagram_id: int, pdp_id: int):
    """
    Negative integers give a 404, so do (id * -1) before passing to endpoint and
    it will get converted.
    """
    diagram = Diagram.query.get_or_404(diagram_id)
    if not diagram:
        return jsonify(success=False, message="Diagram not found"), 404

    if diagram.user_id != auth.current_user().id:
        return jsonify(success=False, message="Unauthorized"), 401

    database = diagram.get_diagram_data()
    pdp_id = -pdp_id  # Convert to negative ID for PDP items

    def done():
        diagram.set_diagram_data(database)
        db.session.commit()
        return jsonify(success=True)

    for person in database.pdp.people:
        if person.id == pdp_id:
            _log.info(f"Rejecting PDP person with id: {pdp_id}")
            database.pdp.people.remove(person)
            return done()

    for event in database.pdp.events:
        if event.id == pdp_id:
            _log.info(f"Rejecting PDP event with id: {pdp_id}")
            database.pdp.events.remove(event)
            return done()

    return jsonify(success=False, message="PDP item not found"), 404
