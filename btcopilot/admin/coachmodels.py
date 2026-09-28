"""Which model coaches one person, and which model runs each of their turns
again for comparison only [R-0596]. With none set a person gets the default
model and no second run."""

import enum

import click

from btcopilot.admin import setting
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.admin.users import find as find_user
from btcopilot.llmutil import MODEL_ALIASES, resolve_model
from btcopilot.models import User


class Unset(enum.StrEnum):
    Default = "default"
    Off = "off"


@click.group("coach-model")
def coach_model():
    """The coach model and the shadow model of one person."""


def _row(user: User) -> dict:
    return {
        "email": user.username,
        "model": setting.read(SettingKey.CoachModel, user.id, Unset.Default.value),
        "shadow": setting.read(SettingKey.ShadowModel, user.id, Unset.Off.value),
    }


def _put(key: SettingKey, email: str, alias: str, unset: Unset) -> None:
    user = find_user(email)
    if alias == unset:
        setting.clear(key, user.id)
        return
    if alias not in MODEL_ALIASES:
        raise click.ClickException(
            f"unknown model {alias}; one of {', '.join(MODEL_ALIASES)} or {unset}"
        )
    setting.write(key, alias, user.id)


@coach_model.command("show")
@click.argument("email", required=False)
@rows_option
def coach_model_show(email):
    """One person's models, or the default and everyone who differs from it."""
    if email:
        return [_row(find_user(email))]
    rows = [
        {
            "email": Unset.Default.value,
            "model": resolve_model(None),
            "shadow": Unset.Off.value,
        }
    ]
    for user in User.query.order_by(User.id).all():
        row = _row(user)
        if row["model"] != Unset.Default or row["shadow"] != Unset.Off:
            rows.append(row)
    return rows


@writes
@coach_model.command("set")
@click.argument("email")
@click.argument("alias")
@rows_option
def coach_model_set(email, alias):
    """Coach this person on a model alias, or on the default with the word default."""
    _put(SettingKey.CoachModel, email, alias, Unset.Default)
    return [_row(find_user(email))]


@writes
@coach_model.command("shadow")
@click.argument("email")
@click.argument("alias")
@rows_option
def coach_model_shadow(email, alias):
    """Run each of this person's turns again on a model alias, never shown to
    them and never charged to them; the word off stops it."""
    _put(SettingKey.ShadowModel, email, alias, Unset.Off)
    return [_row(find_user(email))]
