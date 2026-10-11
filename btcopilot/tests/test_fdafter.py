"""After a desktop file is written into a diagram, its clusters are regrouped
under the import's own turn, and the case report is out of date by the change
the import wrote."""

import pytest
from mock import patch

from btcopilot import fdafter, fdimport, record
from btcopilot.clusters import sync
from btcopilot.extensions import db
from btcopilot.models import Author, Diagram
from btcopilot.schema import DateCertainty, Event, EventKind, ItemKind, Person, asdict
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
    # R-0208, R-0076, R-0850
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
    # R-0825, R-0827
    imported(family, [Person(id=40, name="Bo")], [])

    assert out_of_date(family)["sentence"] == (
        "Bo was added after the coach wrote this report."
    )
