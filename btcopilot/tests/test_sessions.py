"""The chat route, the user's words in and one coach turn out, and the list
of sessions."""

import btcopilot
from btcopilot import diagramjson
from btcopilot.discussions import (
    all_sessions,
    listed,
    newest,
    open_session,
    session_payload,
)
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, Statement


def said(diagram, user, text: str) -> Discussion:
    session = open_session(user, diagram)
    db.session.add(
        Statement(
            discussion_id=session.id, speaker_id=session.chat_user_speaker_id, text=text
        )
    )
    db.session.commit()
    return session


def test_no_chat_route_takes_a_mode(flask_app):
    # R-0015
    rules = [r.rule for r in flask_app.url_map.iter_rules() if r.rule.startswith("/app/chat")]
    assert rules == ["/app/chat"]
    assert [r for r in flask_app.url_map.iter_rules() if "mode" in r.rule] == []


def test_an_admin_finds_a_session_on_any_family_by_what_was_said(
    web, test_user, test_user_2
):
    # R-0267
    web.user.roles = btcopilot.ROLE_ADMIN
    theirs = Diagram(
        user_id=test_user_2.id, name="The Other Family", data=diagramjson.dumps({})
    )
    db.session.add(theirs)
    db.session.flush()
    mine = said(test_user.free_diagram, test_user, "We went to the lake.")
    other = said(theirs, test_user_2, "My brother [[event:4|lost his job]].")

    listed = web.get("/app/sessions?all=true").get_json()
    assert {(s["id"], s["diagram_id"], s["family"]) for s in listed} == {
        (mine.id, test_user.free_diagram.id, test_user.free_diagram.name),
        (other.id, theirs.id, "The Other Family"),
    }
    found = web.get("/app/sessions?all=true&words=job").get_json()
    assert [(s["id"], s["match"]) for s in found] == [
        (other.id, "My brother lost his job.")
    ]


def test_a_list_of_sessions_reads_each_row_as_the_session_itself_does(test_user):
    # R-0267
    quiet = open_session(test_user, test_user.free_diagram)
    told = open_session(test_user, test_user.free_diagram)
    for speaker, text in [
        (told.chat_ai_speaker_id, "Hello."),
        (told.chat_user_speaker_id, "We went to the lake."),
        (told.chat_user_speaker_id, "x" * 200),
    ]:
        db.session.add(Statement(discussion_id=told.id, speaker_id=speaker, text=text))
    db.session.commit()
    rows = listed(all_sessions())
    assert rows == [session_payload(d) for d in newest(all_sessions())]
    assert [(r["id"], r["message_count"], r["preview"]) for r in rows] == [
        (told.id, 3, "We went to the lake."),
        (quiet.id, 0, None),
    ]


def test_the_list_of_every_familys_sessions_leaves_out_scratch_copies(web, test_user):
    # R-0267
    web.user.roles = btcopilot.ROLE_ADMIN
    copy = Diagram(
        user_id=test_user.id, name="Replay", data=diagramjson.dumps({}), scratch=True
    )
    db.session.add(copy)
    db.session.flush()
    real = said(test_user.free_diagram, test_user, "We went to the lake.")
    said(copy, test_user, "A replayed line.")

    listed = web.get("/app/sessions?all=true").get_json()
    assert [s["id"] for s in listed] == [real.id]


def test_only_an_admin_lists_every_familys_sessions(web):
    # R-0267
    assert web.get("/app/sessions?all=true").status_code == 403
