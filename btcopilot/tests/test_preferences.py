import datetime

import pytest

from btcopilot.extensions import db
from btcopilot.models import Discussion
from btcopilot.models.preferences import ChatMode, PrefKey, Proactive, Theme


def test_defaults(test_user):
    # R-0017, R-0099
    assert test_user.preferences == {}
    assert test_user.pref(PrefKey.Speak) is False
    assert test_user.pref(PrefKey.Proactive) is Proactive.Never
    assert test_user.pref(PrefKey.Mode) is ChatMode.Text
    assert test_user.pref(PrefKey.Theme) is Theme.System


def test_set_prefs_round_trips(test_user):
    # R-0099
    test_user.set_prefs(speak=True, proactive="weekly", theme=Theme.Dark)
    db.session.commit()

    reloaded = db.session.get(type(test_user), test_user.id)
    assert reloaded.pref(PrefKey.Speak) is True
    assert reloaded.pref(PrefKey.Proactive) is Proactive.Weekly
    assert reloaded.pref(PrefKey.Theme) is Theme.Dark
    assert reloaded.pref(PrefKey.Mode) is ChatMode.Text


def test_set_prefs_rejects_unknown_key(test_user):
    # R-0453
    with pytest.raises(ValueError):
        test_user.set_prefs(colour="blue")


def test_set_prefs_rejects_bad_value(test_user):
    # R-0453
    with pytest.raises(ValueError):
        test_user.set_prefs(proactive="daily")


def test_speak_must_be_bool(test_user):
    # R-0453
    with pytest.raises(ValueError):
        test_user.set_prefs(speak="true")


def test_birthdate_round_trips(test_user):
    # R-0099
    test_user.birthdate = datetime.date(1978, 4, 11)
    db.session.commit()

    assert db.session.get(type(test_user), test_user.id).birthdate == datetime.date(
        1978, 4, 11
    )


def test_discussion_title_defaults_null_and_round_trips(test_user):
    # R-0097
    discussion = Discussion(user_id=test_user.id)
    db.session.add(discussion)
    db.session.commit()
    assert discussion.title is None

    discussion.title = "Sunday afternoon"
    db.session.commit()
    assert db.session.get(Discussion, discussion.id).title == "Sunday afternoon"
