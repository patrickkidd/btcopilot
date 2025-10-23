import logging
import click
import datetime

from flask import current_app, Blueprint

import vedana
from btcopilot.extensions import db, ensure_stripe_Plan, sync_with_stripe
from btcopilot.pro import tasks, SESSION_EXPIRATION_DAYS
from btcopilot.pro.routes import bp
from btcopilot.pro.models import License, Policy, Session, User


_log = logging.getLogger(__name__)


def init_app(app):
    app.register_blueprint(bp)
    app.cli.add_command(tasks.ingest)
    # _log.info("Updating license policies...")

    # with app.app_context():
    #     update_policies()
    # _log.info("Finished updating license policies.")


# @bp.cli.command("drop-all")
# def drop_all():
#     _log.info("Dropping all tables...")
#     db.session.commit()  # hangs for some reason
#     db.drop_all()


@bp.cli.command("create-alpha-license")
def create_alpha_license():
    policies = Policy.query.filter_by(code=vedana.LICENSE_ALPHA)
    if policies.count() == 0:
        _log.info(
            "Policy %s not found (run flask update-policies?)" % vedana.LICENSE_ALPHA
        )
        return
    policy = policies.first()
    license = License(policy=policy)
    db.session.add(license)
    db.session.commit()
    _log.info(f"Added alpha license: {license.key}")


@bp.cli.command("create-beta-license")
def create_beta_license():
    policies = Policy.query.filter_by(code=vedana.LICENSE_BETA)
    if policies.count() == 0:
        _log.info(
            "Policy %s not found (run flask update-policies?)" % vedana.LICENSE_BETA
        )
        return
    policy = policies.first()
    license = License(policy=policy)
    db.session.add(license)
    db.session.commit()
    _log.info(f"Added beta license: {license.key}")


@bp.cli.command("create-professional-annual-license")
def create_professional_annual_license():
    policies = Policy.query.filter_by(code=vedana.LICENSE_PROFESSIONAL_ANNUAL)
    if policies.count() == 0:
        _log.info(
            "Policy %s not found (run flask update-policies?)"
            % vedana.LICENSE_PROFESSIONAL_ANNUAL
        )
        return
    policy = policies.first()
    license = License(policy=policy)
    db.session.add(license)
    db.session.commit()
    _log.info(f"Added professional monthly license: {license.key}")


@bp.cli.command("create-client-license")
def create_client_annual_license():
    policies = Policy.query.filter_by(code=vedana.LICENSE_CLIENT_ONCE)
    if policies.count() == 0:
        _log.info(
            "Policy %s not found (run flask update-policies?)"
            % vedana.LICENSE_CLIENT_ONCE
        )
        return
    policy = policies.first()
    license = License(policy=policy)
    db.session.add(license)
    db.session.commit()
    _log.info(f"Added client license: {license.key}")


def update_policies():
    policies = Policy.query.all()
    for entry in Policy.POLICIES:
        policy = None
        for p in policies:
            if p.code == entry["code"]:
                policy = p
        if policy:
            _log.info(f"Updating Policy: {entry['code']}")
            policy.update(synchronize_session=False, **entry)

        else:
            _log.info(f"Creating Policy: {entry['code']}")
            policy = Policy(**entry)
            db.session.add(policy)

        ## Stripe Product + Plan
        if current_app.config["STRIPE_ENABLED"] and policy.public:
            stripe_plan = ensure_stripe_Plan(policy)

    db.session.commit()


@bp.cli.command("update-policies")
def _update_policies():
    update_policies()


@bp.cli.command("list-unclaimed-licenses")
def list_unclaimed_licenses():
    print("Unclaimed licenses:")
    for license in License.query.filter_by(user_id=None):
        print("Has unclaimed license: %s :: %s" % (license.key, license.policy.name))


@bp.cli.command("list-users")
def list_users():
    print("Listing all Users:")
    for user in User.query.all():
        print("%s" % user)
        for license in user.licenses:
            print("    %s" % license)
            for activation in license.activations:
                print("        %s" % activation)


@bp.cli.command("set-user-roles")
@click.argument("username")
@click.argument("roles")
def set_user_roles(username, roles):
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f"Cannot find user: {username}", err=True)
        return 1
    for role in roles.split(","):
        if not role in (vedana.ROLE_SUBSCRIBER, vedana.ROLE_ADMIN, vedana.ROLE_AUDITOR):
            click.echo(f"Invalid role: {role}")
            return 1
    user.roles = roles
    db.session.commit()
    click.echo("Set user %s roles to %s" % (username, roles), err=True)


@bp.cli.command("set-user-password")
@click.argument("username")
@click.argument("password")
def set_user_password(username, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f"Cannot find user: {username}", err=True)
        return 1
    user.set_password(password)
    db.session.commit()
    click.echo(f"Set user {username} password {password}")


@bp.cli.command("sync-with-stripe")
def _sync_with_stripe():
    sync_with_stripe()


@bp.cli.command("expire-license")
@click.argument("key")
def expire_license(key):
    license = License.query.filter_by(key=key).first()
    if not license:
        _log.info(f"Cannot find license: {key}")
    elif not license.active:
        _log.info("License already expired.")
    else:
        license.active = False
        db.session.commit()
        _log.info(f"Expired license: {key}")


def _expire_stale_sessions():
    _log.info("Starting...")
    for session in Session.query.all():
        if (
            datetime.datetime.utcnow() - session.updated_at
        ).days >= SESSION_EXPIRATION_DAYS:
            db.session.delete(session)
    db.session.commit()
    _log.info("Done.")


@bp.cli.command("expire-stale-sessions")
def expire_stale_sessions():
    _expire_stale_sessions()


#################################
##  Scratch
#################################

# if not app.config['TESTING']:

# # test user

# test_user = User.query.filter_by(username='patrickkidd@gmail.com').first()
# if not test_user:
#     _log.info('Adding test user: patrickkidd@gmail.com:abc123')
#     test_user = User(username='patrickkidd@gmail.com', password='abc123')
#     db.session.add(test_user)

# db.session.commit()

# unclaimed licenses

# try:
#     maxUnclaimed = len(UNCLAIMED_LICENSES)
#     lastIndex = 0
#     n = License.query.filter_by(user_id=None).count()
#     while License.query.filter_by(user_id=None).count() < maxUnclaimed:
#         entry = UNCLAIMED_LICENSES[lastIndex]
#         _log.info('Adding unclaimed license: %s' % entry['policy'])
#         policy = Policy.query.filter_by(code=entry['policy']).first()
#         license = License(policy=policy)
#         db.session.add(license)
#         lastIndex += 1
# except Exception as e:
#     import traceback, sys
#     traceback.print_exc(file=sys.stderr)
