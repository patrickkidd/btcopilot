"""Give the sandbox account a Pro license + activation for this machine (idempotent).
Run with the server STOPPED. Args: db_dir."""
import sys

sys.path.insert(0, "/Users/patrick/theapp/familydiagram/.claude/worktrees/FD-342/mcpserver")
import ephemeral_server  # noqa: E402

db_dir = sys.argv[1]
ephemeral_server._disable_heavy_extensions()
ephemeral_server._mock_passwords()

import btcopilot  # noqa: E402
from btcopilot.app import create_app  # noqa: E402
from btcopilot.extensions import db  # noqa: E402
from btcopilot.pro.models import Activation, License, Machine, Policy, User  # noqa: E402
from pkdiagram import util  # noqa: E402

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
with app.app_context():
    user = User.query.filter_by(username="patrick@alaskafamilysystems.com").one()
    if Machine.query.filter_by(user_id=user.id, code=util.HARDWARE_UUID).first():
        print("license already present")
        sys.exit(0)
    machine = Machine(user_id=user.id, name="FD-342 sandbox", code=util.HARDWARE_UUID)
    db.session.add(machine)
    db.session.flush()
    for code, product in [
        (btcopilot.LICENSE_PROFESSIONAL_MONTHLY, btcopilot.LICENSE_PROFESSIONAL),
        (btcopilot.LICENSE_BETA, btcopilot.LICENSE_BETA),
    ]:
        policy = Policy(code=code, product=product, name=f"Sandbox {product}", interval="month",
                        amount=0, maxActivations=10, active=True, public=True)
        db.session.add(policy)
        db.session.flush()
        lic = License(user_id=user.id, policy=policy)
        db.session.add(lic)
        db.session.flush()
        db.session.add(Activation(license_id=lic.id, machine_id=machine.id))
    db.session.commit()
    print("license + activation added for", user.username)
