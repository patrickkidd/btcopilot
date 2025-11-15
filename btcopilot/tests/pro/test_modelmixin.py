#
# TODO: Test Model.function() : list[Model] (e.g. TripType.itinerary_entries)
#

import pytest
import datetime
from freezegun import freeze_time
import dateutil

from btcopilot.extensions import db
from btcopilot.pro.models import User, License

FIXED_TIME = datetime.datetime.fromisoformat("2025-01-15T12:00:00")


@pytest.fixture
def user(flask_app):
    with freeze_time(FIXED_TIME, ignore=["transformers"]):
        user = User(
            username="something",
            secret="some_secret",
            licenses=[License(policy_id=i, key="asd") for i in range(3)],
        )
        user.created_at = datetime.datetime.utcnow()  # Explicitly set
        user.set_password("password")
        db.session.add(user)
        db.session.merge(user)
        db.session.commit()
        with flask_app.app_context():
            yield user


def test_nothing(user):
    assert user.as_dict() == {
        "active": True,
        "first_name": "",
        "free_diagram_id": None,
        "id": 1,
        "last_name": "",
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "created_at": FIXED_TIME,
        "updated_at": None,
        "username": "something",
    }


def test_only_blank(user):
    assert user.as_dict() == {
        "active": True,
        "first_name": "",
        "free_diagram_id": None,
        "id": 1,
        "last_name": "",
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "created_at": FIXED_TIME,
        "updated_at": None,
        "username": "something",
    }


def test_include_one_level(user):
    assert user.as_dict(include={"licenses": {"only": ["id"]}}) == {
        "active": True,
        "created_at": FIXED_TIME,
        "first_name": "",
        "free_diagram_id": None,
        "id": 1,
        "last_name": "",
        "licenses": [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ],
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "updated_at": None,
        "username": "something",
    }


def test_include_one_level_2_attrs(user):
    # Use the existing licenses from the fixture instead of creating new ones
    # The user fixture already has 3 licenses
    assert user.as_dict(include={"licenses": {"only": ["id"]}, "full_name": {}}) == {
        "active": True,
        "created_at": FIXED_TIME,
        "first_name": "",
        "free_diagram_id": None,
        "full_name": " ",
        "id": 1,
        "last_name": "",
        "licenses": [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ],
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "updated_at": None,
        "username": "something",
    }


def test_include_blank(user):
    assert user.as_dict(include="") == {
        "active": True,
        "created_at": FIXED_TIME,
        "first_name": "",
        "free_diagram_id": None,
        "id": 1,
        "last_name": "",
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "updated_at": None,
        "username": "something",
    }


def test_exclude_sub(user):
    assert user.as_dict(
        include={
            "licenses": {
                "exclude": [
                    "policy_id",
                    "key",
                    "activated_at",
                    "canceled",
                    "canceled_at",
                    "created_at",
                    "updated_at",
                ]
            }
        },
        exclude=[
            "user_role",
            "full_name",
            "free_diagram_id",
            "password",
            "stripe_id",
            "reset_password_code",
        ],
    ) == {
        "active": True,
        "created_at": FIXED_TIME,
        "first_name": "",
        "id": 1,
        "last_name": "",
        "licenses": [
            {"active": True, "id": 1, "stripe_id": None, "user_id": 1},
            {"active": True, "id": 2, "stripe_id": None, "user_id": 1},
            {"active": True, "id": 3, "stripe_id": None, "user_id": 1},
        ],
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "updated_at": None,
        "username": "something",
    }


@pytest.mark.parametrize(
    "params",
    [
        {"id": {}, "user_role": {"exclude": "name"}, "full_name": {}},
        {"id": {}, "user_role": {"only": ["id", "name"]}, "full_name": {}},
    ],
)
def test_only(snapshot, user, params):
    snapshot.assert_match(user.as_dict(only=params))


def test_include_and_exclude_one_level(user):
    assert user.as_dict(
        include={
            "licenses": {
                "exclude": [
                    "policy_id",
                    "key",
                    "activated_at",
                    "canceled",
                    "canceled_at",
                    "created_at",
                    "updated_at",
                ]
            },
        }
    ) == {
        "active": True,
        "created_at": FIXED_TIME,
        "first_name": "",
        "free_diagram_id": None,
        "id": 1,
        "last_name": "",
        "licenses": [
            {"active": True, "id": 1, "stripe_id": None, "user_id": 1},
            {"active": True, "id": 2, "stripe_id": None, "user_id": 1},
            {"active": True, "id": 3, "stripe_id": None, "user_id": 1},
        ],
        "roles": ["subscriber"],
        "secret": "some_secret",
        "status": "pending",
        "updated_at": None,
        "username": "something",
    }


def test_include_and_only_one_level(user):
    result = user.as_dict(
        include={
            "licenses": {
                "only": [
                    "id",
                    "canceled",
                ]
            },
        },
        exclude=[
            "active",
            "first_name",
            "free_diagram_id",
            "last_name",
            "secret",
            "status",
            "username",
            "user_role",
            "full_name",
            "password",
            "reset_password_code",
            "stripe_id",
            "created_at",
            "updated_at",
        ],
    )
    assert result == {
        "id": 1,
        "licenses": [
            {
                "canceled": False,
                "id": 1,
            },
            {
                "canceled": False,
                "id": 2,
            },
            {
                "canceled": False,
                "id": 3,
            },
        ],
        "roles": ["subscriber"],
    }


def test_filter_attrs():
    kwargs = User.filter_attrs(
        {
            "created_at": datetime.datetime.now(),
            "updated_at": None,
            "username": "me@there.com",
            "invalid_arg": 123,
        }
    )
    assert set(kwargs.keys()) == {"created_at", "updated_at", "username"}
