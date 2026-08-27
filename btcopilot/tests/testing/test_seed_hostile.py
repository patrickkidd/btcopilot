"""FD-336 WP-H1, oracle H3: an LLM writing a seed drifts to the happy family, so
the hostile profile enumerates the failure modes deliberately. These tests prove
each enumerated case is present in the database, that the manifest points a
journey at the row it exemplifies, and that the cases with server-visible
consequences actually bite."""

import pickle
import time
from collections import Counter
from datetime import datetime

import PyQt5.sip  # noqa: F401  required for pickling QtCore objects
import pytest
from flask.testing import FlaskClient

import btcopilot
from btcopilot.personal.models import Discussion, Statement
from btcopilot.pro.models import AccessRight, Diagram, License, User
from btcopilot.testing.fixtures import Case
from btcopilot.tests.pro.fdencryptiontestclient import FDEncryptionTestClient

HOSTILE = {"profile": "hostile"}
RANDOM = {"profile": "random:1:12"}

ORACLE_CASES = (
    Case.EmptyName,
    Case.SingleTokenName,
    Case.LastNameOnly,
    Case.UnicodeName,
    Case.LongName,
    Case.DuplicateNames,
    Case.SelfReferentialBond,
    Case.DanglingEventPerson,
    Case.ChildOfTwoBonds,
    Case.StagedDanglingPdp,
    Case.EmptyDiagram,
    Case.HugeDiagram,
    Case.StaleVersion,
    Case.SharedReadOnly,
    Case.SharedReadWrite,
    Case.NoAccess,
    Case.ExpiredLicense,
    Case.NoLicense,
    Case.NoFreeDiagram,
    Case.OrphanDiscussion,
    Case.ForeignDiagramDiscussion,
    Case.EmojiStatement,
    Case.HugeStatement,
)

PERSON_CASES = (
    Case.EmptyName,
    Case.SingleTokenName,
    Case.LastNameOnly,
    Case.UnicodeName,
    Case.LongName,
    Case.ChildOfTwoBonds,
)
STATEMENT_CASES = (Case.EmojiStatement, Case.HugeStatement)

ROW_LOOKUPS = (("user_id", User), ("diagram_id", Diagram), ("discussion_id", Discussion))

HUGE_PEOPLE = 500
HUGE_EVENTS = 2000
HUGE_STATEMENT = 5000
LONG_NAME = 200


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


def _data(entry):
    return Diagram.query.get(entry["diagram_id"]).get_diagram_data()


def _named_people(entry) -> list:
    return [person for person in _data(entry).people if person.get("name")]


def _statements(entry) -> list:
    return Statement.query.filter_by(discussion_id=entry["discussion_id"]).all()


def _owner(diagram_id) -> User:
    return User.query.get(Diagram.query.get(diagram_id).user_id)


def _put(client, diagram_id, blob, expected_version):
    return client.put(
        f"/v1/diagrams/{diagram_id}",
        data=pickle.dumps(
            {
                "data": blob,
                "updated_at": datetime.utcnow(),
                "expected_version": expected_version,
            }
        ),
    )


def _has_no_family_name(person) -> bool:
    return not person.get("lastName") and not person.get("last_name")


def _bonds_claiming(data, person_id) -> set:
    """A child reaches its parents either through Person.parents naming the bond
    or through an offspring event naming the two parents. Two answers = corrupt."""
    bonds = {
        bond["id"]: frozenset((bond.get("person_a"), bond.get("person_b")))
        for bond in data.pair_bonds
    }
    claims = {
        person["parents"]
        for person in data.people
        if person["id"] == person_id and person.get("parents") in bonds
    }
    for event in data.events:
        if event.get("child") != person_id:
            continue
        parents = frozenset((event.get("person"), event.get("spouse")))
        claims.update(bond_id for bond_id, people in bonds.items() if people == parents)
    return claims


@pytest.fixture(autouse=True)
def llm_stub(monkeypatch):
    monkeypatch.setenv("BTCOPILOT_LLM", "stub")


@pytest.fixture
def hostile(flask_app):
    return _seed(flask_app, HOSTILE)["manifest"]


def test_the_manifest_names_every_enumerated_case(hostile):
    assert {case.value for case in ORACLE_CASES} - set(hostile) == set()


def test_every_named_case_resolves_to_a_row(hostile):
    for case in ORACLE_CASES:
        entry = hostile[case.value]
        rows = [
            model.query.get(entry[key])
            for key, model in ROW_LOOKUPS
            if entry.get(key) is not None
        ]
        assert rows and all(row is not None for row in rows), case.value


def test_the_person_and_statement_cases_point_at_the_row_they_exemplify(hostile):
    """A journey selects a case by name and needs the row, not prose. The
    diagram/discussion id alone does not distinguish, e.g., the single-token
    person from the other two single-token people in the same diagram."""
    for case in PERSON_CASES:
        assert "person_id" in hostile[case.value], case.value
    for case in STATEMENT_CASES:
        assert "statement_id" in hostile[case.value], case.value


def test_the_committed_name_shapes_are_each_present(hostile):
    nameless = _data(hostile[Case.EmptyName.value]).people
    assert any(
        not person.get("name") and _has_no_family_name(person) for person in nameless
    )

    single = _named_people(hostile[Case.SingleTokenName.value])
    assert any(
        " " not in person["name"] and _has_no_family_name(person) for person in single
    )

    unicode_named = _named_people(hostile[Case.UnicodeName.value])
    assert any(not person["name"].isascii() for person in unicode_named)

    long_named = _named_people(hostile[Case.LongName.value])
    assert any(len(person["name"]) >= LONG_NAME for person in long_named)


def test_a_last_name_only_person_still_carries_the_pre_migration_key(hostile):
    people = _data(hostile[Case.LastNameOnly.value]).people
    legacy = [
        person
        for person in people
        if person.get("last_name") and "lastName" not in person
    ]
    assert legacy and not any(person.get("name") for person in legacy)


def test_two_people_share_one_name_in_the_duplicate_case(hostile):
    named = [
        (person["name"], person.get("lastName"))
        for person in _named_people(hostile[Case.DuplicateNames.value])
    ]
    assert Counter(named).most_common(1)[0][1] >= 2


def test_a_pair_bond_points_at_itself(hostile):
    bonds = _data(hostile[Case.SelfReferentialBond.value]).pair_bonds
    assert any(
        bond["person_a"] is not None and bond["person_a"] == bond["person_b"]
        for bond in bonds
    )


def test_an_event_points_at_a_person_the_diagram_does_not_have(hostile):
    data = _data(hostile[Case.DanglingEventPerson.value])
    known = {person["id"] for person in data.people}
    assert any(
        event.get("person") is not None and event["person"] not in known
        for event in data.events
    )


def test_one_child_is_claimed_by_two_different_pair_bonds(hostile):
    data = _data(hostile[Case.ChildOfTwoBonds.value])
    assert any(
        len(_bonds_claiming(data, person["id"])) >= 2 for person in data.people
    )


def test_the_staged_pdp_references_people_that_do_not_exist(hostile):
    data = _data(hostile[Case.StagedDanglingPdp.value])
    staged_ids = {person.id for person in data.pdp.people}
    assert any(staged_id < 0 for staged_id in staged_ids)

    known = staged_ids | {person["id"] for person in data.people}
    referenced = {event.person for event in data.pdp.events if event.person is not None}
    referenced |= {
        bond.person_b for bond in data.pdp.pair_bonds if bond.person_b is not None
    }
    assert referenced - known


def test_the_diagram_sizes_bracket_the_usable_range(hostile):
    assert _data(hostile[Case.EmptyDiagram.value]).people == []

    large = _data(hostile[Case.HugeDiagram.value])
    assert len(large.people) >= HUGE_PEOPLE
    assert len(large.events) >= HUGE_EVENTS


def test_the_shared_cases_carry_the_two_kinds_of_access_right(hostile):
    for case, right in (
        (Case.SharedReadOnly, btcopilot.ACCESS_READ_ONLY),
        (Case.SharedReadWrite, btcopilot.ACCESS_READ_WRITE),
    ):
        entry = hostile[case.value]
        granted = AccessRight.query.filter_by(diagram_id=entry["diagram_id"]).one()
        assert granted.right == right
        assert granted.user_id != Diagram.query.get(entry["diagram_id"]).user_id


def test_the_licensing_cases_are_each_present(hostile):
    expired = License.query.filter_by(
        user_id=hostile[Case.ExpiredLicense.value]["user_id"]
    ).all()
    assert expired and not any(row.active for row in expired)

    unlicensed = hostile[Case.NoLicense.value]["user_id"]
    assert License.query.filter_by(user_id=unlicensed).count() == 0

    nofree = User.query.get(hostile[Case.NoFreeDiagram.value]["user_id"])
    assert nofree.free_diagram_id is None


def test_the_hostile_discussions_are_each_present(hostile):
    orphan = Discussion.query.get(hostile[Case.OrphanDiscussion.value]["discussion_id"])
    assert orphan.user_id is None

    foreign = Discussion.query.get(
        hostile[Case.ForeignDiagramDiscussion.value]["discussion_id"]
    )
    assert Diagram.query.get(foreign.diagram_id).user_id != foreign.user_id


def test_the_extreme_statements_are_present(hostile):
    emoji = _statements(hostile[Case.EmojiStatement.value])
    assert any(any(ord(char) > 0xFFFF for char in row.text) for row in emoji)

    huge = _statements(hostile[Case.HugeStatement.value])
    assert any(len(row.text) >= HUGE_STATEMENT for row in huge)


def test_the_unshared_case_is_denied_to_the_user_who_lacks_access(flask_app, hostile):
    entry = hostile[Case.NoAccess.value]
    excluded = User.query.get(entry["user_id"])
    assert not excluded.has_role(btcopilot.ROLE_ADMIN)

    response = _signed(flask_app, excluded).get(f"/v1/diagrams/{entry['diagram_id']}")
    assert response.status_code in (401, 403)


def test_the_stale_version_row_rejects_a_client_holding_an_older_snapshot(
    flask_app, hostile
):
    entry = hostile[Case.StaleVersion.value]
    diagram = Diagram.query.get(entry["diagram_id"])
    client = _signed(flask_app, User.query.get(entry["user_id"]))

    assert entry["client_version"] < entry["stored_version"]
    assert _put(client, diagram.id, diagram.data, entry["client_version"]).status_code == 409
    assert _put(client, diagram.id, diagram.data, entry["stored_version"]).status_code == 200


def test_a_chat_turn_on_the_orphan_discussion_still_answers(flask_app, hostile):
    entry = hostile[Case.OrphanDiscussion.value]

    response = _signed(flask_app, _owner(entry["diagram_id"])).post(
        f"/personal/discussions/{entry['discussion_id']}/statements",
        json={"statement": "My mother called again."},
    )
    assert response.status_code == 200


def test_the_large_diagram_loads_over_the_pro_api_within_the_budget(flask_app, hostile):
    entry = hostile[Case.HugeDiagram.value]
    client = _signed(flask_app, User.query.get(entry["user_id"]))

    started = time.monotonic()
    response = client.get(f"/v1/diagrams/{entry['diagram_id']}")
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert elapsed < 5


def test_the_random_profile_is_reproducible_from_its_seed(flask_app):
    client = _harness(flask_app)
    first = _seed(flask_app, RANDOM)["manifest"]
    first_blob = Diagram.query.get(
        first[Case.RandomFamily.value]["diagram_id"]
    ).data

    client.post("/test/reset")
    again = _seed(flask_app, RANDOM)["manifest"]
    assert again == first
    assert Diagram.query.get(again[Case.RandomFamily.value]["diagram_id"]).data == first_blob

    client.post("/test/reset")
    other = _seed(flask_app, {"profile": "random:2:12"})["manifest"]
    assert other != first
    assert (
        Diagram.query.get(other[Case.RandomFamily.value]["diagram_id"]).data
        != first_blob
    )


def test_the_composed_profile_keeps_every_hostile_case(flask_app):
    manifest = _seed(flask_app, {"profile": "family+hostile"})["manifest"]
    assert {case.value for case in ORACLE_CASES} - set(manifest) == set()
    assert Case.FamilyCase.value in manifest
