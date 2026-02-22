import logging
import random

from flask import Blueprint, render_template, request, jsonify, url_for

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.training.utils import get_breadcrumbs
from btcopilot.tests.personal.synthetic import PersonaTrait, AttachmentStyle

_log = logging.getLogger(__name__)

bp = Blueprint(
    "synthetic",
    __name__,
    url_prefix="/synthetic",
    template_folder="../templates",
)
bp = minimum_role(btcopilot.ROLE_ADMIN)(bp)

_AGE_RANGES = {
    "20s": (22, 29),
    "30s": (30, 39),
    "40s": (40, 49),
    "50s": (50, 58),
}


@bp.route("/")
def index():
    current_user = auth.current_user()
    breadcrumbs = get_breadcrumbs("synthetic")

    from btcopilot.personal.models import SyntheticPersona

    generated_personas = SyntheticPersona.query.order_by(
        SyntheticPersona.created_at.desc()
    ).all()

    users = (
        User.query.filter(
            User.roles.contains(btcopilot.ROLE_AUDITOR)
            | User.roles.contains(btcopilot.ROLE_ADMIN)
        )
        .order_by(User.username)
        .all()
    )

    trait_options = [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in PersonaTrait
    ]
    attachment_options = [
        {"value": a.value, "label": a.value.replace("_", " ").title()}
        for a in AttachmentStyle
    ]

    return render_template(
        "synthetic_index.html",
        generated_personas=generated_personas,
        trait_options=trait_options,
        attachment_options=attachment_options,
        users=users,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
        btcopilot=btcopilot,
    )


@bp.route("/generate-persona", methods=["POST"])
def generate_persona_route():
    from btcopilot.tests.personal.synthetic import generate_persona

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    traits = [PersonaTrait(t) for t in data.get("traits", [])]
    attachment_style = AttachmentStyle(data["attachment_style"])
    sex = data["sex"]
    low, high = _AGE_RANGES.get(data.get("age_range"), (30, 39))
    age = random.randint(low, high)

    db_persona = generate_persona(traits, attachment_style, sex, age)
    db.session.commit()

    return jsonify({"persona_id": db_persona.id, "name": db_persona.name})


@bp.route("/generate", methods=["POST"])
def generate():
    from btcopilot.extensions import celery

    if celery is None:
        return (
            jsonify({"error": "Celery not available - start Redis and Celery worker"}),
            503,
        )

    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    persona_id = data.get("persona_id")
    if not persona_id:
        return jsonify({"error": "persona_id is required"}), 400

    max_turns = data.get("max_turns", 20)
    skip_extraction = data.get("skip_extraction", False)
    username = data.get("username") or current_user.username

    task = celery.send_task(
        "generate_synthetic_discussion",
        args=[int(persona_id), username, int(max_turns), skip_extraction],
    )

    _log.info(
        f"User {current_user.username} started synthetic generation task {task.id} "
        f"for persona_id {persona_id}"
    )

    return jsonify({"task_id": task.id})


@bp.route("/task/<task_id>", methods=["GET"])
def task_status(task_id):
    from btcopilot.extensions import celery
    from celery.result import AsyncResult

    if celery is None:
        return jsonify({"status": "error", "error": "Celery not available"}), 503

    result = AsyncResult(task_id, app=celery)

    if result.failed():
        return jsonify({"status": "error", "error": str(result.result)})
    elif result.ready():
        task_result = result.get()
        return jsonify(
            {
                "status": "complete",
                "discussion_id": task_result["discussion_id"],
                "turn_count": task_result["turn_count"],
                "quality_score": task_result.get("quality_score"),
                "coverage_rate": task_result.get("coverage_rate"),
                "redirect_url": url_for(
                    "training.discussions.audit",
                    discussion_id=task_result["discussion_id"],
                ),
            }
        )
    elif result.state == "PROGRESS":
        meta = result.info or {}
        return jsonify(
            {
                "status": "progress",
                "current": meta.get("current", 0),
                "total": meta.get("total", 0),
                "user_text": meta.get("user_text", ""),
                "ai_text": meta.get("ai_text", ""),
            }
        )
    else:
        return jsonify({"status": "pending"})
