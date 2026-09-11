import pickle

from btcopilot import diagramjson
from btcopilot.diagrams import migrate_json
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram


def test_converts_once_and_is_idempotent(subscriber):
    pickled = Diagram(user_id=subscriber.user.id, name="Old")
    pickled.data = pickle.dumps({"people": [{"id": 1, "name": "Ada"}]})
    empty = Diagram(user_id=subscriber.user.id, name="Empty", data=b"")
    db.session.add_all([pickled, empty])
    db.session.commit()

    converted, skipped, failed = migrate_json.run()
    assert (converted >= 1, failed) == (True, 0)
    assert skipped >= 1
    assert diagramjson.loads(pickled.data) == {"people": [{"id": 1, "name": "Ada"}]}
    assert diagramjson.is_json(pickled.data)

    converted, _, failed = migrate_json.run()
    assert (converted, failed) == (0, 0)
