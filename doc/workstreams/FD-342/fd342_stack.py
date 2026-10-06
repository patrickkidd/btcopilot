"""FD-342 sandbox stack: same Flask app as familydiagram's ephemeral_server (SQLite, mocked
passwords, no stripe/mail/chroma) but WITH Celery on a private redis so background jobs
(Rebuild diagram / deep re-extract) run.

  python fd342_stack.py server --port 8889 --db-dir DIR --broker redis://localhost:6390/0
  python -m celery -A fd342_stack:celery worker --pool=solo   (env FD342_DB_DIR, FD342_BROKER)
"""
import argparse
import os
import sys

sys.path.insert(0, "/Users/patrick/theapp/familydiagram/.claude/worktrees/FD-342/mcpserver")
import ephemeral_server  # noqa: E402

import btcopilot.extensions as ext  # noqa: E402

for name in ("init_logging", "init_excepthook", "init_datadog", "init_stripe", "init_chroma", "init_mail"):
    setattr(ext, name, lambda app: None)
ephemeral_server._mock_passwords()

from btcopilot.app import create_app  # noqa: E402
from btcopilot.extensions import db  # noqa: E402


def build(db_dir, broker):
    app = create_app(
        config={
            "TESTING": True,
            "CONFIG": "development",
            "SECRET_KEY": "ephemeral-test-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_dir}/test.db",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "STRIPE_ENABLED": False,
            "SCHEDULER_API_ENABLED": False,
            "FD_DIR": db_dir,
            "WTF_CSRF_CHECK_DEFAULT": False,
            "CELERY_BROKER_URL": broker,
            "CELERY_RESULT_BACKEND": broker,
        }
    )
    ephemeral_server._register_test_routes(app)
    with app.app_context():
        db.create_all()
    return app


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["server"])
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--db-dir", required=True)
    p.add_argument("--broker", required=True)
    a = p.parse_args()
    app = build(a.db_dir, a.broker)
    print(f"READY:{a.port}", flush=True)
    app.run(host="127.0.0.1", port=a.port, debug=False, use_reloader=False, threaded=True)
else:
    app = build(os.environ["FD342_DB_DIR"], os.environ["FD342_BROKER"])
    celery = ext.celery
