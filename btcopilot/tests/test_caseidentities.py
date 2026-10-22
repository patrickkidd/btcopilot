"""Who each user is on a case (FD-387): every user on a diagram has a row, the
owner included, naming the person in the diagram they are, or no one for a
human coach consulting on someone else's family. The coach answers a human
coach as a consultant, never as the client.

Invented names only.
"""

import datetime
import pickle
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from PyQt5.QtCore import QDateTime

import btcopilot
from btcopilot import casereport, diagramjson, profile, recordtext
from btcopilot.admin import admin, skill
from btcopilot.admin.database import config
from btcopilot.discussions import SITTING_GAP, chats, open_session, sync_chat_speakers
from btcopilot.extensions import db
from btcopilot.models import AccessRight, Diagram, Speaker, SpeakerType, Statement
from btcopilot.routes.diagrams import diagrams_payload, readable
from btcopilot.schema import EventKind, Person, VariableShift, asdict
from btcopilot.tests.conftest import Model, calling, csrf_token, said, wrote
from btcopilot.tests.test_casereportrewrite import (
    guessed,
    refusals,
    rewrite,
    texts,
    written,
)  # noqa: F401
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolName, Toolbox, said_on

MIGRATION = next(
    Path(btcopilot.__file__).parent.glob("migrations/versions/1b00000000c5_*.py")
)
WREN = {"id": 1, "name": "Wren", "last_name": "Hale", "primary": True}
PLACEHOLDER = {"id": 1, "name": "User", "primary": True}
BORN = {"id": 9, "kind": EventKind.Birth.value, "child": 1, "dateTime": "1980-03-02"}
NOTE = "NOTE-REGISTER-SENTINEL"
CRISIS = "CRISIS-SENTINEL"
BACK = "BACK-SENTINEL"


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )
    monkeypatch.setattr("btcopilot.coachturn.note_register", lambda: NOTE)
    monkeypatch.setattr("btcopilot.coachturn.crisis", lambda *a, **k: CRISIS)
    monkeypatch.setattr("btcopilot.coachturn.back", lambda *a, **k: BACK)


def case(owner, people=(WREN,), events=(BORN,)) -> Diagram:
    diagram = Diagram(
        user_id=owner.id,
        name="The Hales",
        data=diagramjson.dumps(
            {"people": list(people), "events": list(events), "lastItemId": 9}
        ),
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


def rows(diagram) -> list[tuple]:
    return sorted(
        (r.user_id, r.right, r.person_id)
        for r in AccessRight.query.filter_by(diagram_id=diagram.id)
    )


def turn(web, monkeypatch, diagram, statement="My sister is Nell.") -> str:
    """What the coach was told for one turn on the diagram: system and the
    new message's head."""
    model = Model(said("Tell me more."))
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    web.user.current_diagram_id = diagram.id
    db.session.commit()
    response = web.post(
        f"/app/chat?diagram_id={diagram.id}",
        json={"statement": statement},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert response.status_code == 202, response.get_data(as_text=True)
    return model.systems[0]


@pytest.fixture
def coached(test_user, test_user_2):
    """test_user_2's family, with test_user on it as a human coach."""
    diagram = case(test_user_2)
    diagram.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    return diagram


# 1. one column, every user a row, the owner included


def test_a_new_diagram_has_its_owners_row_on_the_primary_person(test_user):
    # R-PENDING-387-1
    named = case(test_user)
    empty = case(test_user, people=(), events=())
    assert rows(named) == [(test_user.id, btcopilot.ACCESS_READ_WRITE, 1)]
    assert rows(empty) == [(test_user.id, btcopilot.ACCESS_READ_WRITE, None)]


def test_a_diagram_made_with_its_owners_row_keeps_just_that_one(test_user):
    # R-PENDING-387-1
    diagram = Diagram(
        user_id=test_user.id,
        name="The Hales",
        data=diagramjson.dumps({"people": [WREN]}),
        access_rights=[
            AccessRight(user_id=test_user.id, right=btcopilot.ACCESS_READ_ONLY)
        ],
    )
    db.session.add(diagram)
    db.session.commit()
    assert rows(diagram) == [(test_user.id, btcopilot.ACCESS_READ_ONLY, 1)]


def test_granting_again_keeps_the_person_unless_told(test_user, test_user_2):
    # R-PENDING-387-1
    diagram = case(test_user)
    diagram.grant_access(test_user_2, btcopilot.ACCESS_READ_WRITE, person_id=1)
    diagram.grant_access(test_user_2, btcopilot.ACCESS_READ_ONLY)
    db.session.commit()
    assert (test_user_2.id, btcopilot.ACCESS_READ_ONLY, 1) in rows(diagram)
    diagram.grant_access(test_user_2, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    assert (test_user_2.id, btcopilot.ACCESS_READ_WRITE, None) in rows(diagram)
    assert len(rows(diagram)) == 2


def test_a_deleted_diagram_takes_its_rows(test_user, test_user_2):
    # R-PENDING-387-1
    diagram = case(test_user)
    diagram.grant_access(test_user_2, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    db.session.delete(diagram)
    db.session.commit()
    assert AccessRight.query.filter_by(diagram_id=diagram.id).count() == 0


def seeded(flask_app, tmp_path) -> sa.Engine:
    """A database at the head before this migration, holding a JSON diagram
    with a primary person, a pickled Pro diagram with one, an empty one and
    one whose owner already has a row."""
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'old.db'}"
    engine = sa.create_engine(flask_app.config["SQLALCHEMY_DATABASE_URI"])
    at = datetime.datetime(2026, 1, 1)
    pro = pickle.dumps(
        {
            "people": [
                {"id": 4, "name": "Ash", "birthDateTime": QDateTime(1950, 1, 1, 0, 0)},
                {"id": 5, "name": "Ivy", "primary": True, "kind": VariableShift.Up},
            ],
            "events": [],
        }
    )
    with flask_app.app_context():
        command.upgrade(config(), "1b00000000c4")
        with engine.begin() as conn:
            meta = sa.MetaData()
            meta.reflect(conn, only=["users", "diagrams", "access_rights"])
            users, diagrams, rights = (
                meta.tables[t] for t in ("users", "diagrams", "access_rights")
            )
            conn.execute(
                users.insert(),
                [
                    {
                        "id": i,
                        "username": f"u{i}@example.com",
                        "status": "confirmed",
                        "created_at": at,
                    }
                    for i in (1, 2)
                ],
            )
            conn.execute(
                diagrams.insert(),
                [
                    {
                        "id": 1,
                        "user_id": 1,
                        "created_at": at,
                        "version": 1,
                        "data": diagramjson.dumps(
                            {"people": [{"id": 3, "primary": True}]}
                        ),
                    },
                    {
                        "id": 2,
                        "user_id": 1,
                        "created_at": at,
                        "version": 1,
                        "data": pro,
                    },
                    {
                        "id": 3,
                        "user_id": 2,
                        "created_at": at,
                        "version": 1,
                        "data": diagramjson.dumps({}),
                    },
                    {
                        "id": 4,
                        "user_id": 2,
                        "created_at": at,
                        "version": 1,
                        "data": diagramjson.dumps(
                            {"people": [{"id": 7, "primary": True}]}
                        ),
                    },
                ],
            )
            conn.execute(
                rights.insert(),
                [
                    {
                        "id": 1,
                        "diagram_id": 4,
                        "user_id": 2,
                        "right": "rw",
                        "created_at": at,
                    },
                    {
                        "id": 2,
                        "diagram_id": 4,
                        "user_id": 1,
                        "right": "ro",
                        "created_at": at,
                    },
                ],
            )
    return engine


def test_the_migration_gives_each_diagram_one_owner_row_on_its_primary_person(
    flask_app, tmp_path
):
    # R-PENDING-387-1
    engine = seeded(flask_app, tmp_path)
    with flask_app.app_context():
        command.upgrade(config(), "head")
    with engine.connect() as conn:
        found = conn.execute(
            sa.text(
                'SELECT diagram_id, user_id, "right", person_id FROM access_rights '
                "ORDER BY diagram_id, user_id"
            )
        ).all()
    assert [tuple(r) for r in found] == [
        (1, 1, "rw", 3),
        (2, 1, "rw", 5),
        (3, 2, "rw", None),
        (4, 1, "ro", None),
        (4, 2, "rw", 7),
    ]


def test_the_migration_reads_the_blob_without_the_app():
    # R-PENDING-387-1
    source = MIGRATION.read_text()
    assert not re.search(r"^\s*(from|import) (btcopilot|PyQt5)", source, re.M)


# 2. voice follows the row


def test_the_owner_alone_on_their_diagram_is_spoken_to_as_before(
    web, monkeypatch, test_user
):
    # R-PENDING-387-2
    diagram = case(test_user)
    told = turn(web, monkeypatch, diagram, "Honestly I just want to die.")
    (marked,) = [line for line in told.splitlines() if recordtext.SPEAKER in line]
    assert marked.startswith("1 Wren Hale")
    assert NOTE not in told
    assert CRISIS in told


def test_a_human_coach_gets_the_consultant_voice_in_a_chat_and_no_one_is_marked(
    web, monkeypatch, coached
):
    # R-PENDING-387-2
    told = turn(web, monkeypatch, coached)
    assert NOTE in told
    assert recordtext.SPEAKER not in told


def test_a_human_coach_is_asked_for_the_clients_entry_in_the_clients_name(
    web, monkeypatch, test_user, test_user_2
):
    # R-PENDING-387-2
    diagram = case(test_user_2, people=(PLACEHOLDER,), events=())
    diagram.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    told = turn(web, monkeypatch, diagram)
    assert "The client's own entry in the diagram (person 1) is still missing" in told
    assert "This person's own entry" not in told


def test_the_owner_is_asked_for_their_own_entry_as_before(web, monkeypatch, test_user):
    # R-PENDING-387-2
    told = turn(web, monkeypatch, case(test_user, people=(PLACEHOLDER,), events=()))
    assert "This person's own entry in the record (person 1) is still missing" in told
    assert "The client's own entry" not in told


def test_the_crisis_check_runs_only_for_the_person_the_family_belongs_to(
    web, monkeypatch, coached
):
    # R-PENDING-387-2
    told = turn(web, monkeypatch, coached, "Honestly I just want to die.")
    assert CRISIS not in told


def test_a_human_coachs_account_never_takes_the_clients_name(
    web, monkeypatch, coached, test_user
):
    # R-PENDING-387-2
    before = (test_user.first_name, test_user.last_name, test_user.birthdate)
    turn(web, monkeypatch, coached)
    db.session.refresh(test_user)
    assert (test_user.first_name, test_user.last_name, test_user.birthdate) == before


def test_the_owner_on_their_diagram_still_gets_their_name_from_it(
    web, monkeypatch, test_user
):
    # R-PENDING-387-2
    turn(web, monkeypatch, case(test_user))
    db.session.refresh(test_user)
    assert (test_user.first_name, test_user.last_name) == ("Wren", "Hale")


def aged(user, diagram):
    """Words of the user's on the diagram from two sitting gaps ago."""
    old = open_session(user, diagram)
    db.session.add(
        Statement(
            discussion_id=old.id,
            speaker_id=old.chat_user_speaker_id,
            text="Hello.",
            created_at=datetime.datetime.utcnow() - 2 * SITTING_GAP,
        )
    )
    db.session.commit()


def test_the_welcome_back_is_only_for_the_person_the_family_belongs_to(
    web, monkeypatch, test_user, coached
):
    # R-PENDING-387-2
    aged(test_user, coached)
    assert BACK not in turn(web, monkeypatch, coached)
    own = case(test_user)
    aged(test_user, own)
    assert BACK in turn(web, monkeypatch, own)


def test_a_session_made_for_a_human_coach_speaks_as_no_one_in_the_family(
    test_user, coached
):
    # R-PENDING-387-2
    session = open_session(test_user, coached)
    sync_chat_speakers(session)
    db.session.commit()
    speaker = Speaker.query.filter_by(
        discussion_id=session.id, type=SpeakerType.Subject
    ).one()
    assert speaker.person_id is None
    assert speaker.name == (test_user.full_name().strip() or test_user.username)


def test_a_session_made_for_the_owner_speaks_as_the_primary_person(test_user):
    # R-PENDING-387-2
    diagram = case(test_user, people=({"id": 6, "name": "Wren", "primary": True},))
    session = open_session(test_user, diagram)
    speaker = Speaker.query.filter_by(
        discussion_id=session.id, type=SpeakerType.Subject
    ).one()
    assert (speaker.person_id, speaker.name) == (6, "Wren")


def test_the_owners_empty_row_names_the_person_the_chat_app_makes(test_user):
    # R-PENDING-387-2
    diagram = case(test_user, people=(), events=())
    sync_chat_speakers(open_session(test_user, diagram))
    db.session.commit()
    assert rows(diagram) == [(test_user.id, btcopilot.ACCESS_READ_WRITE, 1)]


# 6. a single-user diagram behaves as before


def test_the_owners_own_row_never_lists_their_diagram_twice(test_user):
    # R-PENDING-387-6
    case(test_user)
    ids = [d.id for d in readable(test_user)]
    assert len(ids) == len(set(ids))
    listed = [d["id"] for d in diagrams_payload(test_user)]
    assert len(listed) == len(set(listed))


# 3. the coach answering a human coach reads the diagram, never another's chat


def test_a_second_user_on_a_case_sees_and_searches_none_of_the_first_users_words(
    test_user, test_user_2, coached
):
    # R-PENDING-387-3
    owners = open_session(test_user_2, coached)
    db.session.add(
        Statement(
            discussion_id=owners.id,
            speaker_id=owners.chat_user_speaker_id,
            text="Mum moved to the coast in 1990.",
            created_at=datetime.datetime(2026, 1, 5, 10),
        )
    )
    mine = open_session(test_user, coached)
    asking = Statement(
        discussion_id=mine.id,
        speaker_id=mine.chat_user_speaker_id,
        text="What was said about the coast?",
        created_at=datetime.datetime(2027, 1, 1),
    )
    db.session.add(asking)
    db.session.commit()

    assert [d.id for d in chats(test_user, coached.id)] == [mine.id]
    assert [s.text for s in said_on(coached.id, test_user.id)] == [asking.text]
    found, _ = Toolbox(coached.id, "t9", user_id=test_user.id, said=asking).call(
        ToolName.SearchChat.value, {"words": "coast"}
    )
    assert "Mum moved" not in found
    later = Statement(
        discussion_id=owners.id,
        speaker_id=owners.chat_user_speaker_id,
        text="What did I say?",
        created_at=datetime.datetime(2027, 1, 2),
    )
    db.session.add(later)
    db.session.commit()
    theirs, _ = Toolbox(coached.id, "t8", user_id=test_user_2.id, said=later).call(
        ToolName.SearchChat.value, {"words": "coast"}
    )
    assert "Mum moved to the coast in 1990." in theirs


# 4. the case report: "you" only when someone on the case is the person


def test_the_case_report_is_written_to_the_person_only_when_one_on_the_case_is_them(
    test_user, test_user_2, coached
):
    # R-PENDING-387-4
    data = coached.get_diagram_data()
    assert profile.addressed(coached, data)
    coached.grant_access(test_user_2, btcopilot.ACCESS_READ_WRITE, person_id=2)
    db.session.commit()
    assert not profile.addressed(coached, data)
    assert profile.addressed(case(test_user), data)


def test_a_case_written_about_the_person_is_not_refused_for_their_voice():
    # R-PENDING-387-4
    call = SimpleNamespace(
        args={
            "text": "The app's guess: I left home in 1998.",
            "case_report_card": "coach_guess",
        }
    )
    assert "speaks as the person" in casereport.misspoken(call)
    assert casereport.misspoken(call, addressed=False) is None
    named = SimpleNamespace(
        args={"text": "Ivy said her mother left.", "case_report_card": "coach_guess"}
    )
    assert casereport.unmarked(named) is not None
    assert casereport.unmarked(named, addressed=False) is None


def test_a_rewrite_about_the_person_asks_for_cards_by_their_name(
    web, past, written, family, test_user
):
    # R-PENDING-387-4
    family.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, person_id=2)
    db.session.commit()
    model = Model(
        calling(guessed("The app's guess: I remember my mother was ill that winter.")),
        calling(),
    )
    rewrite(web, model)

    asked = model.histories[0][0]["content"]
    assert casereport.ABOUT.format(name="Wren") in asked
    assert not refusals(refusal="speaks as the person")
    assert (
        texts(family)["coach_guess"]
        == "The app's guess: I remember my mother was ill that winter."
    )


def test_a_rewrite_for_the_person_still_refuses_their_voice(web, past, written, family):
    # R-PENDING-387-4
    model = Model(
        calling(guessed("I remember my mother was ill that winter.")),
        calling(guessed('You said "I remember my mother was ill" that winter.')),
    )
    rewrite(web, model)

    assert casereport.ABOUT.split(":")[0] not in model.histories[0][0]["content"]
    assert refusals(refusal="speaks as the person")


# 5. the admin command


def test_admin_puts_a_human_coach_on_a_case_and_takes_them_off(
    flask_app, test_user, test_user_2
):
    # R-PENDING-387-5
    diagram = case(test_user_2)
    runner = flask_app.test_cli_runner()
    email = test_user.username

    added = runner.invoke(
        admin, ["diagrams", "add-user", str(diagram.id), email, "--json"]
    )
    assert added.exit_code == 0, added.output
    assert (test_user.id, btcopilot.ACCESS_READ_WRITE, None) in rows(diagram)
    assert (test_user_2.id, btcopilot.ACCESS_READ_WRITE, 1) in rows(diagram)

    again = runner.invoke(
        admin, ["diagrams", "add-user", str(diagram.id), email, "--person", "1"]
    )
    assert again.exit_code == 0, again.output
    assert (test_user.id, btcopilot.ACCESS_READ_WRITE, 1) in rows(diagram)
    assert len(rows(diagram)) == 2

    gone = runner.invoke(admin, ["diagrams", "remove-user", str(diagram.id), email])
    assert gone.exit_code == 0, gone.output
    assert rows(diagram) == [(test_user_2.id, btcopilot.ACCESS_READ_WRITE, 1)]


def test_admin_refuses_a_person_not_in_the_diagram_and_never_removes_the_owner(
    flask_app, test_user, test_user_2
):
    # R-PENDING-387-5
    diagram = case(test_user_2)
    runner = flask_app.test_cli_runner()
    stray = runner.invoke(
        admin,
        ["diagrams", "add-user", str(diagram.id), test_user.username, "--person", "42"],
    )
    assert stray.exit_code != 0
    assert "no person 42" in stray.output
    owner = runner.invoke(
        admin, ["diagrams", "remove-user", str(diagram.id), test_user_2.username]
    )
    assert owner.exit_code != 0
    assert rows(diagram) == [(test_user_2.id, btcopilot.ACCESS_READ_WRITE, 1)]


def test_the_admin_skill_file_names_the_new_commands():
    # R-PENDING-387-5
    assert skill.PATH.read_text() == skill.render(admin)
    assert "flask admin diagrams add-user" in skill.PATH.read_text()
