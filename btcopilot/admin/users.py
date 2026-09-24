"""Who has an account, what they are allowed to do, and a link that signs
somebody in for the first time."""

import click
from flask import current_app

import btcopilot
from btcopilot.admin.output import rows_option
from btcopilot.auth.emails import send_invitation
from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.licence import professional
from btcopilot.models import User
from btcopilot.admin.guard import writes

ROLES = (btcopilot.ROLE_SUBSCRIBER, btcopilot.ROLE_AUDITOR, btcopilot.ROLE_ADMIN)


def find(email: str) -> User:
    user = User.query.filter_by(username=email.strip().lower()).first()
    if user is None:
        raise click.ClickException(f"no account for {email}")
    return user


def row(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.username,
        "name": f"{user.first_name} {user.last_name}".strip(),
        "roles": user.roles or "",
        "active": user.active,
        "professional": professional(user),
        "diagrams": len(user.diagrams),
    }


@click.group()
def users():
    """The people with accounts."""


@users.command("list")
@click.option("--role", type=click.Choice(ROLES), help="Only people with this role.")
@click.option("--email", help="Only addresses containing this text.")
@rows_option
def user_list(role, email):
    """Every account, one line each."""
    query = User.query.order_by(User.id)
    if email:
        query = query.filter(User.username.contains(email.strip().lower()))
    people = [user for user in query.all() if role is None or user.has_role(role)]
    return [row(user) for user in people]


@users.command("show")
@click.argument("email")
@rows_option
def user_show(email):
    """One account in full, with the licences and diagrams it owns."""
    user = find(email)
    data = row(user)
    data["licences"] = [licence.key for licence in user.licenses]
    data["diagram_ids"] = [diagram.id for diagram in user.diagrams]
    return [data]


@writes
@users.command("roles")
@click.argument("email")
@click.argument("roles", nargs=-1, type=click.Choice(ROLES))
@rows_option
def user_roles(email, roles):
    """Show somebody's roles, or set them to the roles named."""
    user = find(email)
    if roles:
        user.roles = ",".join(dict.fromkeys(roles))
        db.session.commit()
    return [{"email": user.username, "roles": user.roles or ""}]


@writes
@users.command("invite")
@click.argument("email")
@click.option("--base-url", help="Overrides the site address the link points at.")
@click.option("--send", is_flag=True, help="Also email the link to the address.")
@rows_option
def user_invite(email, base_url, send):
    """A one-time sign-in link, which also creates the account on first use."""
    address = email.strip().lower()
    invitation = Invitation.issue(address, current_app.config["INVITATION_DAYS"])
    base = (base_url or current_app.config["SITE_URL"]).rstrip("/")
    url = f"{base}/app/invite/{invitation.token}"
    if send:
        send_invitation(address, url)
    return [
        {
            "email": address,
            "url": url,
            "sent": send,
            "expires_at": invitation.expires_at,
        }
    ]
