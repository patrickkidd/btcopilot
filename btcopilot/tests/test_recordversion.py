"""Every read tells the coach which version of the record it saw, and a change
to something already in the record names that version. If anyone else has
written since, the change is refused and the coach reads again, so no two
writers overwrite each other without knowing. Invented names only."""

import pytest
import sqlalchemy as sa

from btcopilot.extensions import db
from btcopilot.schema import Person, asdict
from btcopilot.toolbox import ToolError, ToolName, Toolbox
from btcopilot.tests.conftest import csrf_token, version


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren")), asdict(Person(id=2, name="Nell"))]
    data.lastItemId = 2
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def rename(tools: Toolbox, person: int, name: str, seen: int):
    return tools.call(
        ToolName.EditPerson.value, {"id": person, "name": name, "version": seen}
    )


def names(diagram) -> dict:
    db.session.expire_all()
    return {p["id"]: p["name"] for p in diagram.get_diagram_data().people}


def test_every_read_ends_with_the_version_it_saw(family):
    # R-0480
    tools = Toolbox(family.id, "t1")
    for tool, args in (
        (ToolName.ReadPeople, {}),
        (ToolName.ReadEvents, {}),
        (ToolName.ReadNotes, {}),
    ):
        text, _ = tools.call(tool.value, args)
        assert text.splitlines()[-1] == f"Record version {version(family)}."


def test_a_change_after_someone_else_wrote_is_refused_until_the_coach_reads_again(
    family,
):
    # R-0480
    coach = Toolbox(family.id, "coach-turn")
    seen = version(family)
    rename(Toolbox(family.id, "someone-else"), 2, "Nella", version(family))

    with pytest.raises(ToolError, match="changed since version"):
        rename(coach, 2, "Nell Hale", seen)
    assert names(family)[2] == "Nella"

    again, _ = coach.call(ToolName.ReadPeople.value, {})
    now = int(again.splitlines()[-1].split()[-1].rstrip("."))
    rename(coach, 2, "Nell Hale", now)
    assert names(family)[2] == "Nell Hale"


def test_the_turns_own_writes_never_make_what_it_read_stale(family):
    # R-0480
    coach = Toolbox(family.id, "coach-turn")
    seen = version(family)
    rename(coach, 1, "Wren Hale", seen)
    rename(coach, 2, "Nell Hale", seen)
    assert names(family) == {1: "Wren Hale", 2: "Nell Hale"}


def test_undoing_its_own_turn_never_makes_what_the_coach_read_stale(family):
    # R-0480
    rename(Toolbox(family.id, "earlier"), 1, "Wren Hale", version(family))
    coach = Toolbox(family.id, "coach-turn")
    seen = version(family)
    coach.call(ToolName.Undo.value, {})
    rename(coach, 2, "Nell Hale", seen)
    assert names(family) == {1: "Wren", 2: "Nell Hale"}


def test_a_write_from_another_process_is_seen_before_a_change(family):
    # R-0480
    coach = Toolbox(family.id, "coach-turn")
    coach.call(ToolName.ReadPeople.value, {})
    seen = version(family)
    with db.engine.begin() as other:
        other.execute(
            sa.text("UPDATE diagrams SET version = version + 1 WHERE id = :id"),
            {"id": family.id},
        )

    with pytest.raises(ToolError, match="changed since version"):
        rename(coach, 2, "Nell Hale", seen)


def test_a_change_must_name_a_version_and_an_addition_need_not(family):
    # R-0480
    coach = Toolbox(family.id, "coach-turn")
    with pytest.raises(ToolError, match="Say which record version"):
        coach.call(ToolName.EditPerson.value, {"id": 1, "name": "Wren Hale"})
    with pytest.raises(ToolError, match="Say which record version"):
        coach.call(ToolName.Remove.value, {"item_kind": "person", "item_id": "2"})

    coach.call(ToolName.EditPerson.value, {"name": "Ash"})
    assert "Ash" in names(family).values()


def test_an_edit_made_by_hand_on_the_page_makes_the_coachs_version_stale(
    web, family
):
    # R-0480
    coach = Toolbox(family.id, "coach-turn")
    coach.call(
        ToolName.EditEvent.value,
        {"kind": "noted", "person": 2, "date": "1990-01-01", "description": "Moved"},
    )
    seen = version(family)
    event_id = family.get_diagram_data().events[-1]["id"]

    response = web.patch(
        f"/app/events/{event_id}",
        json={"description": "Moved to York"},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert response.status_code == 200

    with pytest.raises(ToolError, match="changed since version"):
        coach.call(
            ToolName.EditEvent.value,
            {"id": event_id, "description": "Moved to Leeds for work", "version": seen},
        )
