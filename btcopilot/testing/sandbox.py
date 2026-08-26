"""One definition of a sandbox process's Flask config, used by the server
launcher and by the celery worker so neither hand-copies the other.

create_app applies the third-party stand-ins itself when TESTING is on, so a
caller needs nothing before or after it beyond this config.
"""

import os
import sys

from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.testing.stubs import MEMORY_BACKEND, MEMORY_BROKER

DB_URI_ENV = "BTCOPILOT_SANDBOX_DB_URI"
FD_DIR_ENV = "BTCOPILOT_SANDBOX_FD_DIR"
BROKER_ENV = "BTCOPILOT_SANDBOX_BROKER"

SANDBOX_SECRET_KEY = "sandbox-secret-key"

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")

UNDER_PYTEST = (
    "create_sandbox_app() under pytest would return an app with real bcrypt, "
    "Stripe, Chroma and mail, because create_app installs the stand-ins only "
    "outside pytest. Spawn the sandbox as a subprocess, or use the flask_app "
    "fixture for an in-process app."
)


def sandbox_config(db_uri: str, fd_dir: str, broker: str | None = None) -> dict:
    return {
        "TESTING": True,
        "CONFIG": "development",
        "SECRET_KEY": SANDBOX_SECRET_KEY,
        "SQLALCHEMY_DATABASE_URI": db_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "FD_DIR": fd_dir,
        "VECTOR_DB_PATH": os.path.join(fd_dir, "vector_db"),
        "CELERY_BROKER_URL": broker or MEMORY_BROKER,
        "CELERY_RESULT_BACKEND": broker or MEMORY_BACKEND,
    }


def create_sandbox_app(db_uri: str, fd_dir: str, broker: str | None = None):
    if "pytest" in sys.modules:
        raise RuntimeError(UNDER_PYTEST)
    app = create_app(config=sandbox_config(db_uri, fd_dir, broker))
    with app.app_context():
        db.create_all()
    return app


def create_sandbox_app_from_env():
    return create_sandbox_app(
        db_uri=os.environ[DB_URI_ENV],
        fd_dir=os.environ[FD_DIR_ENV],
        broker=os.environ.get(BROKER_ENV),
    )
