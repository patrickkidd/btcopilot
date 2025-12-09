import logging

from flask import Blueprint, render_template, request, jsonify, url_for

import btcopilot
from btcopilot import auth
from btcopilot.auth import minimum_role
from btcopilot.pro.models import User
from btcopilot.training.utils import get_breadcrumbs
from btcopilot.tests.personal.synthetic import PERSONAS

_log = logging.getLogger(__name__)

bp = Blueprint(
    "synthetic",
    __name__,
    url_prefix="/synthetic",
    template_folder="../templates",
)
bp = minimum_role(btcopilot.ROLE_ADMIN)(bp)


@bp.route("/")
def index():
    current_user = auth.current_user()
    breadcrumbs = get_breadcrumbs("synthetic")

    personas = [
        {
            "name": p.name,
            "background": p.background[:200] + "...",
            "traits": [t.value for t in p.traits],
        }
        for p in PERSONAS
    ]

    users = (
        User.query.filter(
            User.roles.contains(btcopilot.ROLE_AUDITOR)
            | User.roles.contains(btcopilot.ROLE_ADMIN)
        )
        .order_by(User.username)
        .all()
    )

    return render_template(
        "synthetic_index.html",
        personas=personas,
        users=users,
        breadcrumbs=breadcrumbs,
        current_user=current_user,
        btcopilot=btcopilot,
    )


@bp.route("/generate", methods=["POST"])
def generate():
    from btcopilot.extensions import celery

    if celery is None:
        return jsonify({"error": "Celery not available - start Redis and Celery worker"}), 503

    current_user = auth.current_user()

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    persona_name = data.get("persona")
    max_turns = data.get("max_turns", 20)
    skip_extraction = data.get("skip_extraction", False)
    username = data.get("username") or current_user.username

    persona = next((p for p in PERSONAS if p.name == persona_name), None)
    if not persona:
        return jsonify({"error": f"Persona not found: {persona_name}"}), 400

    task = celery.send_task(
        "generate_synthetic_discussion",
        args=[persona_name, username, int(max_turns), skip_extraction],
    )

    _log.info(
        f"User {current_user.username} started synthetic generation task {task.id} "
        f"for persona {persona_name}"
    )

    return jsonify({"task_id": task.id})


@bp.route("/task/<task_id>", methods=["GET"])
def task_status(task_id):
    from btcopilot.extensions import celery
    from celery.result import AsyncResult

    if celery is None:
        return jsonify({"status": "error", "error": "Celery not available"}), 503

    result = AsyncResult(task_id, app=celery)

    if result.ready():
        task_result = result.get()
        if task_result.get("success"):
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
        else:
            return jsonify({"status": "error", "error": task_result.get("error")})
    elif result.failed():
        return jsonify({"status": "error", "error": str(result.result)})
    else:
        return jsonify({"status": "pending"})
