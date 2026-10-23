"""One live stream per diagram: every write, from any writer in any process,
reaches every page following the diagram."""

import json

from mock import patch

from btcopilot import diagramjson, record, turnlog
from btcopilot.clusters import sync
from btcopilot.extensions import db
from btcopilot.models import Author, Diagram, User
from btcopilot.schema import ItemKind
from btcopilot.tests.test_clustersync import detects
from btcopilot.tests.test_fdafter import imported, shifts
from btcopilot.schema import Person
from btcopilot.toolbox import ToolName, Toolbox


def written(diagram_id: int) -> list[dict]:
    return [event for _, event in turnlog.read_from(turnlog.diagram_log(diagram_id), 0)]


def frames(response, count: int) -> list[tuple[str, dict]]:
    """The first `count` events the stream sends, with their ids."""
    found, buffer = [], ""
    for chunk in response.response:
        buffer += chunk.decode() if isinstance(chunk, bytes) else chunk
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            lines = dict(line.split(": ", 1) for line in frame.split("\n") if ": " in line)
            if "data" in lines:
                found.append((lines.get("id"), json.loads(lines["data"])))
        if len(found) >= count:
            response.close()
            return found
    return found


def person(diagram: Diagram, person_id: int, name: str, author=Author.User) -> None:
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person.value, "item_id": person_id, "field": "name", "after": name}],
        author=author,
        turn_id=f"t{person_id}",
    )


def test_the_workers_cluster_grouping_reaches_the_diagrams_stream(test_user):
    # R-0933, R-0208
    diagram = test_user.free_diagram
    turn = imported(diagram, [Person(id=1, name="Wren")], shifts(10, 4))
    with patch("btcopilot.clusters.sync", new=sync), detects(("The hard spring", [10, 11, 12, 13])):
        sync(diagram.id, turn_id=turn, user_id=test_user.id)
    kinds = [{d["item_kind"] for d in e["deltas"]} for e in written(diagram.id)]
    assert {ItemKind.Cluster.value} <= kinds[-1]
    assert written(diagram.id)[-1]["type"] == "record_patch"


def test_a_coach_tool_write_reaches_the_diagrams_stream(test_user):
    # R-0933, R-0084
    diagram = test_user.free_diagram
    Toolbox(diagram.id, "c1").call(ToolName.EditPerson.value, {"name": "Bo", "gender": "male"})
    [told] = written(diagram.id)
    assert (told["author"], told["turn_id"]) == ("coach", "c1")
    assert any(d.get("after") == "Bo" or (d.get("after") or {}).get("name") == "Bo" for d in told["deltas"])


def test_a_page_coming_back_is_given_every_write_since_its_place(web, test_user):
    # R-0933
    diagram = test_user.free_diagram
    for n, name in enumerate(("Ada", "Bea", "Cal"), 10):
        person(diagram, n, name)
    log = turnlog.diagram_log(diagram.id)
    epoch = turnlog.epoch(log)
    response = web.get(
        f"/app/diagrams/{diagram.id}/events",
        headers={"Last-Event-ID": f"{epoch}-1"},
        buffered=False,
    )
    sent = frames(response, 2)
    assert [event_id for event_id, _ in sent] == [f"{epoch}-2", f"{epoch}-3"]
    assert [e["turn_id"] for _, e in sent] == ["t11", "t12"]


def test_a_place_the_log_no_longer_holds_tells_the_page_to_read_the_diagram_again(web, test_user):
    # R-0933
    diagram = test_user.free_diagram
    person(diagram, 10, "Ada")
    log = turnlog.diagram_log(diagram.id)
    response = web.get(
        f"/app/diagrams/{diagram.id}/events",
        headers={"Last-Event-ID": "lapsed-40"},
        buffered=False,
    )
    [(event_id, event)] = frames(response, 1)
    assert (event_id, event) == (f"{turnlog.epoch(log)}-1", {"type": "reload"})


def test_someone_who_cannot_open_the_diagram_is_not_told_its_writes(web):
    # R-0933, R-0888
    other = User(username="bo@example.com")
    db.session.add(other)
    db.session.flush()
    theirs = Diagram(user_id=other.id, name="Theirs", data=diagramjson.dumps({}))
    db.session.add(theirs)
    db.session.commit()
    assert web.get(f"/app/diagrams/{theirs.id}/events").status_code == 404
