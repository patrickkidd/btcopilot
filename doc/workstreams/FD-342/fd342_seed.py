"""Load the prod export of diagram 1924 (+ discussions/speakers/statements) into the
FD-342 ephemeral SQLite sandbox, keeping prod ids. Run with the server STOPPED."""
import base64
import json
import sys
from datetime import date, datetime

sys.path.insert(0, "/Users/patrick/theapp/familydiagram/.claude/worktrees/FD-342/mcpserver")
import ephemeral_server  # noqa: E402

db_dir, json_path = sys.argv[1], sys.argv[2]
ephemeral_server._disable_heavy_extensions()
ephemeral_server._mock_passwords()

from btcopilot.app import create_app  # noqa: E402
from btcopilot.extensions import db  # noqa: E402
from btcopilot.pro.models import Diagram, User  # noqa: E402
from btcopilot.personal.models import Discussion, Speaker, Statement  # noqa: E402

app = create_app(
    config={
        "TESTING": True,
        "CONFIG": "development",
        "SECRET_KEY": "ephemeral-test-key",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_dir}/test.db",
        "STRIPE_ENABLED": False,
        "SCHEDULER_API_ENABLED": False,
        "FD_DIR": db_dir,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
    }
)
exp = json.load(open(json_path))


def ts(v):
    return datetime.fromisoformat(v) if v else None


with app.app_context():
    db.create_all()
    u = exp["user"]
    user = User(
        id=u["id"],
        username=u["username"],
        first_name=u["first_name"],
        last_name=u["last_name"],
        status=u["status"],
        active=u["active"],
        roles=u["roles"],
    )
    user.set_password("test")
    db.session.add(user)
    d = exp["diagram"]
    db.session.add(
        Diagram(
            id=d["id"],
            user_id=d["user_id"],
            name=d["name"],
            alias=d["alias"],
            use_real_names=d["use_real_names"],
            version=d["version"],
            data=base64.b64decode(d["data_b64"]),
            created_at=ts(d["created_at"]),
            updated_at=ts(d["updated_at"]),
        )
    )
    db.session.flush()
    user.free_diagram_id = d["id"]
    for r in exp["discussions"]:
        db.session.add(
            Discussion(
                id=r["id"],
                user_id=r["user_id"],
                diagram_id=r["diagram_id"],
                summary=r["summary"],
                last_topic=r["last_topic"],
                status=r["status"],
                extracting=r["extracting"],
                discussion_date=date.fromisoformat(r["discussion_date"]) if r["discussion_date"] else None,
                synthetic=r["synthetic"],
                extracted_through_order=r["extracted_through_order"],
                pending_extracted_through_order=r["pending_extracted_through_order"],
                calibration_report=r["calibration_report"],
                calibration_advice=r["calibration_advice"],
                statement_reviews=r["statement_reviews"],
                created_at=ts(r["created_at"]),
                updated_at=ts(r["updated_at"]),
            )
        )
    db.session.flush()
    for r in exp["speakers"]:
        db.session.add(
            Speaker(
                id=r["id"],
                discussion_id=r["discussion_id"],
                person_id=r["person_id"],
                name=r["name"],
                type=r["type"].lower(),
                created_at=ts(r["created_at"]),
            )
        )
    db.session.flush()
    for r in exp["discussions"]:
        disc = db.session.get(Discussion, r["id"])
        disc.chat_user_speaker_id = r["chat_user_speaker_id"]
        disc.chat_ai_speaker_id = r["chat_ai_speaker_id"]
    for r in exp["statements"]:
        db.session.add(
            Statement(
                id=r["id"],
                text=r["text"],
                discussion_id=r["discussion_id"],
                speaker_id=r["speaker_id"],
                pdp_deltas=r["pdp_deltas"],
                custom_prompts=r["custom_prompts"],
                order=r["order"],
                approved=r["approved"],
                created_at=ts(r["created_at"]),
                updated_at=ts(r["updated_at"]),
            )
        )
    db.session.commit()
    print(
        "seeded: user", user.id, "diagram", d["id"],
        "discussions", Discussion.query.count(), "statements", Statement.query.count(),
    )
