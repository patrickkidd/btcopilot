"""Test-only HTTP surface for the sandbox harness.

Registered by create_app when TESTING is on or BTCOPILOT_TEST_ROUTES=1, never
in production config. Lives beside the models so it version-locks with them.
"""

import base64
import datetime
import pickle
from pathlib import Path

import sqlalchemy
from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy.orm import class_mapper

import btcopilot
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, Statement
from btcopilot.personal.models.discussion import DiscussionStatus
from btcopilot.personal.models.speaker import SpeakerType
from btcopilot.pro.models import (
    AccessRight,
    Activation,
    Diagram,
    License,
    Machine,
    Policy,
    User,
)
from btcopilot.testing import fixtures, llmstub
from btcopilot.testing.fixtures import LicenseState, SpeakerRole
from btcopilot.testing.llmstub import LLMMode

bp = Blueprint("test", __name__, url_prefix="/test")

DEFAULT_HARDWARE_UUID = "test-hardware-uuid"
DEFAULT_PASSWORD = "test"
LICENSED_POLICIES = (
    (btcopilot.LICENSE_PROFESSIONAL_MONTHLY, btcopilot.LICENSE_PROFESSIONAL),
    (btcopilot.LICENSE_BETA, btcopilot.LICENSE_BETA),
)


# Routers for the three ways a caller's payload can be wrong. A bodiless 500
# leaves the operator nothing to act on, but only these three become 400s —
# anything else is a backend bug and must keep failing as one.
@bp.errorhandler(ValueError)
def bad_value(error):
    return jsonify({"success": False, "error": str(error)}), 400


@bp.errorhandler(KeyError)
def missing_field(error):
    return jsonify({"success": False, "error": f"Missing required field {error}"}), 400


@bp.errorhandler(TypeError)
def malformed_payload(error):
    return jsonify({"success": False, "error": f"Malformed payload: {error}"}), 400


@bp.route("/health")
def health():
    return jsonify(
        {
            "success": True,
            "status": "ready",
            "btcopilot": str(Path(btcopilot.__file__).resolve().parent),
            "llm": LLMMode.Stub.value if llmstub.stubbed() else LLMMode.Real.value,
            "llm_keys": llmstub.credentialed(),
            "broker": current_app.config.get("CELERY_BROKER_URL"),
            "profiles": sorted(fixtures.PROFILES),
        }
    )


@bp.route("/reset", methods=["POST"])
def reset():
    db.drop_all()
    db.create_all()
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/seed", methods=["POST"])
def seed():
    body = request.get_json() or {}
    spec = fixtures.merge(fixtures.spec(body.get("profile")), body)
    hardware_uuid = body.get("hardware_uuid", DEFAULT_HARDWARE_UUID)

    # The Pro app counts a license as active only when one of its activations
    # names a machine whose code equals the app's own HARDWARE_UUID, and
    # Machine.code is globally unique — so the caller's uuid goes to the first
    # user seeded, which is the account reported as primary_user.
    users = [
        _seed_user(entry, hardware_uuid, primary=index == 0)
        for index, entry in enumerate(spec["users"])
    ]
    diagrams = [_seed_diagram(entry) for entry in spec["diagrams"]]
    discussions = [_seed_discussion(entry) for entry in spec["discussions"]]
    access_rights = [_seed_access_right(entry) for entry in spec["access_rights"]]
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "primary_user": users[0]["username"] if users else None,
            "hardware_uuid": users[0]["machine_code"] if users else None,
            "users": users,
            "diagrams": diagrams,
            "discussions": discussions,
            "access_rights": access_rights,
            "manifest": _resolve_manifest(spec["manifest"]),
        }
    )


@bp.route("/import", methods=["POST"])
def import_export():
    """Load a production export, preserving every row id so the sandbox can
    replay the exact rows a bug was reported against."""
    body = request.get_json()
    password = body.get("password", DEFAULT_PASSWORD)
    hardware_uuid = body.get("hardware_uuid", DEFAULT_HARDWARE_UUID)
    discussion_rows = body.get("discussions", [])
    speaker_rows = body.get("speakers", [])
    statement_rows = body.get("statements", [])
    chat_speakers = {
        row["id"]: _chat_speaker_ids(row, speaker_rows, statement_rows)
        for row in discussion_rows
    }

    user_data = body["user"]
    user = db.session.get(User, user_data["id"])
    if user is None:
        user = _row(
            User,
            user_data,
            exclude=("password", "reset_password_code", "free_diagram_id"),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    machine = _license(user, {}, hardware_uuid, primary=True)

    diagram_data = body.get("diagram")
    diagram = None
    if diagram_data:
        diagram = db.session.get(Diagram, diagram_data["id"])
        if diagram is None:
            diagram = _row(Diagram, diagram_data, exclude=("data",))
            diagram.data = base64.b64decode(diagram_data["data_b64"])
            db.session.add(diagram)
            db.session.flush()
        if user_data.get("free_diagram_id") in (None, diagram.id):
            user.free_diagram_id = diagram.id

    for row in discussion_rows:
        if db.session.get(Discussion, row["id"]) is None:
            db.session.add(
                _row(
                    Discussion,
                    row,
                    exclude=("chat_user_speaker_id", "chat_ai_speaker_id"),
                )
            )
    db.session.flush()

    for row in speaker_rows:
        if db.session.get(Speaker, row["id"]) is None:
            db.session.add(_row(Speaker, row))
    db.session.flush()

    for row in discussion_rows:
        discussion = db.session.get(Discussion, row["id"])
        discussion.chat_user_speaker_id, discussion.chat_ai_speaker_id = chat_speakers[
            row["id"]
        ]

    for row in statement_rows:
        if db.session.get(Statement, row["id"]) is None:
            db.session.add(_row(Statement, row))
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "primary_user": user.username,
            "hardware_uuid": machine.code if machine else None,
            "user": {
                "id": user.id,
                "username": user.username,
                "free_diagram_id": user.free_diagram_id,
                "machine_code": machine.code if machine else None,
                "licensed": _licensed(user),
            },
            "diagram": (
                {"id": diagram.id, "version": diagram.version} if diagram else None
            ),
            "discussions": [row["id"] for row in discussion_rows],
            "speakers": [row["id"] for row in speaker_rows],
            "statements": [row["id"] for row in statement_rows],
        }
    )


@bp.route("/diagrams/<int:diagram_id>", methods=["GET"])
def read_diagram(diagram_id):
    """Raw pickle bytes. Use pickle.loads() on the response content."""
    diagram = db.session.get(Diagram, diagram_id)
    if not diagram:
        return jsonify({"success": False, "error": "Not found"}), 404
    return Response(diagram.data or b"", mimetype="application/octet-stream")


@bp.route("/diagrams/<int:diagram_id>", methods=["PUT"])
def write_diagram(diagram_id):
    """Raw pickle bytes as the request body. Bumps version so a client holding
    the pre-write snapshot hits a 409 on its next save, as if another real
    client had written."""
    diagram = db.session.get(Diagram, diagram_id)
    if not diagram:
        return jsonify({"success": False, "error": "Not found"}), 404
    diagram.data = request.data
    diagram.version = (diagram.version or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "version": diagram.version})


@bp.route("/diagrams/seed_pickle", methods=["POST"])
def seed_pickle():
    """Seed a diagram from raw pickle bytes (preserves Qt types). Query params:
    user_id (required), name (optional)."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    diagram = Diagram(
        user_id=user_id, data=request.data, name=request.args.get("name", "")
    )
    db.session.add(diagram)
    db.session.commit()
    return jsonify({"success": True, "id": diagram.id})


def _seed_user(entry: dict, hardware_uuid: str, primary: bool = False) -> dict:
    username = entry["username"]
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(
            username=username,
            first_name=entry.get("first_name", "Test"),
            last_name=entry.get("last_name", "User"),
            status=entry.get("status", "confirmed"),
            roles=entry.get("roles", btcopilot.ROLE_SUBSCRIBER),
        )
        user.set_password(entry.get("password", DEFAULT_PASSWORD))
        db.session.add(user)
        db.session.flush()
    if entry.get("free_diagram", True) and user.free_diagram is None:
        user.set_free_diagram(pickle.dumps({}))
        db.session.flush()
    machine = _license(user, entry, hardware_uuid, primary)
    return {
        "id": user.id,
        "username": user.username,
        "free_diagram_id": user.free_diagram_id,
        "machine_code": machine.code if machine else None,
        "licensed": _licensed(user),
    }


def _licensed(user: User) -> bool:
    """The predicate the Pro app applies, minus the machine-code match the
    caller can make itself from machine_code: an expired user has a machine and
    activations but no active license, so machine_code alone would say usable."""
    db.session.flush()
    return any(license.active and license.activations for license in user.licenses)


def _license(
    user: User, entry: dict, hardware_uuid: str, primary: bool = False
) -> Machine | None:
    """Licenses a user that has no machine yet, whether or not this call created
    the user. Only the primary user's machine carries the caller's hardware uuid
    verbatim, because Machine.code is unique and the app activates against its
    own; every other user gets a per-user code, reported back as machine_code."""
    state = LicenseState(entry.get("license", LicenseState.Active.value))
    if state is LicenseState.None_:
        return None
    machine = Machine.query.filter_by(user_id=user.id).first()
    if machine:
        return machine
    code = entry.get("hardware_uuid") or (
        hardware_uuid if primary else f"{hardware_uuid}:{user.username}"
    )
    if Machine.query.filter_by(code=code).first():
        code = f"{code}:{user.username}"
    machine = Machine(
        user_id=user.id, name=f"Sandbox machine for {user.username}", code=code
    )
    db.session.add(machine)
    db.session.flush()
    for policy_code, product in LICENSED_POLICIES:
        policy = Policy.query.filter_by(code=policy_code).first()
        if policy is None:
            policy = Policy(
                code=policy_code,
                product=product,
                name=f"Sandbox {product}",
                interval="month",
                amount=0,
                maxActivations=10,
                active=True,
                public=True,
            )
            db.session.add(policy)
            db.session.flush()
        license = License(
            user_id=user.id,
            policy=policy,
            active=state is LicenseState.Active,
            activated_at=datetime.datetime.utcnow(),
        )
        db.session.add(license)
        db.session.flush()
        db.session.add(Activation(license_id=license.id, machine_id=machine.id))
    db.session.flush()
    return machine


def _seed_diagram(entry: dict) -> dict:
    """A diagram without a name has no natural key, so it is always created —
    the shape the pre-existing familydiagram harness sends."""
    user = _user(entry["user"]) if "user" in entry else _user_by_id(entry["user_id"])
    name = entry.get("name")
    diagram = (
        Diagram.query.filter_by(user_id=user.id, name=name).first()
        if name is not None
        else None
    )
    if diagram is None:
        diagram = Diagram(user_id=user.id, name=name)
        db.session.add(diagram)
    data = entry.get("data_b64", entry.get("data", {}))
    diagram.data = (
        base64.b64decode(data) if isinstance(data, str) else pickle.dumps(data)
    )
    diagram.version = entry.get("version", diagram.version or 1)
    diagram.alias = entry.get("alias", diagram.alias)
    diagram.use_real_names = entry.get("use_real_names", diagram.use_real_names)
    db.session.flush()
    return {"id": diagram.id, "user_id": diagram.user_id, "name": diagram.name}


def _seed_discussion(entry: dict) -> dict:
    user = _user(entry["user"]) if entry.get("user") else None
    diagram = _diagram(entry["diagram"]) if entry.get("diagram") else None
    summary = entry["summary"]
    discussion = Discussion.query.filter_by(
        user_id=user.id if user else None,
        diagram_id=diagram.id if diagram else None,
        summary=summary,
    ).first()
    if discussion is None:
        discussion = Discussion(
            user_id=user.id if user else None,
            diagram_id=diagram.id if diagram else None,
            summary=summary,
            last_topic=entry.get("last_topic"),
            status=DiscussionStatus(entry.get("status", DiscussionStatus.Ready.value)),
            discussion_date=(
                datetime.date.fromisoformat(entry["discussion_date"])
                if entry.get("discussion_date")
                else None
            ),
            extracted_through_order=entry.get("extracted_through_order"),
        )
        db.session.add(discussion)
        db.session.flush()

    speakers = {}
    for spec in entry.get("speakers", []):
        speaker = Speaker.query.filter_by(
            discussion_id=discussion.id, name=spec["name"]
        ).first()
        if speaker is None:
            speaker = Speaker(
                discussion_id=discussion.id,
                name=spec["name"],
                type=SpeakerType(spec.get("type", SpeakerType.Subject.value)),
                person_id=spec.get("person_id"),
            )
            db.session.add(speaker)
            db.session.flush()
        speakers[spec["name"]] = speaker
        role = spec.get("role")
        if role == SpeakerRole.User.value:
            discussion.chat_user_speaker_id = speaker.id
        elif role == SpeakerRole.Ai.value:
            discussion.chat_ai_speaker_id = speaker.id

    order = (
        db.session.query(db.func.max(Statement.order))
        .filter(Statement.discussion_id == discussion.id)
        .scalar()
        or 0
    )
    statement_ids = [s.id for s in discussion.statements]
    for spec in entry.get("statements", []):
        existing = Statement.query.filter_by(
            discussion_id=discussion.id, text=spec["text"]
        ).first()
        if existing:
            continue
        order += 1
        statement = Statement(
            discussion_id=discussion.id,
            text=spec["text"],
            speaker_id=(
                speakers[spec["speaker"]].id
                if spec.get("speaker") in speakers
                else None
            ),
            order=order,
        )
        db.session.add(statement)
        db.session.flush()
        statement_ids.append(statement.id)

    return {
        "id": discussion.id,
        "user_id": discussion.user_id,
        "diagram_id": discussion.diagram_id,
        "summary": discussion.summary,
        "speakers": [{"id": s.id, "name": s.name} for s in speakers.values()],
        "statements": statement_ids,
    }


def _seed_access_right(entry: dict) -> dict:
    diagram = _diagram(entry["diagram"])
    user = _user(entry["user"])
    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=user.id
    ).first()
    if access_right is None:
        access_right = AccessRight(
            diagram_id=diagram.id, user_id=user.id, right=entry["right"]
        )
        db.session.add(access_right)
    else:
        access_right.right = entry["right"]
    db.session.flush()
    return {
        "id": access_right.id,
        "diagram_id": diagram.id,
        "user_id": user.id,
        "right": access_right.right,
    }


def _chat_speaker_ids(row: dict, speakers: list, statements: list) -> tuple:
    """Exports predating the chat_*_speaker columns carry the roles only as
    speaker types. Back-fill from those rather than leaving a discussion whose
    statements have speakers but whose chat roles are empty."""
    mine = [s for s in speakers if s.get("discussion_id") == row["id"]]
    if not mine and any(s.get("discussion_id") == row["id"] for s in statements):
        raise ValueError(
            f"Export has statements for discussion {row['id']} but no speakers"
        )
    return (
        row.get("chat_user_speaker_id") or _speaker_of(mine, SpeakerType.Subject),
        row.get("chat_ai_speaker_id") or _speaker_of(mine, SpeakerType.Expert),
    )


def _speaker_of(speakers: list, speaker_type: SpeakerType):
    return next(
        (s["id"] for s in speakers if _enum(SpeakerType, s["type"]) is speaker_type),
        None,
    )


def _user(username: str) -> User:
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise ValueError(f"Seed references unknown user {username!r}")
    return user


def _user_by_id(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError(f"Seed references unknown user id {user_id}")
    return user


def _diagram(ref: str) -> Diagram:
    username, _, name = ref.partition("/")
    diagram = Diagram.query.filter_by(user_id=_user(username).id, name=name).first()
    if diagram is None:
        raise ValueError(f"Seed references unknown diagram {ref!r}")
    return diagram


def _resolve_manifest(manifest: dict) -> dict:
    resolved = {}
    for case, entry in manifest.items():
        row = dict(entry)
        if entry.get("user"):
            row["user_id"] = _user(entry["user"]).id
        if entry.get("diagram"):
            row["diagram_id"] = _diagram(entry["diagram"]).id
        if entry.get("discussion"):
            discussion = Discussion.query.filter_by(summary=entry["discussion"]).first()
            row["discussion_id"] = discussion.id if discussion else None
            if entry.get("statement_order") and discussion:
                statement = Statement.query.filter_by(
                    discussion_id=discussion.id, order=entry["statement_order"]
                ).first()
                row["statement_id"] = statement.id if statement else None
        resolved[case] = row
    return resolved


def _row(model, data: dict, exclude: tuple[str, ...] = ()):
    """Build a model instance from an export row, taking the column list from
    the model so it cannot drift from the schema."""
    columns = class_mapper(model).columns
    kwargs = {
        key: _coerce(columns[key], value)
        for key, value in data.items()
        if key in columns and key not in exclude
    }
    return model(**kwargs)


def _coerce(column, value):
    if value is None or not isinstance(value, str):
        return value
    if isinstance(column.type, sqlalchemy.Enum) and column.type.enum_class:
        return _enum(column.type.enum_class, value)
    if isinstance(column.type, sqlalchemy.DateTime):
        return datetime.datetime.fromisoformat(value)
    if isinstance(column.type, sqlalchemy.Date):
        return datetime.date.fromisoformat(value)
    if isinstance(column.type, sqlalchemy.LargeBinary):
        return base64.b64decode(value)
    return value


def _enum(enum_class, value: str):
    """Exports carry the enum by value or by name, and prod rows predate the
    values_callable convention, so accept both spellings."""
    by_value = {member.value: member for member in enum_class}
    if value in by_value:
        return by_value[value]
    by_name = {name.lower(): member for name, member in enum_class.__members__.items()}
    if value.lower() in by_name:
        return by_name[value.lower()]
    raise ValueError(f"{value!r} is not a valid {enum_class.__name__}")
