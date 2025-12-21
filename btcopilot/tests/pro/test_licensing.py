import os, uuid, pickle
import datetime
import contextlib

import mock
import pytest
import flask_mail


import btcopilot
from btcopilot import params
from btcopilot.extensions import db, mail, create_stripe_Subscription, sync_with_stripe
from btcopilot.pro import validate_uuid4
from btcopilot.pro.models import (
    User,
    Machine,
    Activation,
    License,
    Policy,
)


# STRIPE_PUBLISHABLE_KEY = 'pk_test_Su5gswjnbuKpxLKmZsnnMTMf00r8LLUZRI'


## Users


@pytest.mark.real_passwords
def test_user_password():
    user = User(username="patrickkidd@gmail.com", password="something")
    assert user.password != "something"
    assert user.check_password("something") == True


@pytest.mark.real_passwords
def test_user_password_fail():
    user = User(username="patrickkidd@gmail.com", password="something")
    assert user.check_password("something 22") == False


@pytest.mark.real_passwords
def test_user_reset_password_code():
    code = "123456"
    user = User(
        username="patrickkidd@gmail.com", password="something", reset_password_code=code
    )
    assert user.reset_password_code != code
    assert user.check_reset_password_code(code) == True


@pytest.mark.real_passwords
def test_user_reset_password_code_fail():
    code = "123456"
    user = User(
        username="patrickkidd@gmail.com", password="something", reset_password_code=code
    )
    assert user.check_reset_password_code("999999") == False


@pytest.mark.real_passwords
def test_user_reset_password_code_is_null():
    code = "123456"
    user = User(
        username="patrickkidd@gmail.com", password="something", reset_password_code=code
    )
    user.set_password("something else")
    assert user.reset_password_code == None


@pytest.mark.parametrize(
    "roles, requested, expected",
    [
        [(btcopilot.ROLE_SUBSCRIBER,), btcopilot.ROLE_AUDITOR, False],
        [(btcopilot.ROLE_SUBSCRIBER,), btcopilot.ROLE_ADMIN, False],
        [(btcopilot.ROLE_AUDITOR,), btcopilot.ROLE_SUBSCRIBER, True],
        [(btcopilot.ROLE_AUDITOR,), btcopilot.ROLE_ADMIN, False],
        [(btcopilot.ROLE_ADMIN,), btcopilot.ROLE_SUBSCRIBER, True],
        [(btcopilot.ROLE_ADMIN,), btcopilot.ROLE_AUDITOR, True],
    ],
)
def test_roles(roles, requested, expected):
    user = User(
        username="patrickkidd@gmail.com",
        password="something",
        roles=roles,
    )
    assert user.has_role(requested) == expected


# Users HTTP


def test_users_status(flask_app, test_user):
    test_user.status = "confirmed"
    db.session.commit()
    args = {"username": test_user.username}
    with flask_app.test_client() as client:
        response = client.post("/v1/users/status", data=pickle.dumps(args))
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["status"] == "confirmed"
    assert data["id"] == test_user.id


def test_users_status_pending(flask_app, test_user):
    test_user.status = "pending"
    db.session.commit()
    args = {"username": test_user.username}
    with flask_app.test_client() as client:
        response = client.post("/v1/users/status", data=pickle.dumps(args))
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["status"] == "pending"
    assert data["id"] == test_user.id


def test_users_status_not_found(flask_app, test_user):
    args = {"username": "noone@none.com"}
    with flask_app.test_client() as client:
        response = client.post("/v1/users/status", data=pickle.dumps(args))
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["status"] == "not found"


def test_users_create(flask_app):
    args = {"username": "patrickkidd@gmail.com"}
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/users", data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert type(data["id"]) == int
    assert User.query.filter_by(username=args["username"]).first().id == 1


def test_users_create_conflict(flask_app, test_user):
    args = {"username": test_user.username}
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/users", data=bdata)
    assert response.status_code == 409


def test_users_confirm_code(flask_app, test_user):
    code = "123456"
    test_user.set_reset_password_code(code)
    db.session.commit()
    args = {"username": test_user.username, "reset_password_code": code}
    with flask_app.test_client() as client:
        response = client.post(
            "/v1/users/%i/confirm" % test_user.id, data=pickle.dumps(args)
        )
    assert response.status_code == 200


def test_users_confirm_code_fail(flask_app, test_user):
    code = "123456"
    test_user.set_reset_password_code(code)
    db.session.commit()
    args = {"username": test_user.username, "reset_password_code": "999999"}
    with flask_app.test_client() as client:
        response = client.post(
            "/v1/users/%i/confirm" % test_user.id, data=pickle.dumps(args)
        )
    assert response.status_code == 401


def test_users_update(flask_app, test_user):
    code = "123456"
    test_user.set_reset_password_code(code)
    db.session.commit()
    was_first_name = test_user.first_name
    was_last_name = test_user.last_name
    args = {
        "username": test_user.username,
        "password": "something",
        "reset_password_code": code,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/users/%s" % test_user.id, data=bdata)
    assert response.status_code == 200
    pickle.loads(response.data)
    user = User.query.filter_by(username=args["username"]).first()
    assert user.check_password(args["password"]) == True
    assert user.first_name == was_first_name
    assert user.last_name == was_last_name
    assert user.status == "confirmed"


def test_users_update_no_password(flask_app, test_user):
    test_user.set_password("something")
    code = "123456"
    test_user.set_reset_password_code(code)
    db.session.commit()
    args = {
        "username": test_user.username,
        "first_name": "Some",
        "last_name": "Person",
        "reset_password_code": code,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/users/%s" % test_user.id, data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    user = User.query.filter_by(username=args["username"]).first()
    assert user.check_password("something") == True
    assert user.first_name == args["first_name"]
    assert user.last_name == args["last_name"]


def test_users_update_invalid_code(flask_app, test_user):
    test_user.set_password("old password")
    code = "123456"
    test_user.set_reset_password_code(code)
    db.session.commit()
    args = {
        "username": test_user.username,
        "password": "new password",
        "reset_password_code": "999999",
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.post("/v1/users/%i" % test_user.id, data=bdata)
    assert response.status_code == 401
    user = User.query.filter_by(username=args["username"]).first()
    assert user.check_password(args["password"]) != True


def test_users_email_code(snapshot, flask_app, test_user, monkeypatch):
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch("random.randint", return_value=123456))
        send = stack.enter_context(
            mock.patch.object(flask_mail.Mail, "send", wraps=mail.send)
        )
        client = stack.enter_context(flask_app.test_client())
        response = client.post("/v1/users/%i/email_code" % test_user.id, data=b"")
    assert response.status_code == 200
    message = send.call_args[0][0]
    snapshot.assert_match(message.html)
    user = User.query.filter_by(id=test_user.id).first()
    assert user.check_reset_password_code(message.__code)


# still used?
def test_users_get_free_diagram_none(flask_app, test_session, test_user):
    args = {
        "session": test_session.token,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.get(f"/v1/users/{test_user.id}/free_diagram", data=bdata)
    assert response.data == test_user.free_diagram.data


def test_users_get_free_diagram_data(flask_app, test_user, test_session):
    set_data = pickle.dumps({})
    test_user.set_free_diagram(set_data, _commit=True)
    args = {
        "session": test_session.token,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.get(f"/v1/users/{test_user.id}/free_diagram", data=bdata)
    assert response.data == set_data
    assert response.last_modified.replace(
        tzinfo=None
    ) == test_user.free_diagram.updated_at.replace(microsecond=0)


def test_users_update_free_diagram_data(flask_app, test_user, test_session):
    test_user.set_free_diagram(b"")
    args = {
        "session": test_session.token,
        "data": pickle.dumps(pickle.dumps({"with": "more"})),
    }
    with flask_app.test_client(user=test_user) as client:
        response = client.put(
            f"/v1/users/{test_user.id}/free_diagram", data=pickle.dumps(args)
        )
    assert response.data == User.query.get(test_user.id).free_diagram.data


## Policies


def test_policies(flask_app, test_license, test_session, test_user):
    policy_id = test_license.policy.id
    policy_name = test_license.policy.name
    policy_maxActivations = test_license.policy.maxActivations
    policy2 = Policy(maxActivations=3, name="some policy")
    db.session.add(policy2)
    db.session.commit()
    bdata = pickle.dumps({"session": test_session.token})
    with flask_app.test_client(user=test_user) as client:
        response = client.get("/v1/policies", data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    policies = data["policies"]
    assert len(policies) == 2
    assert policies[0]["id"] == policy_id
    assert policies[0]["name"] == policy_name
    assert policies[0]["maxActivations"] == policy_maxActivations
    assert policies[1]["id"] == policy2.id
    assert policies[1]["name"] == policy2.name
    assert policies[1]["maxActivations"] == policy2.maxActivations


## Licenses


def test_licenses_purchase(flask_app, test_user, test_license, test_session):
    args = {
        "session": test_session.token,
        "policy": test_license.policy.code,
        "cc_number": "4242424242424242",
        "cc_exp_month": "12",
        "cc_exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
        "cc_cvc": "123",
        "cc_zip": "83014",
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses", data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert validate_uuid4(data["key"]) == True
    activated_at = data["activated_at"]
    assert (datetime.datetime.utcnow() - activated_at).days in (0, 1)
    assert len(data["activations"]) == 0
    if flask_app.config["STRIPE_ENABLED"]:
        assert data["stripe_id"] != None


def test_licenses_purchase_and_activate_new_machine(
    flask_app, test_user, test_license, test_session
):
    assert Machine.query.count() == 0
    args = {
        "session": test_session.token,
        "policy": test_license.policy.code,
        "cc_number": "4242424242424242",
        "cc_exp_month": "12",
        "cc_exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
        "cc_cvc": "123",
        "cc_zip": "83014",
        "machine": {"code": str(uuid.uuid4()), "name": "Some machine"},
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses", data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    # machine
    assert Machine.query.count() == 1
    assert Machine.query.all()[0].code == args["machine"]["code"]
    assert Machine.query.all()[0].name == args["machine"]["name"]
    assert len(data["activations"]) == 1
    assert data["activations"][0]["machine"]["code"] == args["machine"]["code"]
    assert data["activations"][0]["machine"]["name"] == args["machine"]["name"]


def test_licenses_purchase_declined(flask_app, test_user, test_license, test_session):
    args = {
        "session": test_session.token,
        "policy": test_license.policy.code,
        "cc_number": "4000000000000002",
        "cc_exp_month": "12",
        "cc_exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
        "cc_cvc": "123",
        "cc_zip": "83014",
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses", data=bdata)
    assert response.status_code == 400


def test_licenses_purchase_invalid_policy(
    flask_app, test_user, test_license, test_session
):
    args = {
        "session": test_session.token,  # TODO: rename to 'session'
        "policy": "99999",
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses", data=bdata)
    assert response.status_code == 400


@pytest.mark.skipif(
    not params.truthy(os.getenv("ENABLE_STRIPE", False)),
    reason="Tests communication with Stripe",
)
def test_licenses_cron_check_Stripe_canceled(flask_app, test_session, test_policy):
    import stripe

    assert flask_app.config["STRIPE_ENABLED"]
    license = License(
        user=test_session.user,
        policy=test_policy,
        active=True,
        activated_at=datetime.datetime.utcnow(),
    )
    stripeSub = create_stripe_Subscription(
        test_session.user,
        test_policy,
        license,
        {
            "number": "4242424242424242",
            "exp_month": "12",
            "exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
            "cvc": "123",
            "address_zip": "83014",
        },
    )
    license.stripe_id = stripeSub["id"]
    stripe.Subscription.delete(stripeSub["id"])
    db.session.add(license)
    db.session.commit()
    license_id = license.id

    sync_with_stripe(flask_app)
    license = License.query.get(license_id)
    assert license.canceled == True
    assert stripe.Subscription.retrieve(stripeSub["id"])["status"] == "canceled"


@pytest.mark.skipif(
    not params.truthy(os.getenv("ENABLE_STRIPE", False)),
    reason="Tests communication with Stripe",
)
def test_licenses_not_cron_check_canceled(flask_app, test_session, test_policy):
    import stripe

    assert flask_app.config["STRIPE_ENABLED"]
    license = License(
        user=test_session.user,
        policy=test_policy,
        active=True,
        activated_at=datetime.datetime.utcnow(),
    )
    stripeSub = create_stripe_Subscription(
        test_session.user,
        test_policy,
        license,
        {
            "number": "4242424242424242",
            "exp_month": "12",
            "exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
            "cvc": "123",
            "address_zip": "83014",
        },
    )
    license.stripe_id = stripeSub["id"]
    db.session.add(license)
    db.session.commit()

    sync_with_stripe()
    db.session.refresh(license)
    assert license.canceled == False
    assert stripe.Subscription.retrieve(stripeSub["id"])["status"] == "active"


def test_licenses_verify(flask_app, test_license):
    args = {"licenses": [test_license.as_dict(include="policy")]}
    bdata = pickle.dumps(args)
    test_license.canceled = True
    test_license.active = False
    db.session.commit()
    with flask_app.test_client() as client:
        response = client.get("/v1/licenses/verify", data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["licenses"][0]["canceled"] == True
    assert data["licenses"][0]["active"] == False


@pytest.fixture
def no_license():
    return {
        "activated_at": None,
        "active": True,
        "canceled": False,
        "canceled_at": None,
        "created_at": datetime.datetime(2020, 3, 1, 4, 43, 5, 888106),
        "id": 1,
        "key": "237531df-2fbe-44e1-b175-7dd4b1b7ab9a",
        "policy": {
            "active": True,
            "amount": 0.0,
            "code": "com.vedanamedia.familydiagram.professional.monthly",
            "created_at": datetime.datetime(2020, 3, 1, 3, 41, 58, 238656),
            "description": "Full functionaliy for alpha releases only. "
            "Requires entering a license key provided by "
            "Vedanā Media",
            "id": 3,
            "interval": None,
            "maxActivations": 2,
            "name": "Alpha",
            "product": "com.vedanamedia.familydiagram.professional",
            "public": False,
            "updated_at": None,
        },
        "policy_id": 3,
        "stripe_id": None,
        "updated_at": None,
        "user_id": None,
    }


def test_licenses_verify_404(flask_app, no_license):
    args = {"licenses": [no_license]}
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.get("/v1/licenses/verify", data=bdata)
    assert response.status_code == 404
    assert (
        response.headers["FD-User-Message"]
        == "License %s not found" % no_license["key"]
    )


@pytest.mark.skip(reason="Trouble reproducing")
def test_licenses_verify_no_500_on_empty_db(flask_app, no_license):
    args = {"licenses": [no_license]}
    bdata = pickle.dumps(args)
    with flask_app.test_client() as client:
        response = client.get("/v1/licenses/verify", data=bdata)
    assert response.status_code == 404
    data = pickle.loads(response.data)
    assert data == {"licenses": []}


def test_licenses_cancel(flask_app, test_user, test_session, test_policy):
    license = License(
        user=test_session.user,
        policy=test_policy,
        activated_at=datetime.datetime.utcnow(),
    )
    if flask_app.config["STRIPE_ENABLED"]:
        stripeSub = create_stripe_Subscription(
            test_session.user,
            test_policy,
            license,
            {
                "number": "4242424242424242",
                "exp_month": "12",
                "exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
                "cvc": "123",
                "address_zip": "83014",
            },
        )
        license.stripe_id = stripeSub["id"]
    db.session.add(license)
    db.session.commit()
    license_id = license.id
    args = {"session": test_session.token}
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses/%s/cancel" % license.key, data=bdata)
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["canceled_at"] != None
    assert data["canceled"] == True
    assert data["active"] == True

    license = License.query.get(license_id)
    assert license.canceled_at != None
    assert license.canceled == True
    assert license.active == True

    if flask_app.config["STRIPE_ENABLED"]:
        import stripe

        assert stripe.Subscription.retrieve(stripeSub["id"])["status"] == "canceled"


@pytest.mark.skipif(
    not params.truthy(os.getenv("ENABLE_STRIPE", False)),
    reason="Tests communication with Stripe",
)
def test_licenses_canceled_and_not_active(
    flask_app, test_user, test_session, test_policy
):
    license = License(
        user=test_session.user,
        policy=test_policy,
        activated_at=datetime.datetime.utcnow(),
    )
    if flask_app.config["STRIPE_ENABLED"]:
        stripeSub = create_stripe_Subscription(
            test_session.user,
            test_policy,
            license,
            {
                "number": "4242424242424242",
                "exp_month": "12",
                "exp_year": "%i" % (datetime.datetime.utcnow().year + 1),
                "cvc": "123",
                "address_zip": "83014",
            },
        )
        license.stripe_id = stripeSub["id"]
        db.session.add(license)
        db.session.commit()
    args = {"session": test_session.token}
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses/%s/cancel" % license.key, data=bdata)
    assert response.status_code == 200
    sync_with_stripe()

    db.session.refresh(license)
    db.session.commit()
    assert license.canceled == True
    assert license.active == False


def test_licenses_cancel_not_found(flask_app, test_user, test_license, test_session):
    args = {"session": test_session.token, "key": "bad key"}
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses/%s/cancel", data=bdata)
    assert response.status_code == 404


def test_licenses_import(flask_app, test_user, test_license, test_session):
    user_id = test_session.user.id
    # add orphan license
    license = License(policy=test_license.policy)
    db.session.add(license)
    db.session.commit()
    #
    args = {"session": test_session.token, "key": license.key}
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses/%s/import", data=bdata)
    assert response.status_code == 200
    license = License.query.filter_by(key=args["key"]).first()
    assert license != None
    assert license.user_id == user_id
    assert (datetime.datetime.utcnow() - license.activated_at).days in (0, 1)
    data = pickle.loads(response.data)
    assert data["id"] == license.id
    assert data["key"] == args["key"]
    assert data["activated_at"] == license.activated_at


def test_licenses_import_not_found(flask_app, test_user, test_license, test_session):
    args = {"session": test_session.token, "key": "bad key"}
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/licenses/%s/import", data=bdata)
    assert response.status_code == 404


## Machines


def test_machines_create(flask_app, test_user, test_session):
    args = {
        "session": test_session.token,
        "code": str(uuid.uuid4()),
        "name": "Some person's machine",
    }
    with flask_app.test_client(user=test_user) as client:
        response = client.post(
            "/v1/machines/%s" % args["code"], data=pickle.dumps(args)
        )
    assert response.status_code == 200
    assert Machine.query.filter_by(code=args["code"]).count() == 1
    machine = Machine.query.filter_by(code=args["code"]).first()
    assert machine.code == args["code"]
    assert machine.name == args["name"]


def test_machines_update(flask_app, test_user, test_session, test_machine):
    machine_id = test_machine.id
    args = {
        "session": test_session.token,
        "code": test_machine.code,
        "name": "A different name",
    }
    #
    with flask_app.test_client(user=test_user) as client:
        response = client.post(
            "/v1/machines/%s" % args["code"], data=pickle.dumps(args)
        )
    assert response.status_code == 200
    test_machine = Machine.query.get(machine_id)
    assert test_machine.code == args["code"]
    assert test_machine.name == args["name"]


def test_machines_delete(flask_app, test_user, test_session):
    args = {
        "session": test_session.token,
        "code": str(uuid.uuid4()),
        "name": "Some machine",
    }
    m1 = Machine(user=test_user, code=args["code"], name=args["name"])
    db.session.add(m1)
    db.session.commit()
    #
    with flask_app.test_client(user=test_user) as client:
        response = client.delete(
            "/v1/machines/%s" % args["code"], data=pickle.dumps(args)
        )
    assert response.status_code == 200
    assert Machine.query.filter_by(code=args["code"]).count() == 0


def test_machines_delete_fail(flask_app, test_user, test_session):
    args = {"session": test_session.token, "code": str(uuid.uuid4())}
    with flask_app.test_client(user=test_user) as client:
        response = client.delete(
            "/v1/machines/%s" % args["code"], data=pickle.dumps(args)
        )
    assert response.status_code == 404


## Activations


def test_activations_create_no_machine(
    flask_app, test_user, test_license, test_session
):
    activations = Activation.query.filter_by(license=test_license)
    assert activations.count() == 0

    machineId = str(uuid.uuid4())
    args = {
        "session": test_session.token,
        "license": test_license.key,
        "machine": str(uuid.uuid4()),
        "name": "Some machine name",
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/activations", data=bdata)
    assert response.status_code == 200
    assert Activation.query.filter_by(license=test_license).count() == 1


def test_activations_create_first(
    flask_app, test_user, test_license, test_session, test_machine
):
    activations = Activation.query.filter_by(license=test_license)
    assert activations.count() == 0

    machineId = str(uuid.uuid4())
    args = {
        "session": test_session.token,
        "license": test_license.key,
        "machine": test_machine.code,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/activations", data=bdata)
    assert response.status_code == 200
    assert Activation.query.filter_by(license=test_license).count() == 1


def test_activations_create_second(
    flask_app, test_user, test_license, test_session, test_machine
):
    machine2 = Machine(
        user=test_session.user, code=str(uuid.uuid4()), name="Second machine"
    )
    db.session.add(machine2)
    a1 = Activation(license=test_license, machine=test_machine)
    db.session.add(a1)
    db.session.commit()
    activations = Activation.query.filter_by(license=test_license)
    assert activations.count() == 1  # test other code, not the above init code
    #
    args = {
        "session": test_session.token,
        "license": test_license.key,
        "machine": machine2.code,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/activations", data=bdata)
    assert response.status_code == 200
    assert Activation.query.filter_by(license=test_license).count() == 2


def test_activations_create_over_limit(
    flask_app, test_user, test_session, test_license, test_machine
):
    machine2 = Machine(
        user=test_session.user, code=str(uuid.uuid4()), name="Second machine"
    )
    a1 = Activation(license=test_license, machine=test_machine)
    a2 = Activation(license=test_license, machine=machine2)
    db.session.add(machine2)
    db.session.add(a1)
    db.session.add(a2)
    db.session.commit()
    assert a1.license.policy.maxActivations == 2  # ensure now at limit

    args = {
        "session": test_session.token,
        "license": test_license.key,
        "machine": str(uuid.uuid4()),  # new machine
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/activations", data=bdata)
    assert response.status_code == 402


def test_activations_duplicate_machine(
    flask_app, test_user, test_session, test_license, test_machine, test_activation
):
    assert len(test_license.activations) == 1  # ensure still under limit

    args = {
        "session": test_session.token,
        "license": test_license.key,
        "machine": test_machine.code,
    }
    bdata = pickle.dumps(args)
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/activations", data=bdata)
    assert response.status_code == 409


def test_activations_deactivate(
    flask_app, test_user, test_session, test_license, test_machine
):
    machine2 = Machine(
        user=test_session.user, code=str(uuid.uuid4()), name="Second machine"
    )
    a1 = Activation(license=test_license, machine=test_machine)
    a2 = Activation(license=test_license, machine=machine2)
    db.session.add(machine2)
    db.session.add(a1)
    db.session.add(a2)
    db.session.commit()
    activations = Activation.query.filter_by(license=test_license)
    assert activations.count() == 2

    machineId = str(uuid.uuid4())
    args = {
        "session": test_session.token,
    }
    with flask_app.test_client(user=test_user) as client:
        response = client.delete("/v1/activations/%i" % a1.id, data=pickle.dumps(args))
    assert response.status_code == 200

    activations = Activation.query.filter_by(license=test_license)
    assert activations.count() == 1
