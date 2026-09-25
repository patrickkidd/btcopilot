"""read_changes then undo, as the coach would, on the editable fixture diagram.
Run by web/tests/visual/sandboxhandundo.spec.ts: handundo.py [undo EVENT_ID]"""
import sys
import uuid

from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.models import Diagram, User
from btcopilot.routes.fixtures import username
from btcopilot.toolbox import Toolbox

app = create_app()
with app.app_context():
    user = User.query.filter_by(username=username("editable")).one()
    diagram = Diagram.query.filter_by(user_id=user.id).order_by(Diagram.id).first()
    box = Toolbox(diagram.id, uuid.uuid4().hex, user_id=user.id)
    text, _ = box.call("read_changes", {"limit": 3})
    print("READ_CHANGES:\n" + text)
    if "undo" in sys.argv:
        text, _ = box.call("undo", {})
        db.session.commit()
        print("UNDO:", text)
        event = next(e for e in diagram.get_diagram_data().events if e["id"] == int(sys.argv[2]))
        print("EVENT_NOW:", event.get("description"))
