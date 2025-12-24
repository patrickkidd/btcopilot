import btcopilot
from btcopilot import auth, pdp
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, AccessRight, User
from btcopilot.schema import DiagramData, EventKind, asdict
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal.models.speaker import Speaker
from btcopilot.training import diagramlayout

import logging
from flask import Blueprint, request, jsonify, render_template


_log = logging.getLogger(__name__)

bp = Blueprint(
    "diagrams",
    __name__,
    url_prefix="/diagrams",
    template_folder="../templates",
)
bp = minimum_role(btcopilot.ROLE_AUDITOR)(bp)


@bp.route("", methods=["POST"])
def create():
    current_user = auth.current_user()

    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name", "").strip()

    if not user_id:
        return jsonify({"error": "user id is required"}), 400

    if not name:
        return jsonify({"error": "Diagram name is required"}), 400

    # Create new diagram
    diagram = Diagram(
        user_id=user_id,
        name=name,
        data=b"",  # Empty initial data
    )

    # Initialize with database containing default User and Assistant people
    database_with_defaults = DiagramData.create_with_defaults()
    diagram.set_diagram_data(database_with_defaults)

    db.session.add(diagram)
    db.session.commit()

    _log.info(
        f"Auditor {current_user.username} created diagram '{name}' (ID: {diagram.id})"
    )

    return jsonify(
        {
            "success": True,
            "diagram": {
                "id": diagram.id,
                "name": diagram.name,
                "created_at": (
                    diagram.created_at.isoformat() if diagram.created_at else None
                ),
            },
        }
    )


@bp.route("/<int:diagram_id>", methods=["DELETE"])
def delete(diagram_id):
    from btcopilot.training.models import Feedback

    current_user = auth.current_user()

    # Find the diagram
    diagram = Diagram.query.get(diagram_id)

    if not diagram:
        return jsonify({"error": "Diagram not found"}), 404

    # Check permissions: user owns diagram OR user is admin
    is_owner = diagram.user_id == current_user.id
    is_admin = btcopilot.ROLE_ADMIN in current_user.roles

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    discussions = Discussion.query.filter_by(diagram_id=diagram_id)
    if discussions.count() > 0 and not is_admin:
        return (
            jsonify({"error": "Only admins can delete diagrams with discussions"}),
            400,
        )

    diagram_name = diagram.name
    diagram_owner_id = diagram.user_id

    # Manually cascade delete related records
    # 1. Delete feedbacks for statements in discussions of this diagram
    Feedback.query.filter(
        Feedback.statement_id.in_(
            db.session.query(Statement.id).filter(
                Statement.discussion_id.in_(
                    db.session.query(Discussion.id).filter(
                        Discussion.diagram_id == diagram_id
                    )
                )
            )
        )
    ).delete(synchronize_session=False)

    # 2. Delete statements in discussions of this diagram
    Statement.query.filter(
        Statement.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # 3. Delete speakers in discussions of this diagram
    Speaker.query.filter(
        Speaker.discussion_id.in_(
            db.session.query(Discussion.id).filter(Discussion.diagram_id == diagram_id)
        )
    ).delete(synchronize_session=False)

    # 4. Delete discussions for this diagram
    Discussion.query.filter(Discussion.diagram_id == diagram_id).delete(
        synchronize_session=False
    )

    # 5. Delete access rights for this diagram
    access_rights = AccessRight.query.filter_by(diagram_id=diagram_id)
    access_rights.delete(synchronize_session=False)

    # 6. Finally delete the diagram itself
    db.session.delete(diagram)
    db.session.commit()

    if is_admin and not is_owner:
        _log.info(
            f"Admin {current_user.username} deleted diagram '{diagram_name}' (ID: {diagram_id}) owned by user ID {diagram_owner_id}"
        )
    else:
        _log.info(
            f"User {current_user.username} deleted their own diagram '{diagram_name}' (ID: {diagram_id})"
        )

    return jsonify({"success": True})


@bp.route("/<int:diagram_id>/access-rights", methods=["GET"])
def get_access_rights(diagram_id):
    current_user = auth.current_user()

    diagram = Diagram.query.get_or_404(diagram_id)

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    access_rights = AccessRight.query.filter_by(diagram_id=diagram_id).all()

    rights_data = [
        ar.as_dict(include={"user": {"only": ["username", "first_name", "last_name"]}})
        for ar in access_rights
    ]

    return jsonify({"success": True, "access_rights": rights_data})


@bp.route("/<int:diagram_id>/access-rights", methods=["POST"])
def grant_access_right(diagram_id):
    current_user = auth.current_user()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    target_user_id = data.get("user_id")
    right = data.get("right")

    if not target_user_id:
        return jsonify({"error": "user_id required"}), 400

    if right not in [btcopilot.ACCESS_READ_ONLY, btcopilot.ACCESS_READ_WRITE]:
        return (
            jsonify(
                {
                    "error": f"Invalid right. Must be '{btcopilot.ACCESS_READ_ONLY}' or '{btcopilot.ACCESS_READ_WRITE}'"
                }
            ),
            400,
        )

    diagram = Diagram.query.get_or_404(diagram_id)
    target_user = User.query.get(target_user_id)

    if not target_user:
        return jsonify({"error": "User not found"}), 404

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    if target_user_id == diagram.user_id:
        return (
            jsonify({"error": "Cannot grant access rights to diagram owner"}),
            400,
        )

    existing_right = AccessRight.query.filter_by(
        diagram_id=diagram_id, user_id=target_user_id
    ).first()

    if existing_right:
        old_right = existing_right.right
        existing_right.right = right
        db.session.commit()

        _log.info(
            f"User {current_user.username} updated access right for user {target_user.username} "
            f"on diagram {diagram_id} from {old_right} to {right}"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Updated access to {right}",
                "access_right": existing_right.as_dict(
                    include={"user": {"only": ["username", "first_name", "last_name"]}}
                ),
            }
        )
    else:
        diagram.grant_access(target_user, right, _commit=True)

        new_right = AccessRight.query.filter_by(
            diagram_id=diagram_id, user_id=target_user_id
        ).first()

        _log.info(
            f"User {current_user.username} granted {right} access to user {target_user.username} "
            f"on diagram {diagram_id}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Granted {right} access",
                    "access_right": new_right.as_dict(
                        include={
                            "user": {"only": ["username", "first_name", "last_name"]}
                        }
                    ),
                }
            ),
            201,
        )


@bp.route("/<int:diagram_id>/access-rights/<int:access_right_id>", methods=["DELETE"])
def revoke_access_right(diagram_id, access_right_id):
    current_user = auth.current_user()

    diagram = Diagram.query.get_or_404(diagram_id)

    is_owner = diagram.user_id == current_user.id
    is_admin = current_user.has_role(btcopilot.ROLE_ADMIN)

    if not (is_owner or is_admin):
        return jsonify({"error": "Access denied"}), 403

    access_right = AccessRight.query.get_or_404(access_right_id)

    if access_right.diagram_id != diagram_id:
        return jsonify({"error": "Access right does not belong to this diagram"}), 400

    target_user = User.query.get(access_right.user_id)
    target_username = (
        target_user.username if target_user else f"User {access_right.user_id}"
    )

    db.session.delete(access_right)
    db.session.commit()

    _log.info(
        f"User {current_user.username} revoked access from user {target_username} on diagram {diagram_id}"
    )

    return jsonify({"success": True, "message": "Access revoked"})


@bp.route("/render/<int:statement_id>")
@bp.route("/render/<int:statement_id>/<auditor_id>")
def render(statement_id: int, auditor_id: str = None):
    from flask import url_for

    current_user = auth.current_user()
    statement = Statement.query.get_or_404(statement_id)
    discussion = statement.discussion
    is_embed = request.args.get("embed", "false").lower() == "true"

    breadcrumbs = [
        {"title": "Coding", "url": url_for("training.audit.index")},
        {
            "title": discussion.summary or "Discussion",
            "url": url_for("training.discussions.audit", discussion_id=discussion.id),
        },
        {"title": "Family Diagram", "url": None},
    ]

    # Get committed diagram data (includes User ID: 1, Assistant ID: 2)
    diagram_data = discussion.diagram.get_diagram_data() if discussion.diagram else None

    # Get cumulative PDP from statements
    pdp_data = pdp.cumulative(discussion, statement, auditor_id)

    # Build people list: start with committed diagram people, then merge PDP people
    people_by_id = {}

    # Add committed diagram people first (including User ID: 1, excluding Assistant ID: 2)
    if diagram_data:
        for person_dict in diagram_data.people:
            pid = person_dict.get("id")
            if pid is not None and pid != 2:  # Skip Assistant (ID: 2)
                people_by_id[pid] = {
                    "id": pid,
                    "name": person_dict.get("name") or f"Person {pid}",
                    "gender": person_dict.get("gender", "unknown"),
                    "deceased": person_dict.get("deceased", False),
                    "primary": person_dict.get("primary", False),
                    "parents": person_dict.get("parents"),
                }

    # Merge PDP people (overwrites committed if same ID, adds new negative IDs)
    for person in pdp_data.people:
        person_dict = asdict(person)
        person_dict["name"] = person.name or f"Person {person.id}"
        person_dict["gender"] = person.gender.value if person.gender else "unknown"
        person_dict["deceased"] = False
        person_dict["primary"] = False
        people_by_id[person.id] = person_dict

    people_list = list(people_by_id.values())

    # Build pair bonds
    pair_bonds_list = []
    pair_bonds_by_persons = {}

    # Add committed diagram pair bonds
    if diagram_data:
        for pb_dict in diagram_data.pair_bonds:
            person_a = pb_dict.get("personA") or pb_dict.get("person_a")
            person_b = pb_dict.get("personB") or pb_dict.get("person_b")
            if person_a and person_b:
                key = tuple(sorted([person_a, person_b]))
                pb_data = {
                    "id": pb_dict.get("id"),
                    "person_a": person_a,
                    "person_b": person_b,
                    "married": pb_dict.get("married", True),
                    "separated": pb_dict.get("separated", False),
                    "divorced": pb_dict.get("divorced", False),
                }
                pair_bonds_list.append(pb_data)
                pair_bonds_by_persons[key] = pb_data

    # Add PDP pair bonds
    for pb in pdp_data.pair_bonds:
        key = tuple(sorted([pb.person_a, pb.person_b]))
        pb_dict = asdict(pb)
        pb_dict["married"] = True
        pb_dict["separated"] = False
        pb_dict["divorced"] = False
        if key in pair_bonds_by_persons:
            pair_bonds_by_persons[key].update(pb_dict)
        else:
            pair_bonds_list.append(pb_dict)
            pair_bonds_by_persons[key] = pb_dict

    # Create pair bonds from married/bonded events (first pass)
    # Track these separately - they should not be subject to orphan filtering
    marriage_pair_bond_ids = set()
    for event in pdp_data.events:
        if event.kind in (EventKind.Married, EventKind.Bonded):
            if event.person and event.spouse:
                key = tuple(sorted([event.person, event.spouse]))
                if key not in pair_bonds_by_persons:
                    pb_dict = {
                        "id": event.id,
                        "person_a": event.person,
                        "person_b": event.spouse,
                        "married": event.kind == EventKind.Married,
                        "separated": False,
                        "divorced": False,
                    }
                    pair_bonds_list.append(pb_dict)
                    pair_bonds_by_persons[key] = pb_dict
                    marriage_pair_bond_ids.add(event.id)

    # Apply separated/divorced status (second pass, after pair bonds exist)
    for event in pdp_data.events:
        if event.kind == EventKind.Separated:
            if event.person and event.spouse:
                key = tuple(sorted([event.person, event.spouse]))
                if key in pair_bonds_by_persons:
                    pair_bonds_by_persons[key]["separated"] = True
        elif event.kind == EventKind.Divorced:
            if event.person and event.spouse:
                key = tuple(sorted([event.person, event.spouse]))
                if key in pair_bonds_by_persons:
                    pair_bonds_by_persons[key]["divorced"] = True

    # Build parent-child relationships
    parent_child = []
    referenced_pair_bond_ids = set()
    for person_dict in people_list:
        if person_dict.get("parents"):
            parent_child.append(
                {
                    "child_id": person_dict["id"],
                    "pair_bond_id": person_dict["parents"],
                }
            )
            referenced_pair_bond_ids.add(person_dict["parents"])

    # Clean up pair bonds: remove invalid refs, duplicates, and orphans
    person_ids = {p["id"] for p in people_list}
    seen_person_pairs: set[tuple[int, int]] = set()
    cleaned_pair_bonds = []

    for pb in pair_bonds_list:
        pb_id = pb.get("id")
        person_a = pb.get("person_a")
        person_b = pb.get("person_b")

        # Skip if either person doesn't exist
        if person_a not in person_ids or person_b not in person_ids:
            _log.debug(
                f"Render: removing pair bond {pb_id}: references non-existent person"
            )
            continue

        # Skip duplicates (same person pair)
        person_pair = tuple(sorted([person_a, person_b]))
        if person_pair in seen_person_pairs:
            _log.debug(f"Render: removing duplicate pair bond {pb_id}")
            continue

        # Skip orphaned pair bonds (not referenced by any person's parents)
        # But keep pair bonds from marriage events - they represent spousal relationships
        if pb_id not in referenced_pair_bond_ids and pb_id not in marriage_pair_bond_ids:
            _log.debug(f"Render: removing orphaned pair bond {pb_id}")
            continue

        seen_person_pairs.add(person_pair)
        cleaned_pair_bonds.append(pb)

    render_data = {
        "people": people_list,
        "pair_bonds": cleaned_pair_bonds,
        "parent_child": parent_child,
    }

    layout = diagramlayout.compute(render_data)

    if is_embed:
        return render_template(
            "components/family_diagram_svg.html",
            data=render_data,
            layout=layout,
            statement_id=statement_id,
            auditor_id=auditor_id,
        )

    return render_template(
        "diagram_render.html",
        data=render_data,
        layout=layout,
        statement_id=statement_id,
        auditor_id=auditor_id,
        discussion=discussion,
        statement=statement,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
    )
