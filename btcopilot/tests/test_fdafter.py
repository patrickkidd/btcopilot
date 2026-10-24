"""A desktop file made into a new diagram from the Diagrams page: the upload
checked and built in the request, its record mailed by the worker, and its
clusters grouped once the person says who the case is about."""

import io
import json
import statistics
import zipfile

import pytest
from mock import patch

import btcopilot
from btcopilot import (
    diagramjson,
    attachments,
    extensions,
    fdafter,
    fdfile,
    fdimport,
    prompts,
    record,
    recordtext,
)
from btcopilot.clusters import sync
from btcopilot.extensions import db
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.llmutil import Spent, resolve_model
from btcopilot.pricing import cost
from btcopilot.models import User, Author, Change, Diagram, ModelCall
from btcopilot.models.etc import AccessRight
from btcopilot.models.modelcall import Purpose
from btcopilot.schema import DateCertainty, Event, EventKind, ItemKind, Person, asdict
from btcopilot.tests.conftest import csrf_token
from btcopilot.tests.fdfixtures import dumps, scene, shift
from btcopilot.tests.test_pro import pro  # noqa: F401
from btcopilot.tests.test_casereportrewrite import out_of_date, written  # noqa: F401
from btcopilot.tests.test_clustersync import clusters_of, detects
from btcopilot.tests.test_turnhistory import family  # noqa: F401


@pytest.fixture(autouse=True)
def regrouping():
    with patch("btcopilot.clusters.sync", new=sync):
        yield


def imported(diagram: Diagram, people: list[Person], events: list[Event]) -> str:
    turn = fdimport.TURN.format(diagram.id)
    record.apply(
        diagram.id,
        [
            {
                "item_kind": kind.value,
                "item_id": item.id,
                "field": None,
                "after": asdict(item),
            }
            for kind, items in ((ItemKind.Person, people), (ItemKind.Event, events))
            for item in items
        ],
        author=Author.Pro,
        turn_id=turn,
        user_id=diagram.user_id,
    )
    return turn


def shifts(first: int, count: int) -> list[Event]:
    return [
        Event(
            id=first + n,
            kind=EventKind.Shift,
            person=1,
            dateTime=f"1994-0{n + 1}-01",
            dateCertainty=DateCertainty.Certain,
            title=f"Anxious moment {n}",
            description=f"moment {n}",
            anxiety="up",
        )
        for n in range(count)
    ]


def test_an_import_is_regrouped_under_its_turn_and_undone_with_it(test_user):
    # R-0208, R-0076, R-0909, R-0084
    diagram = test_user.free_diagram
    turn = imported(diagram, [Person(id=1, name="Wren")], shifts(10, 4))

    with detects(("The hard spring", [10, 11, 12, 13])):
        regrouped = fdafter.catch_up(diagram.id, turn_id=turn, user_id=test_user.id)
    assert regrouped.change.turn_id == turn
    assert [c["name"] for c in clusters_of(diagram).values()] == ["The hard spring"]

    with detects(("Never asked for", [10, 11, 12])) as detect:
        assert fdafter.catch_up(diagram.id, turn_id=turn, user_id=test_user.id) is None
    detect.assert_not_called()

    record.undo(diagram.id, turn, author=Author.User)
    db.session.expire_all()
    data = diagram.get_diagram_data()
    assert (data.events, data.clusters) == ([], [])


def test_an_import_into_a_diagram_with_a_report_puts_it_out_of_date(written, family):
    # R-0826, R-0827
    imported(family, [Person(id=40, name="Bo")], [])

    assert out_of_date(family)["sentence"] == (
        "Bo was added after the coach wrote this report."
    )


@pytest.fixture
def held():
    store = attachments.MemoryFiles()
    attachments.use(store)
    yield store
    attachments.use(None)


@pytest.fixture
def landed(flask_app, monkeypatch, held):
    """The worker's steps after a file is in, run where the test sees them."""
    caught = []
    monkeypatch.setattr(
        fdafter, "catch_up", lambda *args, **kwargs: caught.append(kwargs["turn_id"])
    )
    monkeypatch.setattr(fdafter, "send", lambda *args: caught.append(args))
    flask_app.config["MAIL_SERVER"] = "localhost"
    with extensions.mail.record_messages() as outbox:
        yield caught, outbox


def upload(client, data: bytes):
    return client.post(
        "/app/diagrams",
        data={"name": "Lund family", "file": (io.BytesIO(data), "diagram.pickle")},
        content_type="multipart/form-data",
        headers={"X-CSRFToken": csrf_token(client)},
    )


def zipped(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as folder:
        for name, data in files.items():
            # a fixed date, so the bytes are the same in every test process
            folder.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data)
    return out.getvalue()


def made() -> Diagram:
    return Diagram.query.filter_by(name="Lund family").one()


def test_anyone_makes_a_diagram_from_a_desktop_file_and_is_no_one_in_it(web, landed, test_user):
    # R-0888, R-0899
    assert upload(web, dumps(scene())).status_code == 201
    [row] = made().access_rights
    assert (row.user_id, row.person_id) == (test_user.id, None)


def test_a_desktop_file_over_20_mb_is_refused_before_it_is_read(pro, landed, monkeypatch):
    # R-0899
    read = []
    monkeypatch.setattr(fdfile, "read", read.append)
    refused = upload(pro, b"x" * (attachments.MAX_BYTES + 1))
    assert (refused.status_code, read) == (413, [])


@pytest.mark.parametrize(
    "data",
    [b"not a diagram", zipped({"Lund.fd/notes.txt": b"hello"})],
    ids=["plain bytes", "zip with no pickle"],
)
def test_a_file_that_is_not_a_family_diagram_is_refused_in_one_sentence(pro, landed, data):
    # R-0899, R-0882
    refused = upload(pro, data)
    assert (refused.status_code, refused.get_data(as_text=True)) == (400, fdafter.NOT_FD)
    assert Diagram.query.filter_by(name="Lund family").count() == 0


def test_a_file_saved_by_a_desktop_too_old_is_refused_with_what_to_do(pro, landed):
    # R-0914, R-0899
    refused = upload(pro, dumps(scene(version="2.0.11")))
    assert refused.status_code == 400
    assert "Open it in Family Diagram and save it" in refused.get_data(as_text=True)


@pytest.mark.parametrize("zip_it", [False, True])
def test_a_file_is_made_in_the_request_as_it_stands_and_opened(
    pro, landed, held, test_user, zip_it
):
    # R-0899, R-0902, R-0882
    pickled = dumps(scene())
    data = zipped({"Lund family.fd/diagram.pickle": pickled}) if zip_it else pickled
    answered = upload(pro, data)
    assert answered.status_code == 201
    diagram = made()
    body = answered.get_json()
    assert (body["id"], body["name"], body["current"], body["imported"]) == (
        diagram.id,
        "Lund family",
        True,
        {
            "people": 3,
            "events": 3,
            "left_out": 0,
            "primary": [3],
            "coding_cost": fdafter.coding_cost(test_user.id, diagram),
        },
    )
    assert "turn_id" not in body
    assert test_user.current_diagram_id == diagram.id
    assert sorted(p["name"] for p in diagram.get_diagram_data().people) == ["Ada", "Bo", "Cy"]
    assert ModelCall.query.count() == 0
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    caught, outbox = landed
    assert caught == [(diagram.id, test_user.id, change.turn_id)]
    assert (attachments.held(change.turn_id), outbox) == (pickled, [])


def test_the_worker_mails_the_record_and_leaves_the_grouping_to_the_subject_pick(pro, landed, test_user):
    # R-0932, R-0902, R-0935
    upload(pro, dumps(scene(events=[*scene()["events"], shift(23)])))
    caught, outbox = landed
    [(diagram_id, user_id, turn)] = caught
    fdafter.run(diagram_id, user_id, turn)
    assert caught[1:] == []
    [mail] = outbox
    record_text = mail.attachments[0].data.decode()
    assert "Ada Lund (person 1)" in record_text
    assert attachments.held(turn) is None




def both_primary() -> dict:
    """A file that marks two people primary, as Patrick's couple timeline does."""
    fd = scene()
    for one in fd["people"][:2]:
        one["primary"] = True
    return fd


def access(client, diagram_id: int, person_id):
    return client.patch(
        f"/app/diagrams/{diagram_id}/access",
        json={"person_id": person_id},
        headers={"X-CSRFToken": csrf_token(client)},
    )


def test_the_import_answers_every_person_the_file_marks_primary(web, landed):
    # R-0888, R-0899, R-0930
    body = upload(web, dumps(both_primary())).get_json()
    assert body["imported"]["primary"] == [3, 4]
    people = made().get_diagram_data().people
    assert not any(p.get("primary") for p in people)


def test_the_importer_says_which_person_they_are_and_can_take_it_back(web, landed, test_user):
    # R-0888, R-0889
    upload(web, dumps(both_primary()))
    diagram = made()
    said = access(web, diagram.id, 3)
    assert (said.status_code, said.get_json()["person_id"]) == (200, 3)
    assert diagram.access_right(test_user).person_id == 3
    cleared = access(web, diagram.id, None)
    assert (cleared.status_code, cleared.get_json()["person_id"]) == (200, None)


def test_a_person_not_in_the_diagram_is_refused(web, landed):
    # R-0888
    upload(web, dumps(scene()))
    refused = access(web, made().id, 99)
    assert (refused.status_code, refused.get_data(as_text=True)) == (
        400,
        "That person is not in this diagram.",
    )


def test_someone_with_no_row_on_a_diagram_cannot_say_who_they_are_in_it(web):
    # R-0888
    other = User(username="bo@example.com")
    db.session.add(other)
    db.session.flush()
    theirs = Diagram(user_id=other.id, name="Theirs", data=diagramjson.dumps({}))
    db.session.add(theirs)
    db.session.commit()
    assert access(web, theirs.id, None).status_code == 404


def test_a_read_only_grantee_cannot_say_who_the_diagram_is_about(web, test_user, monkeypatch):
    # R-0888, R-0889
    other = User(username="bo@example.com")
    db.session.add(other)
    db.session.flush()
    theirs = Diagram(user_id=other.id, name="Theirs", data=diagramjson.dumps({}))
    db.session.add(theirs)
    db.session.flush()
    imported(theirs, [Person(id=3, name="Ann")], [])
    db.session.add(
        AccessRight(diagram_id=theirs.id, user_id=test_user.id, right=btcopilot.ACCESS_READ_ONLY)
    )
    db.session.commit()
    asked = []
    monkeypatch.setattr(fdafter, "regroup", lambda *args: asked.append(args))
    assert access(web, theirs.id, 3).status_code == 404
    db.session.expire_all()
    assert not any(p.get("primary") for p in db.session.get(Diagram, theirs.id).get_diagram_data().people)
    assert asked == []


def test_saying_who_you_are_marks_that_person_the_one_the_diagram_is_about(web, landed):
    # R-0888, R-0889
    upload(web, dumps(both_primary()))
    diagram = made()
    access(web, diagram.id, 3)
    access(web, diagram.id, 4)
    db.session.expire_all()
    marked = [p["id"] for p in made().get_diagram_data().people if p.get("primary")]
    assert marked == [4]


def test_saying_who_you_are_regroups_the_clusters_on_the_worker(web, landed, monkeypatch):
    # R-0935, R-0934
    upload(web, dumps(both_primary()))
    diagram = made()
    asked = []
    monkeypatch.setattr(fdafter, "regroup", lambda *args: asked.append(args))
    access(web, diagram.id, 3)
    [(diagram_id, turn_id, _)] = asked
    assert diagram_id == diagram.id and turn_id


def test_the_page_is_told_whether_to_say_you_or_name_the_person(web, landed):
    # R-0889, R-0935
    upload(web, dumps(both_primary()))
    diagram = made()
    listed = lambda: next(d for d in web.get("/app/diagrams").get_json() if d["id"] == diagram.id)
    timeline = lambda: web.get(f"/app/timeline?diagram_id={diagram.id}").get_json()
    assert (listed()["addressed"], timeline()["addressed"]) == (False, False)
    access(web, diagram.id, 3)
    assert (listed()["addressed"], timeline()["addressed"]) == (True, True)


def test_the_regroup_task_hands_the_queue_nothing_it_cannot_keep(test_user, monkeypatch):
    # R-0935
    monkeypatch.setattr(fdafter, "catch_up", lambda *args, **kwargs: object())
    answer = fdafter.regrouped(test_user.free_diagram_id, turn_id="t1", user_id=test_user.id)
    assert json.dumps(answer) == "null"


def upload_named(client, data: bytes, filename: str):
    return client.post(
        "/app/diagrams",
        data={"name": "Lund family", "file": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        headers={"X-CSRFToken": csrf_token(client)},
    )


def test_a_mac_zip_of_the_package_is_read_by_its_bytes_whatever_its_name(web, landed):
    # R-0882, R-0899
    pickled = dumps(scene())
    data = zipped(
        {
            "Lund family.fd/": b"",
            "__MACOSX/Lund family.fd/._diagram.pickle": b"\x00\x05fork",
            "__MACOSX/Lund family.fd/diagram.pickle": b"\x00\x05fork",
            "Lund family.fd/People/": b"",
            "Lund family.fd/diagram.pickle": pickled,
        }
    )
    for name in ("Lund family.fd", "Lund family.fd.zip"):
        assert upload_named(web, data, name).status_code == 201, name


def test_a_diagram_pickle_is_read_by_its_bytes_whatever_its_name(web, landed):
    # R-0882, R-0899
    assert upload_named(web, dumps(scene()), "anything.fd").status_code == 201
    refused = upload_named(web, b"PK not really", "diagram.pickle")
    assert (refused.status_code, refused.get_data(as_text=True)) == (400, fdafter.NOT_FD)



def calls(user_id: int, turns: int, per_turn: int, model: str) -> list[float]:
    """The ledger of a coach model's recent turns, one row per call."""
    costs = []
    for turn in range(turns):
        for step in range(per_turn):
            spent = round(0.01 * (turn * per_turn + step + 1), 6)
            costs.append(spent)
            db.session.add(
                ModelCall(
                    user_id=user_id,
                    turn_id=f"t{turn}",
                    purpose=Purpose.Coach,
                    model=model,
                    input_tokens=1,
                    output_tokens=1,
                    cache_creation_tokens=0,
                    cache_read_tokens=0,
                    cost_usd=spent,
                    duration_ms=1,
                    tool_calls=0,
                )
            )
    db.session.commit()
    return costs


def with_events(user, uncoded: int, coded: int = 0) -> Diagram:
    """The user's diagram holding `uncoded` noted events and shifts with no
    code, `coded` coded shifts, and a birth, which takes no code."""
    diagram = user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [{"id": 1, "name": "Wren"}]
    data.events = [
        *(
            {"id": 10 + n, "kind": "noted" if n % 2 else "shift", "person": 1, "title": f"Event {n}"}
            for n in range(uncoded)
        ),
        *(
            {"id": 500 + n, "kind": "shift", "person": 1, "anxiety": "up", "title": f"Coded {n}"}
            for n in range(coded)
        ),
        {"id": 999, "kind": "birth", "child": 1},
    ]
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_the_most_a_yes_costs_is_ten_cents_for_each_event_left_to_code(test_user):
    # R-0902, R-0903, R-0936
    diagram = with_events(test_user, uncoded=22, coded=3)
    assert fdafter.uncoded(diagram.get_diagram_data()) == 22
    assert fdafter.coding_cost(test_user.id, diagram)["high"] == 0.35


def test_the_least_a_yes_costs_is_read_from_the_models_own_turns(test_user):
    # R-0902, R-0903
    diagram = with_events(test_user, uncoded=30)
    model = resolve_model(setting.read(SettingKey.CoachModel, test_user.id))
    costs = calls(test_user.id, turns=5, per_turn=5, model=model)
    said = fdafter.coding_cost(test_user.id, diagram)
    assert said == {"low": min(round(statistics.median(costs) * 5, 2), 0.48), "high": 0.48}


def test_the_least_a_yes_costs_is_never_above_the_most(test_user):
    # R-0902, R-0903
    said = fdafter.coding_cost(test_user.id, with_events(test_user, uncoded=1))
    assert said["low"] <= said["high"] == 0.02


def test_the_price_read_cost_counts_what_a_coach_call_writes(test_user):
    # R-0902, R-0903
    diagram = with_events(test_user, uncoded=100)
    model = resolve_model(setting.read(SettingKey.CoachModel, test_user.id))
    words = prompts.get_agent_prompt(
        record=recordtext.outline(diagram.get_diagram_data(), diagram.version, None)
    )
    reading = len(words) // fdafter.CHARS_PER_TOKEN
    unwritten = fdafter.coding_cost(test_user.id, diagram)
    assert unwritten["low"] == round(float(cost(model, Spent(input=reading, output=fdafter.OUTPUT_TOKENS))), 2)
    calls(test_user.id, turns=1, per_turn=3, model="another-model")
    ModelCall.query.update({"output_tokens": 4000})
    db.session.commit()
    written = fdafter.coding_cost(test_user.id, diagram)
    assert written["low"] == round(float(cost(model, Spent(input=reading, output=4000))), 2)
    assert written["low"] > unwritten["low"]
