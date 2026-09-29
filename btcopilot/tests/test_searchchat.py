"""The coach searches what was said on a family, across the user's sessions,
by words, by a person's first name, and by the days it was said (R-0520).

Invented names only.
"""

import datetime

import pytest

from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import Person, asdict
from btcopilot.toolbox import SEARCH_CUT, ToolError, ToolName, Toolbox


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren")), asdict(Person(id=2, name="Ash"))]
    data.lastItemId = 2
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def says(session, text: str, day: str, coach: bool = False) -> None:
    db.session.add(
        Statement(
            discussion_id=session.id,
            text=text,
            speaker_id=(
                session.chat_ai_speaker_id if coach else session.chat_user_speaker_id
            ),
            created_at=datetime.datetime.fromisoformat(day),
        )
    )
    db.session.commit()


def search(family, user, **args) -> list[str]:
    text, _ = Toolbox(family.id, "t9", user_id=user.id).call(
        ToolName.SearchChat.value, args
    )
    return [line.split(" ", 1)[1] for line in text.splitlines()]


def test_a_search_finds_words_in_any_of_the_users_sessions_newest_first(
    family, test_user, test_user_2
):
    # R-0520
    first, later = open_session(test_user, family), open_session(test_user_2, family)
    says(first, "Mum moved to the coast in 1990.", "2026-01-05T10:00")
    says(first, "When she moved, who went with her?", "2026-01-05T10:01", coach=True)
    says(
        open_session(test_user, family),
        "We removed the old photos.",
        "2026-02-01T09:00",
    )
    says(later, "Mum moved again.", "2026-03-01T09:00")

    assert search(family, test_user, words="moved mum") == [
        "2026-01-05 user: Mum moved to the coast in 1990.",
    ]
    assert search(family, test_user, words="moved") == [
        "2026-01-05 coach: When she moved, who went with her?",
        "2026-01-05 user: Mum moved to the coast in 1990.",
    ]


def test_a_search_by_person_uses_their_first_name_and_keeps_to_the_days(
    family, test_user, monkeypatch
):
    # R-0520
    monkeypatch.setattr("btcopilot.toolbox.SEARCH_SHOWN", 1)
    session = open_session(test_user, family)
    says(session, "Ash started school.", "2026-01-05T10:00")
    says(session, "I was washing up when Ash called.", "2026-02-05T10:00")
    says(session, "Ash's wedding was lovely.", "2026-03-05T10:00")
    says(session, "The car wash closed.", "2026-03-06T10:00")

    assert search(family, test_user, person=2, end="2026-02-05") == [
        "2026-02-05 user: I was washing up when Ash called.",
        "older ones matched too; narrow the days to see them.",
    ]
    assert search(family, test_user, person=2, start="2026-03-01") == [
        "2026-03-05 user: Ash's wedding was lovely.",
    ]


def test_a_long_message_is_cut_around_what_matched(family, test_user):
    # R-0520
    session = open_session(test_user, family)
    says(
        session,
        "x" * SEARCH_CUT + " Wren left home " + "y" * SEARCH_CUT,
        "2026-01-05T10:00",
    )

    (hit,) = search(family, test_user, words="left")
    assert hit.startswith("2026-01-05 user: …x")
    assert "Wren left home" in hit
    assert hit.endswith("y…")


def test_a_search_for_nothing_is_refused(family, test_user):
    # R-0520
    with pytest.raises(ToolError):
        search(family, test_user)
