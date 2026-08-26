"""FD-336 WP-H1, oracle H3/H4: the /test blueprint is the sandbox's only data
door. Seeding must be repeatable (same payload, same ids, no duplicates), must
back-fill licensing for users that lack it, must round-trip a production export
without renumbering it, and must not exist in a non-test app."""

import base64
import pickle

import PyQt5.sip  # noqa: F401  required for pickling QtCore objects
from flask.testing import FlaskClient

import btcopilot
from btcopilot.app import create_app
from btcopilot.personal.models import Discussion, Speaker, Statement
from btcopilot.pro.models import AccessRight, Diagram, License, Machine, User
from btcopilot.testing.fixtures import LicenseState
from btcopilot.tests.pro.fdencryptiontestclient import FDEncryptionTestClient

OWNER = "harness+owner@example.com"
SHARER = "harness+sharer@example.com"
UNLICENSED = "harness+unlicensed@example.com"

CASE_NAME = "Byron Case"
CASE_REF = f"{OWNER}/{CASE_NAME}"
CASE_PEOPLE = [
    {"id": 1, "name": "Ada", "lastName": "Byron", "gender": "female"},
    {"id": 2, "name": "Bea", "lastName": "Byron", "gender": "female"},
]

FAMILY_PAYLOAD = {
    "users": [
        {
            "username": OWNER,
            "first_name": "Ada",
            "last_name": "Byron",
            "password": "harness",
        },
        {
            "username": SHARER,
            "first_name": "Bea",
            "last_name": "Byron",
            "password": "harness",
        },
    ],
    "diagrams": [
        {
            "user": OWNER,
            "name": CASE_NAME,
            "data": {
                "people": CASE_PEOPLE,
                "events": [],
                "pair_bonds": [],
                "lastItemId": 2,
            },
        }
    ],
    "discussions": [{"user": OWNER, "diagram": CASE_REF, "summary": "intake"}],
    "access_rights": [
        {"diagram": CASE_REF, "user": SHARER, "right": btcopilot.ACCESS_READ_ONLY}
    ],
}

IMPORTED_PEOPLE = [
    {"id": 10, "name": "Imo", "lastName": "Porter", "gender": "female"},
    {"id": 11, "name": "Ray", "lastName": "Porter", "gender": "male"},
]

EXPORT = {
    "user": {
        "id": 7,
        "username": "harness+import@example.com",
        "first_name": "Imo",
        "last_name": "Porter",
    },
    "diagram": {
        "id": 1924,
        "user_id": 7,
        "name": "Imported Case",
        "data_b64": base64.b64encode(
            pickle.dumps(
                {
                    "people": IMPORTED_PEOPLE,
                    "events": [],
                    "pair_bonds": [],
                    "lastItemId": 11,
                }
            )
        ).decode("ascii"),
    },
    "discussions": [
        {
            "id": 55,
            "user_id": 7,
            "diagram_id": 1924,
            "summary": "first session",
            "chat_user_speaker_id": 301,
            "chat_ai_speaker_id": 302,
        },
        {
            "id": 58,
            "user_id": 7,
            "diagram_id": 1924,
            "summary": "second session",
            "chat_user_speaker_id": 307,
            "chat_ai_speaker_id": 308,
        },
    ],
    "speakers": [
        {"id": 301, "discussion_id": 55, "name": "Imo", "type": "subject"},
        {"id": 302, "discussion_id": 55, "name": "Coach", "type": "expert"},
        {"id": 307, "discussion_id": 58, "name": "Imo", "type": "subject"},
        {"id": 308, "discussion_id": 58, "name": "Coach", "type": "expert"},
    ],
    "statements": [
        {
            "id": 900,
            "discussion_id": 55,
            "speaker_id": 301,
            "text": "My mother called again.",
            "order": 1,
        },
        {
            "id": 903,
            "discussion_id": 55,
            "speaker_id": 302,
            "text": "What happened next?",
            "order": 2,
        },
        {
            "id": 911,
            "discussion_id": 58,
            "speaker_id": 307,
            "text": "Ray moved out in March.",
            "order": 1,
        },
    ],
}


def _harness(flask_app) -> FlaskClient:
    flask_app.test_client_class = FlaskClient
    return flask_app.test_client()


def _signed(flask_app, user) -> FDEncryptionTestClient:
    flask_app.test_client_class = FDEncryptionTestClient
    return flask_app.test_client(user=user)


def _seed(flask_app, payload) -> dict:
    response = _harness(flask_app).post("/test/seed", json=payload)
    assert response.status_code == 200, response.data
    return response.get_json()


def _ids_by(entries, key) -> dict:
    return {entry[key]: entry["id"] for entry in entries}


def test_reseeding_the_same_payload_reuses_every_id(flask_app):
    first = _seed(flask_app, FAMILY_PAYLOAD)
    second = _seed(flask_app, FAMILY_PAYLOAD)
    assert _ids_by(second["users"], "username") == _ids_by(first["users"], "username")
    assert _ids_by(second["diagrams"], "name") == _ids_by(first["diagrams"], "name")
    assert _ids_by(second["discussions"], "summary") == _ids_by(
        first["discussions"], "summary"
    )


def test_reseeding_the_same_payload_creates_no_duplicate_rows(flask_app):
    _seed(flask_app, FAMILY_PAYLOAD)
    _seed(flask_app, FAMILY_PAYLOAD)
    assert User.query.filter(User.username.in_([OWNER, SHARER])).count() == 2
    assert Diagram.query.filter_by(name=CASE_NAME).count() == 1
    assert Discussion.query.count() == 1
    assert AccessRight.query.count() == 1


def test_a_user_seeded_without_licenses_is_licensed_on_the_next_seed(flask_app):
    first = _seed(
        flask_app,
        {"users": [{"username": UNLICENSED, "license": LicenseState.None_.value}]},
    )
    user_id = first["users"][0]["id"]
    assert License.query.filter_by(user_id=user_id).count() == 0
    assert Machine.query.filter_by(user_id=user_id).count() == 0

    _seed(flask_app, {"users": [{"username": UNLICENSED}]})
    assert License.query.filter_by(user_id=user_id).count() > 0
    assert Machine.query.filter_by(user_id=user_id).count() == 1


def test_import_preserves_every_non_contiguous_id(flask_app):
    response = _harness(flask_app).post("/test/import", json=EXPORT)
    assert response.status_code == 200, response.data

    assert User.query.get(7).username == EXPORT["user"]["username"]
    assert Diagram.query.get(1924).user_id == 7
    assert sorted(d.id for d in Discussion.query.all()) == [55, 58]
    assert sorted(s.id for s in Speaker.query.all()) == [301, 302, 307, 308]
    assert sorted(s.id for s in Statement.query.all()) == [900, 903, 911]


def test_import_binds_statements_to_their_original_speakers(flask_app):
    _harness(flask_app).post("/test/import", json=EXPORT)
    assert Statement.query.get(900).speaker_id == 301
    assert Statement.query.get(903).speaker_id == 302
    assert Statement.query.get(911).speaker_id == 307


def test_import_back_fills_the_chat_speaker_ids(flask_app):
    _harness(flask_app).post("/test/import", json=EXPORT)

    for discussion_id, subject_id, expert_id in ((55, 301, 302), (58, 307, 308)):
        discussion = Discussion.query.get(discussion_id)
        assert discussion.chat_user_speaker_id == subject_id
        assert discussion.chat_ai_speaker_id == expert_id


def test_import_keeps_the_diagram_blob_intact(flask_app):
    _harness(flask_app).post("/test/import", json=EXPORT)
    assert Diagram.query.get(1924).get_diagram_data().people == IMPORTED_PEOPLE


def test_reset_empties_the_database_and_health_answers_afterwards(flask_app):
    _seed(flask_app, FAMILY_PAYLOAD)
    client = _harness(flask_app)

    assert client.post("/test/reset").status_code == 200
    assert User.query.count() == 0
    assert Diagram.query.count() == 0
    assert Discussion.query.count() == 0

    assert client.get("/test/health").status_code == 200


def test_a_diagram_seeded_from_a_dict_reads_back_over_the_pro_api(flask_app):
    seeded = _seed(flask_app, FAMILY_PAYLOAD)
    diagram_id = _ids_by(seeded["diagrams"], "name")[CASE_NAME]
    owner = User.query.filter_by(username=OWNER).one()

    response = _signed(flask_app, owner).get(f"/v1/diagrams/{diagram_id}")
    assert response.status_code == 200

    blob = pickle.loads(response.data)["data"]
    assert pickle.loads(blob)["people"] == CASE_PEOPLE


def test_the_blueprint_is_absent_from_an_app_that_is_not_under_test(
    flask_app, tmp_path, monkeypatch
):
    assert _harness(flask_app).get("/test/health").status_code == 200

    monkeypatch.delenv("BTCOPILOT_TEST_ROUTES", raising=False)
    production_app = create_app(
        config={
            "ENV": "unittest",
            "CONFIG": "testing",
            "TESTING": False,
            "SECRET_KEY": "test_secret_key",
            "FD_DIR": str(tmp_path),
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "VECTOR_DB_PATH": str(tmp_path / "production_vector_db"),
            "CHROMA_PERSIST_PATH": str(tmp_path / "production_vector_db"),
            "STRIPE_ENABLED": False,
            "SCHEDULER_API_ENABLED": False,
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
        }
    )
    assert production_app.test_client().get("/test/health").status_code == 404
    assert production_app.test_client().post("/test/seed", json={}).status_code == 404


def test_the_blueprint_is_present_when_the_env_flag_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("BTCOPILOT_TEST_ROUTES", "1")
    app = create_app(
        config={
            "ENV": "unittest",
            "CONFIG": "testing",
            "TESTING": False,
            "SECRET_KEY": "test_secret_key",
            "FD_DIR": str(tmp_path),
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "VECTOR_DB_PATH": str(tmp_path / "flagged_vector_db"),
            "CHROMA_PERSIST_PATH": str(tmp_path / "flagged_vector_db"),
            "STRIPE_ENABLED": False,
            "SCHEDULER_API_ENABLED": False,
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
        }
    )
    assert app.test_client().get("/test/health").status_code == 200
