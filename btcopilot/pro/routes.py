##
## Create = POST;
##
## Read = GET;
##
## Update = PATCH;
##
## Delete = DELETE.
##


import sys
import re, pickle, ast, datetime, uuid, logging
import pickle
import logging
from functools import wraps

from flask import (
    Blueprint,
    g,
    request,
    current_app,
    Response,
    make_response,
    render_template,
)
from flask_mail import Message
from sqlalchemy import inspect
from sqlalchemy.orm import defer

import vedana

from btcopilot import version, auth
from btcopilot.extensions import (
    db,
    mail,
    create_stripe_Subscription,
    ensure_stripe_Customer,
)
from btcopilot.pro.models import (
    Activation,
    AccessRight,
    Diagram,
    License,
    Machine,
    Policy,
    Session,
    User,
)
from btcopilot.pro import (
    DEACTIVATED_VERSIONS,
    IS_TEST,
    SESSION_EXPIRATION_DAYS,
)


S_FAIL_TO_SERV_LT_v150 = "Received request from app version %s, and this server can only support 1.5.0 and above."

_log = logging.getLogger(__name__)
_log.level = logging.INFO


bp = Blueprint("v1", __name__, url_prefix="/v1")


def init_app(app):
    app.register_blueprint(bp)


def toBool(x):
    y = ast.literal_eval(x)
    return bool(y)


def _client_version_lte(ver_string):
    if g.fd_client_version and version.lessThanOrEqual(g.fd_client_version, ver_string):
        return True
    return False


# decorator
def encrypted(func):
    """
    Server-side implementation of proprietary request signing. must return
    values for this:
    http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get user from FD Auth header

        g.user = auth.current_user()
        # Client Version determines if payloads are encrypted
        g.fd_client_version = request.headers.get("FD-Client-Version")

        if _client_version_lte("1.4.5"):
            # _log.error(S_FAIL_TO_SERV_LT_v150, exc_info=True)
            # return ("App version not supported", 406)
            _log.debug(
                f"Detected client version {g.fd_client_version} which expects encrypted response payloads."
            )

        ## Run view

        response = make_response(func(*args, **kwargs))

        ## Encrypt response

        if response.status_code != 200 and isinstance(response.data, (str, bytes)):
            if isinstance(response.data, bytes):
                x = response.data.decode("utf-8")
            else:
                x = response.data
            x = x.replace("\n", "")
            # y = x.encode("utf-8")
            response.headers["FD-User-Message"] = x

        response.headers["FD-Server-Version"] = bytes(version.VERSION, "utf-8")

        return response

    return wrapper


def deprecated(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        _log.info(f"{func.__qualname__} is deprecated.")
        return func(*args, **kwargs)

    return _wrapper


@bp.route("/hello")
def hello():
    return "Hello, World!"


@bp.route("/deactivated_versions")
@encrypted
@deprecated
def deactivated_versions():
    return ("\n".join(DEACTIVATED_VERSIONS)).encode("utf-8")


@bp.route("/diagrams", methods=("GET", "POST"))
@bp.route("/diagrams/<int:id>", methods=("GET", "PATCH", "PUT", "DELETE"))
@encrypted
def diagrams(id=None):
    """
    HEAD: verify
    GET: index, data
    POST: create
    PUT|PATCH: update
    DELETE: delete
    """
    if g.user.IS_ANONYMOUS:
        return ("Access Denied", 401)
    if id is None:
        if request.method == "GET":  # index
            if "user_id" in request.args:
                try:
                    user_id = int(request.args["user_id"])
                except ValueError:
                    user_id = None
                if user_id is None:
                    email = request.args["user_id"]
                    user = User.query.filter_by(username=email).first()
                    if not user:
                        return ("Not Found", 404)
                    user_id = user.id
            else:
                user_id = g.user.id
            own_diagrams = (
                Diagram.query.filter_by(user_id=user_id).options(defer(Diagram.data))
            ).all()
            shared_diagrams = (
                Diagram.query.join(AccessRight)
                .filter(
                    AccessRight.user_id == user_id,
                    AccessRight.right.in_(
                        [vedana.ACCESS_READ_ONLY, vedana.ACCESS_READ_WRITE]
                    ),
                )
                .options(defer(Diagram.data))
            ).all()
            diagrams = list(set(own_diagrams + shared_diagrams))
            diagrams = sorted(diagrams, key=lambda x: x.id)
            data = [
                diagram.as_dict(exclude="data", include="saved_at")
                for diagram in diagrams
            ]
            # _log.debug(f"INDEX:")
            # for diagram in data:
            #     _log.debug(f"    Diagram[{diagram['id']}].updated_at: {diagram['updated_at']}")
            if _client_version_lte("1.4.5"):
                # Versions up to 1.4.5 expect a dict for server index. It's zero
                # customer impact so no big deal, but avoids spamming the app log
                # with exceptions.
                return pickle.dumps({x["id"]: x for x in data})
            else:
                return pickle.dumps(data)
        elif request.method == "POST":  # create
            args = pickle.loads(request.data)
            diagram = Diagram(
                user_id=g.user.id,
                name=args["name"],
                data=args["data"],
            )
            db.session.add(diagram)
            db.session.commit()
            _log.info("Created new diagram")
            return pickle.dumps(diagram.as_dict())
    else:
        diagram = Diagram.query.get(id)
        if not diagram:
            return ("Not Found", 404)
        if request.method in ("GET", "HEAD"):  # data
            if not diagram.check_read_access(g.user) and not g.user.has_role(
                vedana.ROLE_ADMIN
            ):
                return ("Access Denied", 401)
        if request.method == "GET":  # data
            # if diagram.data:
            #     data = diagram.as_dict()
            #     persons = [item for item in data.get('items', []) if item['kind'] == 'Person']
            #     _log.debug(f"    Scene contains persons: {len(persons)}")
            #     _log.debug(f"    Diagram.updated_at: {diagram.updated_at}")
            _log.info(f"Fetched diagram {id}")
            return pickle.dumps(diagram.as_dict())
        elif request.method == "HEAD":  # verify
            return ("Success", 200)
        elif request.method in ("PATCH", "PUT"):  # update
            if not diagram.check_write_access(g.user):
                return ("Access Denied", 401)
            data = pickle.loads(request.data)
            # Support either sending a pickled dict of db model attributes or the pickled scene data.
            # To sync with the client's `updated_at` so that it doesn't think
            # someone else wrote to the server every time it itself writes to the server.
            diagram.updated_at = data["updated_at"]
            diagram.data = data["data"]
            session = inspect(diagram).session
            session.add(diagram)
            # persons = [item for item in data.get('items', []) if item['kind'] == 'Person']
            # _log.debug(f"    Scene contains persons: {len(persons)}")
            # _log.debug(f"    Diagram.updated_at: {diagram.updated_at}")
            session.commit()
            _log.info(
                f"Updated diagram {diagram.id} for user: {g.user}, bytes: {len(diagram.data)} updated_at: {diagram.updated_at}"
            )
            return ("Success", 200)
        elif request.method == "DELETE":  # delete
            if not diagram.check_write_access(g.user):
                return ("Access Denied", 401)
            Diagram.query.filter_by(id=diagram.id).delete()
            db.session.commit()
            _log.info("Deleted diagram for user: %s" % g.user)
            return ("Success", 200)


## Users


@bp.route("/users/status", methods=("POST",))
@encrypted
def users_status():
    args = pickle.loads(request.data)
    user = User.query.filter_by(username=args["username"].lower()).first()
    if user:
        data = {"status": user.status, "id": user.id}
    else:
        data = {"status": "not found"}
    return pickle.dumps(data)
    # user = User(username=args['username'],
    #                password=args['password'])
    # user.reset_password_code = str(uuid.uuid4())
    # db.session.add(user)
    # db.session.commit()
    # if current_app.config['STRIPE_ENABLED']:
    #     customer = ensure_stripe_Customer(user)
    #     user.stripe_id = customer['id']
    #     db.session.commit()
    # current_app.send_new_user_email()
    # return pickle.dumps({ 'status': 'created' })


@bp.route("/users", methods=("POST",))
@encrypted
def users_create():
    args = pickle.loads(request.data)
    regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not re.search(regex, args["username"].lower()):
        return ("Bad Request", 400)
    user = User.query.filter_by(username=args["username"].lower()).first()
    if user:
        return ("Conflict", 409)
    user = User(username=args["username"].lower())
    db.session.add(user)
    db.session.merge(user)
    user.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    g.user = user
    if current_app.config["STRIPE_ENABLED"]:
        customer = ensure_stripe_Customer(user)
        user.stripe_id = customer["id"]
        db.session.commit()
    data = {"id": user.id}
    bdata = pickle.dumps(data)
    _log.info("Created user: %s" % user)
    return bdata


@bp.route("/users/<int:user_id>/email_code", methods=("POST",))
@encrypted
def users_email_code(user_id):
    user = User.query.get(user_id)
    g.user = user
    if not user:
        return ("User doesn't exist", 404)
    code = str(uuid.uuid4())
    user.set_reset_password_code(code)

    msg = Message(
        "Instructions to reset your family diagram password",
        recipients=[user.username],
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    msg.__code = code  # for testing
    msg.html = render_template("set_password_email.html", user=user, license_key=code)
    _log.debug(f"self.mail.server: {mail.server}, self.mail.port: {mail.port}")
    mail.send(msg)

    db.session.commit()
    _log.info("Sent reset password email to: %s" % (user))
    return pickle.dumps(user.as_dict())


@bp.route("/users/<int:user_id>/confirm", methods=("POST",))
@encrypted
def users_confirm(user_id):
    args = pickle.loads(request.data)
    user = User.query.get(user_id)
    g.user = user
    if not user:
        return ("User does not exist", 404)
    reset_password_code = args.get("reset_password_code").strip()
    _log.info("Confirming password code for user: %s" % (user))
    if not user.check_reset_password_code(reset_password_code):
        return ("Invalid code", 401)
    bdata = pickle.dumps(user.as_dict())
    _log.info(f"Confirmed password code for {user}")
    return bdata


@bp.route("/users/<int:user_id>", methods=("POST",))
@encrypted
def users_update(user_id):
    args = pickle.loads(request.data)
    user = User.query.get(user_id)
    g.user = user
    if not user:
        return ("Not Found", 404)
    if "session" in args:
        session = Session.query.filter_by(token=args["session"]).first()
        if session.user.id != user.id:
            return ("Session does not match user", 401)
    else:
        if not user.check_reset_password_code(args["reset_password_code"]):
            return ("Invalid password reset code", 401)
    if args.get("password"):
        user.set_password(args["password"])
        user.status = "confirmed"
    if args.get("first_name"):
        user.first_name = args["first_name"]
    if args.get("last_name"):
        user.last_name = args["last_name"]
    db.session.commit()
    data = user.as_dict(
        {"licenses": [l.as_dict({"policy": l.policy.as_dict()}) for l in user.licenses]}
    )
    _log.info("Updated attributes for: %s" % user)
    return pickle.dumps(data)


@bp.route("/users/<int:user_id>/free_diagram", methods=("GET", "POST", "PUT", "PATCH"))
@encrypted
def users_free_diagram(user_id):
    user = User.query.get(user_id)
    if not user:
        return ("Not Found", 404)
    if g.user.id != user.id:
        return ("Unauthorized", 401)
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    if request.method == "GET":
        if not user.free_diagram:
            # upsert?
            # user.set_free_diagram(None, _commit=True)
            return ("No Content", 204)  # Sort of like a HEAD
        else:
            response = Response(user.free_diagram.data, status=200)
            response.last_modified = user.free_diagram.updated_at
            return response
    elif request.method == "POST":
        _log.info("Created free diagram for user: %s" % user)
        user.set_free_diagram(
            args["data"], updated_at=args.get("localMTime"), _commit=True
        )
        return pickle.dumps(user.free_diagram.as_dict())
    elif request.method in ("PUT", "PATCH"):
        if args.get("localMTime"):
            _log.info("Updated free diagram for user: %s" % user)
            user.set_free_diagram(
                args["data"], updated_at=args.get("localMTime"), _commit=True
            )
        else:
            _log.info("Created free diagram for user: %s" % user)
            user.set_free_diagram(args["data"], _commit=True)
    if user.free_diagram.data:
        return user.free_diagram.data
    else:
        return b""


## Sessions


@bp.route("/init", methods=("GET",))
@encrypted
def sessions_init():
    """Called when the MainWindow starts up."""
    args = pickle.loads(request.data)
    if args.get("token"):
        session = Session.query.filter_by(token=args.get("token")).first()
        if not session:
            return ("Not Found", 404)
        elif (
            datetime.datetime.utcnow() - session.updated_at
        ).days >= SESSION_EXPIRATION_DAYS:
            db.session.delete(session)
            return ("Not Found", 404)
        data = session.account_editor_dict()
        session.updated_at = datetime.datetime.utcnow()  # set when accessing
    else:
        session = Session()
        data = session.account_editor_dict()
        data["session"] = None
    # Offline licensess
    license_keys = [x["key"] for x in args["licenses"]]
    licenses_q = License.query.filter(License.key.in_(license_keys)).filter(
        License.active == True
    )
    g.user = session.user
    data["licenses"] = [x.as_dict(include="policy") for x in licenses_q]
    #
    bdata = pickle.dumps(data)
    if not IS_TEST:
        _log.info("Re-logged in user: %s" % session.user)
    return bdata


@bp.route("/sessions", methods=("POST",))
@encrypted
def sessions_login():
    args = pickle.loads(request.data)
    include_therapist = args.get("include_therapist", False)
    user = User.query.filter_by(username=args["username"].lower()).first()
    if not user or not user.check_password(args["password"]):
        return ("Unauthorized", 401)
    session = Session(user_id=user.id)
    db.session.add(session)
    db.session.commit()
    account_editor_dict = session.account_editor_dict()
    if not include_therapist and account_editor_dict["session"]["user"].get(
        "free_diagram"
    ):
        free_diagram = account_editor_dict["session"]["user"].get("free_diagram")
        if "discussions" in free_diagram:
            del free_diagram["discussions"]
    bdata = pickle.dumps(account_editor_dict)
    g.user = session.user
    if not IS_TEST:
        _log.info(f"Logged in user: {user}")
    return bdata


@bp.route("/sessions/<token>", methods=("GET", "DELETE"))
@encrypted
def sessions_session(token):
    session = Session.query.filter_by(token=token).first()
    if not session:
        return ("Not Found", 404)
    elif (
        datetime.datetime.utcnow() - session.updated_at
    ).days >= SESSION_EXPIRATION_DAYS:
        db.session.delete(session)
        return ("Not Found", 404)
    g.user = session.user
    if request.method == "GET":
        session.updated_at = datetime.datetime.utcnow()  # set when accessing
        bdata = pickle.dumps(session.account_editor_dict())
        _log.info("Re-logged in user: %s" % session.user)
        return bdata
    elif request.method == "DELETE":
        db.session.delete(session)
        db.session.commit()
        _log.info("Logged out user: %s" % g.user)
        return ("Success", 200)


## Policies


@bp.route("/policies", methods=("GET",))
@encrypted
def policies_policies():
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    ret = {"policies": []}
    for policy in Policy.query.all():
        ret["policies"].append(policy.as_dict())
    bdata = pickle.dumps(ret)
    return bdata


## Licenses


@bp.route("/licenses", methods=("POST",))
@encrypted
def licenses_purchase():
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)

    policy = Policy.query.filter_by(code=args["policy"]).first()
    if not policy:
        return ("Bad Request", 400)

    license = License(
        user=session.user, policy=policy, activated_at=datetime.datetime.utcnow()
    )
    db.session.add(license)

    machine = None
    if "machine" in args:
        machine = Machine.query.filter_by(code=args["machine"]["code"]).first()
        if not machine:
            machine = Machine(
                user=session.user,
                code=args["machine"]["code"],
                name=args["machine"]["name"],
            )
            db.session.add(machine)
            _log.info("Added Machine %s for: %s" % (machine, session.user))
        activation = Activation.query.filter_by(
            license=license, machine=machine
        ).first()
        if not activation:
            activation = Activation(license_id=license.id, machine_id=machine.id)
            _log.info(
                "Activated %s on `%s` for %s"
                % (license.policy.code, machine.name, session.user)
            )
            db.session.add(activation)

    if current_app.config["STRIPE_ENABLED"]:
        import stripe

        stripeCard = {
            "number": args["cc_number"],
            "exp_month": args["cc_exp_month"],
            "exp_year": args["cc_exp_year"],
            "cvc": args["cc_cvc"],
            "address_zip": args.get("cc_zip"),
        }
        try:
            subscription = create_stripe_Subscription(
                session.user, policy, license, stripeCard
            )
        except stripe.error.StripeError as e:
            import traceback, sys

            a, b, c = sys.exc_info()
            traceback.print_exception(a, b, c)
            response = Response(e.user_message, 400)
            response.headers["FD-User-Message"] = e.user_message
            db.session.close()
            return response
        license.stripe_id = subscription["id"]
    elif current_app.config["TESTING"] and args["cc_number"] == "4000000000000002":
        return ("Declined", 400)

    db.session.commit()

    _log.info("Added license %s for: %s" % (license, session.user))

    data = license.as_dict(
        {
            "policy": policy.as_dict(),
            "activations": [
                a.as_dict({"machine": a.machine.as_dict()}) for a in license.activations
            ],
        }
    )
    return pickle.dumps(data)


@bp.route("/licenses/verify", methods=("GET",))
@encrypted
@deprecated
def licenses_verify():
    args = pickle.loads(request.data)
    ret = {"licenses": []}
    for entry in args["licenses"]:
        license = License.query.filter_by(key=entry["key"]).first()
        if license:
            ret["licenses"].append(license.as_dict(include="policy"))
        else:
            return ("License %s not found" % entry["key"], 404)
    return pickle.dumps(ret)


@bp.route("/licenses/<key>", methods=("GET",))
@encrypted
def licenses_get(key):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    user = session.user
    license = License.query.filter_by(key=args["key"]).first()
    if not license:
        return ("Not Found", 404)
    if license.user != session.user:
        return ("Unauthorized", 401)
    data = license.as_dict()
    data["days_old"] = license.days_old()
    data["user"] = license.user.as_dict()
    data["policy"] = license.policy.as_dict()
    return pickle.dumps(data)


@bp.route("/licenses/<key>/cancel", methods=("POST",))
@encrypted
def licenses_cancel(key):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    user = session.user
    license = License.query.filter_by(key=key).first()
    if not license:
        return ("Not Found", 404)
    if license.user != session.user:
        return ("Unauthorized", 401)
    if current_app.config["STRIPE_ENABLED"]:
        import stripe

        try:
            stripe.Subscription.delete(license.stripe_id)
        except stripe.error.StripeError as e:
            response = Response(e.user_message, 400)
            response.headers["FD-User-Message"] = e.user_message
            return response
    license.canceled = True
    license.canceled_at = datetime.datetime.utcnow()
    db.session.commit()
    _log.info("Canceled license %s for: %s" % (license.policy.code, user))
    bdata = pickle.dumps(license.as_dict())
    return bdata


@bp.route("/licenses/<key>/import", methods=("POST",))
@encrypted
def licenses_import(key):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    user = session.user
    license = License.query.filter_by(key=args["key"]).first()
    if not license:
        return ("Not Found", 404)
    if license.user_id != None:
        return ("Unauthorized", 401)
    license.activated_at = datetime.datetime.utcnow()
    license.user = session.user
    machine = None
    if "machine" in args:
        machine = Machine.query.filter_by(code=args["machine"]["code"]).first()
        if not machine:
            machine = Machine(
                user=session.user,
                code=args["machine"]["code"],
                name=args["machine"]["name"],
            )
            db.session.add(machine)
        activation = Activation.query.filter_by(
            license=license, machine=machine
        ).first()
        if not activation:
            activation = Activation(license_id=license.id, machine_id=machine.id)
            db.session.add(activation)
    db.session.commit()
    _log.info("Imported license %s for: %s" % (license.policy.code, user))
    bdata = pickle.dumps(license.as_dict())
    return bdata


## Machines


@bp.route("/machines/<code>", methods=("GET", "POST", "DELETE"))
@encrypted
def machines_machine(code):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    machine = Machine.query.filter_by(code=code).first()
    if machine and session.user.id != machine.user.id:
        return ("Unauthorized", 401)
    if request.method == "GET":
        if not machine:
            return ("Not Found", 404)
        else:
            return pickle.dumps(machine.as_dict())
    elif request.method == "POST":
        if not machine:
            machine = Machine(user=session.user, code=code, name=args["name"])
            db.session.add(machine)
        machine.name = args["name"]
    elif request.method == "DELETE":
        if not machine:
            return ("Not Found", 404)
        else:
            db.session.delete(machine)
    db.session.commit()
    return ("Success", 200)


## Activations


@bp.route("/activations", methods=("POST",))
@encrypted
def activations_create():
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    license = License.query.filter_by(user=session.user, key=args["license"]).first()
    if not license:
        return ("Bad Request", 400)
    # exceeded max activations?
    if len(license.activations) >= license.policy.maxActivations:
        return ("Payment Required", 402)
    #
    machine = Machine.query.filter_by(code=args["machine"]).first()
    if not machine:
        machine = Machine(user=session.user, code=args["machine"], name=args["name"])
        db.session.add(machine)
    # already activated?
    activation = Activation.query.filter_by(license=license, machine=machine).first()
    if activation:
        return ("Conflict", 409)
    # do activation
    activation = Activation(license_id=license.id, machine_id=machine.id)
    db.session.add(activation)
    db.session.commit()
    _log.info(
        "Activated %s on `%s` for %s"
        % (license.policy.code, machine.name, session.user)
    )
    return ("Success", 200)


@bp.route("/activations/<id>", methods=("DELETE",))
@encrypted
def activations_activation(id):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    activation = Activation.query.get(id)
    if not activation:
        return ("Not Found", 404)
    if session.user.id != activation.license.user.id:
        return ("Unauthorized", 401)
    # do delete
    machine = activation.machine
    db.session.delete(activation)
    db.session.commit()
    _log.info(
        "Deactivated %s on `%s` for %s"
        % (activation.license.policy.code, machine.name, session.user)
    )
    return ("Success", 200)


@bp.route("/access_rights", methods=("POST",))
@bp.route("/access_rights/<int:id>", methods=("PATCH", "DELETE"))
@encrypted
def access_right(id=None):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)
    elif request.method == "POST":
        access_right = AccessRight(
            diagram_id=args["diagram_id"], user_id=args["user_id"], right=args["right"]
        )
        db.session.add(access_right)
    else:
        access_right = AccessRight.query.get(id)
        if not access_right:
            return ("Not Found", 404)
        elif request.method == "PATCH":
            access_right.update(**args)
        elif request.method == "DELETE":
            db.session.delete(access_right)
    db.session.commit()
    if request.method != "DELETE":
        db.session.refresh(access_right)
    return pickle.dumps(access_right.as_dict())


@bp.route("/copilot/chat", methods=["POST"])
@bp.route("/copilot/chat/<int:conversation_id>", methods=["POST", "DELETE"])
@encrypted
def copilot_chat(conversation_id: int = None):
    args = pickle.loads(request.data)
    session = Session.query.filter_by(token=args["session"]).first()
    if not session:
        return ("Unauthorized", 401)

    if not "question" in args:
        return ("The parameter 'question' is required", 400)

    events = [
        Event(
            dateTime=x["dateTime"],
            description=x["description"],
            people=x["people"],
            variables=x["variables"],
        )
        for x in args.get("events", [])
    ]

    response = current_app.engine.ask(args["question"], events, conversation_id)
    return pickle.dumps(
        {
            "conversation_id": conversation_id,
            "response": response.answer,
            "sources": response.sources,
        }
    )
