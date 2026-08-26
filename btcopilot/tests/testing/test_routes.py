import base64
import copy
import json
import os
import pickle
from pathlib import Path

import pytest

import btcopilot
import btcopilot.extensions as extensions
from btcopilot.app import create_app
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, Statement
from btcopilot.personal.models.speaker import SpeakerType
from btcopilot.pro.models import AccessRight, Diagram, License, Machine, User
from btcopilot.testing import configure_test_app, credentials, sandbox, stubs
from btcopilot.testing.fixtures import Case, LicenseState


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def restore_stubs():
    """configure_test_app() replaces module-level functions for the life of the
    process, which is right for a sandbox server and wrong for a test session."""
    saved = {name: getattr(extensions, name) for name in stubs.NOOP_EXTENSIONS}
    saved["init_celery"] = extensions.init_celery
    passwords = {
        name: getattr(User, name)
        for name in (
            "set_password",
            "check_password",
            "set_reset_password_code",
            "check_reset_password_code",
        )
    }
    yield
    for name, original in saved.items():
        setattr(extensions, name, original)
    for name, original in passwords.items():
        setattr(User, name, original)


EXPORT = {
    "user": {
        "id": 900,
        "username": "imported@test",
        "first_name": "Im",
        "last_name": "Ported",
        "status": "confirmed",
        "active": True,
        "roles": "subscriber",
        "created_at": "2024-01-01T00:00:00",
    },
    "diagram": {
        "id": 1924,
        "user_id": 900,
        "name": "Prod Case",
        "version": 344,
        "use_real_names": False,
        "data_b64": base64.b64encode(pickle.dumps({"people": []})).decode(),
        "created_at": "2024-02-01T00:00:00",
        "updated_at": "2026-02-01T00:00:00",
    },
    "discussions": [
        {
            "id": 55,
            "user_id": 900,
            "diagram_id": 1924,
            "summary": "Prod discussion",
            "status": "ready",
            "extracting": False,
            "synthetic": False,
            "discussion_date": "2026-01-05",
            "chat_user_speaker_id": 70,
            "chat_ai_speaker_id": 71,
            "created_at": "2026-01-05T00:00:00",
        }
    ],
    "speakers": [
        {
            "id": 70,
            "discussion_id": 55,
            "person_id": 3,
            "name": "Client",
            "type": "Subject",
            "created_at": "2026-01-05T00:00:00",
        },
        {
            "id": 71,
            "discussion_id": 55,
            "name": "Coach",
            "type": "expert",
            "created_at": "2026-01-05T00:00:00",
        },
    ],
    "statements": [
        {
            "id": 800,
            "discussion_id": 55,
            "speaker_id": 70,
            "text": "My father died in 2014.",
            "order": 1,
            "approved": False,
            "created_at": "2026-01-05T00:00:01",
        }
    ],
}


def test_health_names_the_loaded_checkout(client):
    health = client.get("/test/health").json
    assert (health["success"], health["status"]) == (True, "ready")
    assert health["btcopilot"] == str(Path(btcopilot.__file__).resolve().parent)
    assert health["llm"] == "real"
    assert set(health["profiles"]) == {"minimal", "family", "hostile", "random"}


def test_health_reports_whether_any_blanked_credential_survived(client, monkeypatch):
    for name in credentials.BLANKED:
        monkeypatch.delenv(name, raising=False)
    assert client.get("/test/health").json["llm_keys"] is False

    for name in (credentials.LLM_KEYS[0], credentials.SERVICE_KEYS[0]):
        monkeypatch.setenv(name, "anything")
        assert client.get("/test/health").json["llm_keys"] is True
        monkeypatch.delenv(name)


def test_blanked_covers_every_credential_the_backend_reads():
    read_at_runtime = {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_EXTRACTION_API_KEY",
        "GOOGLE_GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ASSEMBLYAI_API_KEY",
        "FD_TEST_STRIPE_KEY",
    }
    assert read_at_runtime <= set(credentials.BLANKED)
    assert set(credentials.BLANKED) == set(credentials.LLM_KEYS + credentials.SERVICE_KEYS)
    assert not set(credentials.LLM_KEYS) & set(credentials.SERVICE_KEYS)


def test_an_unknown_profile_names_the_real_ones(client):
    response = client.post("/test/seed", json={"profile": "nosuchprofile"})
    assert response.status_code == 400
    assert "nosuchprofile" in response.json["error"]
    assert "hostile" in response.json["error"]


def test_a_seed_naming_an_unknown_user_fails_loudly(client):
    response = client.post(
        "/test/seed", json={"diagrams": [{"user": "ghost@test", "name": "X"}]}
    )
    assert response.status_code == 400
    assert "ghost@test" in response.json["error"]


def test_seed_family_is_idempotent_on_natural_keys(client):
    first = client.post("/test/seed", json={"profile": "family"}).json
    second = client.post("/test/seed", json={"profile": "family"}).json
    assert first["users"] == second["users"]
    assert first["diagrams"] == second["diagrams"]
    assert first["discussions"] == second["discussions"]
    assert (User.query.count(), Diagram.query.count()) == (1, 2)
    assert (Discussion.query.count(), Statement.query.count()) == (2, 7)


def test_seed_licenses_a_user_that_is_missing_one(client):
    client.post(
        "/test/seed",
        json={"users": [{"username": "u@test", "license": LicenseState.None_.value}]},
    )
    assert Machine.query.count() == 0

    result = client.post("/test/seed", json={"users": [{"username": "u@test"}]}).json
    assert (Machine.query.count(), License.query.count()) == (1, 2)
    assert result["users"][0]["machine_code"] == "test-hardware-uuid"


def test_seeded_apps_come_up_licensed_except_the_hostile_cases(client):
    """The Pro app only counts a license as active when one of its activations
    names a machine whose code is the app's own HARDWARE_UUID, so the account
    the app runs as needs the caller's uuid, not just License rows."""
    result = client.post(
        "/test/seed",
        json={"profile": "family+hostile", "hardware_uuid": "REAL-HARDWARE-UUID"},
    ).json
    primary = User.query.filter_by(username=result["primary_user"]).one()
    assert result["hardware_uuid"] == "REAL-HARDWARE-UUID"

    activated = [
        license
        for license in primary.licenses
        if license.active
        and any(a.machine.code == "REAL-HARDWARE-UUID" for a in license.activations)
    ]
    assert {license.policy.code for license in activated} == {
        btcopilot.LICENSE_PROFESSIONAL_MONTHLY,
        btcopilot.LICENSE_BETA,
    }

    licensed = {row["username"]: row["licensed"] for row in result["users"]}
    assert licensed[primary.username] is True
    assert licensed["hostile+expired@test"] is False
    assert licensed["hostile+nolicense@test"] is False
    assert all(
        state
        for username, state in licensed.items()
        if username not in ("hostile+expired@test", "hostile+nolicense@test")
    )

    expired = User.query.filter_by(username="hostile+expired@test").one()
    assert not any(license.active for license in expired.licenses)
    assert Machine.query.filter_by(user_id=expired.id).count() == 1
    unlicensed = User.query.filter_by(username="hostile+nolicense@test").one()
    assert unlicensed.licenses == []
    assert Machine.query.filter_by(user_id=unlicensed.id).count() == 0


def test_seeding_onto_a_live_sandbox_cannot_hand_over_the_real_uuid(client):
    """Machine.code is globally unique, so a second profile seeded without a
    reset gets a suffixed code and its accounts cannot open the desktop apps.
    The response says so; reset-then-seed is the only correct reseed."""
    first = client.post(
        "/test/seed", json={"profile": "family", "hardware_uuid": "REAL-HARDWARE-UUID"}
    ).json
    assert first["hardware_uuid"] == "REAL-HARDWARE-UUID"

    second = client.post(
        "/test/seed", json={"profile": "minimal", "hardware_uuid": "REAL-HARDWARE-UUID"}
    ).json
    assert second["hardware_uuid"] == "REAL-HARDWARE-UUID:minimal@test"
    assert second["users"][0]["licensed"] is True

    client.post("/test/reset")
    after_reset = client.post(
        "/test/seed", json={"profile": "minimal", "hardware_uuid": "REAL-HARDWARE-UUID"}
    ).json
    assert after_reset["hardware_uuid"] == "REAL-HARDWARE-UUID"


def test_import_licenses_the_account_the_app_runs_as(client):
    export = copy.deepcopy(EXPORT)
    export["hardware_uuid"] = "REAL-HARDWARE-UUID"

    result = client.post("/test/import", json=export).json
    assert result["hardware_uuid"] == "REAL-HARDWARE-UUID"
    assert result["user"]["licensed"] is True

    user = db.session.get(User, 900)
    assert {license.policy.code for license in user.licenses if license.active} == {
        btcopilot.LICENSE_PROFESSIONAL_MONTHLY,
        btcopilot.LICENSE_BETA,
    }
    assert Machine.query.filter_by(user_id=900).one().code == "REAL-HARDWARE-UUID"


def test_seed_expired_license_is_inactive(client):
    client.post(
        "/test/seed",
        json={"users": [{"username": "x@test", "license": LicenseState.Expired.value}]},
    )
    assert [license.active for license in License.query.all()] == [False, False]


def test_seed_hostile_covers_access_rights_and_an_orphan_discussion(client):
    result = client.post("/test/seed", json={"profile": "hostile"}).json
    manifest = result["manifest"]
    assert {right.right for right in AccessRight.query.all()} == {"ro", "rw"}
    orphan = Discussion.query.filter_by(
        id=manifest[Case.OrphanDiscussion.value]["discussion_id"]
    ).one()
    assert orphan.user_id is None
    stale = db.session.get(Diagram, manifest[Case.StaleVersion.value]["diagram_id"])
    assert stale.version > manifest[Case.StaleVersion.value]["client_version"]


def test_person_and_statement_cases_point_at_the_row_they_exemplify(client):
    manifest = client.post("/test/seed", json={"profile": "hostile"}).json["manifest"]
    person_cases = [
        Case.EmptyName,
        Case.SingleTokenName,
        Case.LastNameOnly,
        Case.UnicodeName,
        Case.LongName,
        Case.ChildOfTwoBonds,
    ]
    person_ids = [manifest[case.value]["person_id"] for case in person_cases]
    assert len(set(person_ids)) == len(person_ids)

    people = {
        p["id"]: p
        for p in pickle.loads(
            db.session.get(Diagram, manifest[Case.EmptyName.value]["diagram_id"]).data
        )["people"]
    }
    assert people[manifest[Case.EmptyName.value]["person_id"]]["name"] == ""
    assert "last_name" in people[manifest[Case.LastNameOnly.value]["person_id"]]
    assert len(people[manifest[Case.LongName.value]["person_id"]]["name"]) == 200

    emoji = db.session.get(
        Statement, manifest[Case.EmojiStatement.value]["statement_id"]
    )
    huge = db.session.get(Statement, manifest[Case.HugeStatement.value]["statement_id"])
    assert emoji.id != huge.id
    assert len(huge.text) == 5000
    assert any(ord(character) > 0xFFFF for character in emoji.text)


def test_seed_accepts_the_pre_existing_user_id_payload(client):
    seeded = client.post(
        "/test/seed", json={"users": [{"username": "legacy@test"}]}
    ).json
    user_id = seeded["users"][0]["id"]
    assert seeded["users"][0]["free_diagram_id"]
    assert seeded["primary_user"] == "legacy@test"

    first = client.post(
        "/test/seed", json={"diagrams": [{"user_id": user_id, "data": {}}]}
    ).json
    second = client.post(
        "/test/seed", json={"diagrams": [{"user_id": user_id, "data": {}}]}
    ).json
    assert first["diagrams"][0]["id"] != second["diagrams"][0]["id"]


def test_seed_accepts_a_diagram_as_a_plain_dict_or_pickle_bytes(client):
    client.post("/test/seed", json={"users": [{"username": "d@test"}]})
    result = client.post(
        "/test/seed",
        json={
            "diagrams": [
                {"user": "d@test", "name": "Plain", "data": {"people": [{"id": 1}]}},
                {
                    "user": "d@test",
                    "name": "Pickled",
                    "data_b64": base64.b64encode(
                        pickle.dumps({"people": [{"id": 2}]})
                    ).decode(),
                },
            ]
        },
    ).json
    loaded = [
        pickle.loads(db.session.get(Diagram, d["id"]).data) for d in result["diagrams"]
    ]
    assert loaded == [{"people": [{"id": 1}]}, {"people": [{"id": 2}]}]


def test_import_preserves_ids_and_backfills_chat_speakers(client):
    result = client.post("/test/import", json=EXPORT).json
    assert result["user"]["id"] == 900
    assert result["diagram"] == {"id": 1924, "version": 344}

    discussion = db.session.get(Discussion, 55)
    assert (discussion.chat_user_speaker_id, discussion.chat_ai_speaker_id) == (70, 71)
    assert db.session.get(User, 900).free_diagram_id == 1924
    assert db.session.get(Statement, 800).discussion_id == 55
    assert db.session.get(Speaker, 70).type is SpeakerType.Subject
    assert db.session.get(Speaker, 71).type is SpeakerType.Expert


def test_import_names_the_account_to_authenticate_as(client):
    imported = client.post("/test/import", json=EXPORT).json
    assert imported["primary_user"] == "imported@test"


def test_a_malformed_export_names_the_missing_field(client):
    response = client.post("/test/import", json={"nope": 1})
    assert response.status_code == 400
    assert "user" in response.json["error"]


def test_import_backfills_chat_speakers_from_speaker_type(client):
    export = copy.deepcopy(EXPORT)
    del export["discussions"][0]["chat_user_speaker_id"]
    del export["discussions"][0]["chat_ai_speaker_id"]

    client.post("/test/import", json=export)
    discussion = db.session.get(Discussion, 55)
    assert (discussion.chat_user_speaker_id, discussion.chat_ai_speaker_id) == (70, 71)


def test_import_refuses_statements_whose_discussion_has_no_speakers(client):
    export = copy.deepcopy(EXPORT)
    export["speakers"] = []

    response = client.post("/test/import", json=export)
    assert response.status_code == 400
    assert "55" in response.json["error"]
    assert Statement.query.count() == 0


def test_import_allows_a_discussion_with_neither_speakers_nor_statements(client):
    export = copy.deepcopy(EXPORT)
    export["speakers"] = []
    export["statements"] = []
    del export["discussions"][0]["chat_user_speaker_id"]
    del export["discussions"][0]["chat_ai_speaker_id"]

    assert client.post("/test/import", json=export).status_code == 200
    assert db.session.get(Discussion, 55).chat_user_speaker_id is None


def test_import_is_idempotent(client):
    client.post("/test/import", json=EXPORT)
    client.post("/test/import", json=EXPORT)
    assert (User.query.count(), Diagram.query.count()) == (1, 1)
    assert (Speaker.query.count(), Statement.query.count()) == (2, 1)


def test_diagram_pickle_round_trip_and_version_bump(client):
    seeded = client.post("/test/seed", json={"profile": "minimal"}).json
    diagram_id = seeded["users"][0]["free_diagram_id"]

    payload = pickle.dumps({"people": [{"id": 7, "name": "Zephyrine"}]})
    put = client.put(f"/test/diagrams/{diagram_id}", data=payload)
    assert put.json["version"] == 2
    assert pickle.loads(
        client.get(f"/test/diagrams/{diagram_id}").data
    ) == pickle.loads(payload)


def test_the_shipped_example_payloads_still_load(client):
    """The two file shapes bin/sandbox routes between; a test so the examples
    cannot drift from the endpoints they document."""
    with open(os.path.join(sandbox.EXAMPLES_DIR, "export.json")) as f:
        imported = client.post("/test/import", json=json.load(f)).json
    assert imported["user"]["id"] == 7
    assert imported["diagram"] == {"id": 1924, "version": 344}
    assert db.session.get(Discussion, 55).chat_ai_speaker_id == 302

    with open(os.path.join(sandbox.EXAMPLES_DIR, "seed.json")) as f:
        seeded = client.post("/test/seed", json=json.load(f)).json
    assert seeded["primary_user"] == "spec@test"
    assert len(seeded["diagrams"]) == 1
    assert seeded["access_rights"][0]["right"] == "ro"


def test_create_sandbox_app_refuses_to_half_configure_under_pytest():
    with pytest.raises(RuntimeError, match="flask_app"):
        sandbox.create_sandbox_app(db_uri="sqlite:///:memory:", fd_dir="/tmp")


def test_reset_drops_everything(client):
    client.post("/test/seed", json={"profile": "family"})
    client.post("/test/reset")
    assert (User.query.count(), Diagram.query.count(), Discussion.query.count()) == (
        0,
        0,
        0,
    )


def test_test_routes_refuse_production_config(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(
            config={
                "TESTING": True,
                "CONFIG": "production",
                "SECRET_KEY": "k",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "FD_DIR": str(tmp_path),
            }
        )


def test_a_real_broker_keeps_celery_live(flask_app, restore_stubs):
    assert configure_test_app(flask_app, broker="redis://localhost:6390/0") is True
    assert flask_app.config["CELERY_RESULT_BACKEND"] == "redis://localhost:6390/0"
    assert extensions.init_celery is not stubs._noop


def test_no_broker_keeps_celery_out_of_the_way(flask_app, restore_stubs):
    assert configure_test_app(flask_app, broker=None) is False
    assert flask_app.config["CELERY_BROKER_URL"] == stubs.MEMORY_BROKER
    assert extensions.init_celery is stubs._noop
    assert extensions.init_datadog is stubs._noop
