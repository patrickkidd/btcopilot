"""How much of the coach one person may use in a month. The meter that counts
what they have spent is step 14's work; this is the cap it will read."""

import click

from btcopilot.admin import setting
from btcopilot.admin.users import find as find_user
from btcopilot.admin.output import rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.models import User
from btcopilot.admin.guard import writes

#: The cap for anyone with no cap of their own.
DEFAULT = "default"


@click.group("token-cap")
def token_cap():
    """The monthly ceiling on coach use."""


@token_cap.command("show")
@click.argument("email", required=False)
@rows_option
def token_cap_show(email):
    """The cap for one person, or the default and everyone who differs from it."""
    fallback = setting.read(SettingKey.TokenCap)
    if email:
        user = find_user(email)
        own = setting.read(SettingKey.TokenCap, user.id)
        return [
            {
                "email": user.username,
                "cap": fallback if own is None else own,
                "source": DEFAULT if own is None else "their own",
            }
        ]
    rows = [{"email": DEFAULT, "cap": fallback, "source": DEFAULT}]
    for user in User.query.order_by(User.id).all():
        own = setting.read(SettingKey.TokenCap, user.id)
        if own is not None:
            rows.append({"email": user.username, "cap": own, "source": "their own"})
    return rows


@writes
@token_cap.command("set")
@click.argument("email")
@click.argument("tokens", type=int)
@rows_option
def token_cap_set(email, tokens):
    """Set the cap, in tokens a month. Use the word default for everyone else."""
    if tokens < 0:
        raise click.ClickException("a cap cannot be below zero")
    scope = None if email == DEFAULT else find_user(email).id
    setting.write(SettingKey.TokenCap, tokens, scope)
    return [{"email": email, "cap": tokens}]
