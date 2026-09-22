"""What somebody has bought: give it, take it away, and see who holds what."""

import datetime

import click

from btcopilot.admin.users import find as find_user
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.pro.models import License, Policy
from btcopilot.admin.guard import writes


def row(licence: License) -> dict:
    return {
        "key": licence.key,
        "plan": licence.policy.code,
        "email": licence.user.username if licence.user else "",
        "status": licence.status().value,
        "activated_at": licence.activated_at,
        "canceled_at": licence.canceled_at,
    }


def find(key: str) -> License:
    licence = License.query.filter_by(key=key).first()
    if licence is None:
        raise click.ClickException(f"no licence with key {key}")
    return licence


@click.group()
def licences():
    """What people have bought."""


@licences.command("list")
@click.option("--email", help="Only the licences one person holds.")
@click.option("--plan", help="Only this plan's licences.")
@rows_option
def licence_list(email, plan):
    """Every licence, one line each."""
    query = License.query.order_by(License.id)
    if email:
        query = query.filter_by(user_id=find_user(email).id)
    if plan:
        query = query.join(Policy).filter(Policy.code == plan)
    return [row(licence) for licence in query.all()]


@writes
@licences.command("grant")
@click.argument("email")
@click.argument("plan")
@rows_option
def licence_grant(email, plan):
    """Give somebody a licence on the plan named."""
    user = find_user(email)
    policy = Policy.query.filter_by(code=plan).first()
    if policy is None:
        raise click.ClickException(f"no plan with code {plan}")
    licence = License(
        policy=policy,
        user=user,
        active=True,
        activated_at=datetime.datetime.utcnow(),
    )
    db.session.add(licence)
    db.session.commit()
    return [row(licence)]


@writes
@licences.command("revoke")
@click.argument("key")
@rows_option
def licence_revoke(key):
    """Turn a licence off, which stops the app it unlocks."""
    licence = find(key)
    licence.active = False
    db.session.commit()
    return [row(licence)]


@licences.command("plans")
@rows_option
def licence_plans():
    """The plans a licence can be granted on."""
    return [
        {
            "code": policy.code,
            "name": policy.name,
            "amount": policy.amount,
            "interval": policy.interval,
            "active": policy.active,
        }
        for policy in Policy.query.order_by(Policy.code).all()
    ]
