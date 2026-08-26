"""The backend's test surface: seed profiles, test-only routes, LLM and
third-party stand-ins. Registered by create_app under TESTING or
BTCOPILOT_TEST_ROUTES=1, never under production config.
"""

import os

from btcopilot.params import truthy
from btcopilot.testing import credentials, fixtures, llmstub, stubs
from btcopilot.testing.credentials import BLANKED, LLM_KEYS, SERVICE_KEYS
from btcopilot.testing.routes import bp
from btcopilot.testing.sandbox import (
    create_sandbox_app,
    create_sandbox_app_from_env,
    sandbox_config,
)
from btcopilot.testing.stubs import configure_test_app

TEST_ROUTES_ENV = "BTCOPILOT_TEST_ROUTES"


def enabled(app) -> bool:
    return bool(app.config.get("TESTING")) or truthy(os.getenv(TEST_ROUTES_ENV, False))


def init_app(app):
    if not enabled(app):
        return
    if app.config.get("CONFIG") == "production":
        raise RuntimeError(
            "btcopilot.testing routes cannot be registered in production"
        )
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    # llmutil's factories are module globals, so the stub is process-wide however
    # it is installed. Reconciling on every app keeps the process honest: an app
    # built without the flag takes the stub back out rather than inheriting it.
    if llmstub.stubbed():
        llmstub.install()
    else:
        llmstub.uninstall()
