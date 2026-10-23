"""A desktop file made into a new diagram from the Diagrams page: the upload
checked in the request, the diagram built by the worker, and its clusters
regrouped under the import's own turn."""

import io
import zipfile

import pytest
from mock import patch

from btcopilot import (
    attachments,
    extensions,
    fdafter,
    fdfile,
    fdimport,
    record,
)
from btcopilot.clusters import sync
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram, ModelCall
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
            folder.writestr(name, data)
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
        {"people": 3, "events": 3, "left_out": 0},
    )
    assert "turn_id" not in body
    assert test_user.current_diagram_id == diagram.id
    assert sorted(p["name"] for p in diagram.get_diagram_data().people) == ["Ada", "Bo", "Cy"]
    assert ModelCall.query.count() == 0
    [change] = Change.query.filter_by(diagram_id=diagram.id).all()
    caught, outbox = landed
    assert caught == [(diagram.id, test_user.id, change.turn_id)]
    assert (attachments.held(change.turn_id), outbox) == (pickled, [])


def test_the_worker_mails_the_record_and_groups_the_clusters(pro, landed, test_user):
    # R-0932, R-0917, R-0902
    upload(pro, dumps(scene(events=[*scene()["events"], shift(23)])))
    caught, outbox = landed
    [(diagram_id, user_id, turn)] = caught
    fdafter.run(diagram_id, user_id, turn)
    assert caught[1:] == [turn]
    [mail] = outbox
    record_text = mail.attachments[0].data.decode()
    assert "Ada Lund (person 1)" in record_text
    assert attachments.held(turn) is None


