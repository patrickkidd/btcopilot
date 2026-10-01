"""Which model coaches one person; which models run each of their turns again
for comparison only [R-0596] is their own setting, shown here. With none set a
person gets the default model and no second run."""

import enum

import click

from btcopilot import shadow
from btcopilot.admin import setting
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.admin.users import find as find_user
from btcopilot.llmutil import MODEL_ALIASES, resolve_model
from btcopilot.models import User
from btcopilot.models.preferences import PrefKey


class Unset(enum.StrEnum):
    Default = "default"
    Off = "off"


@click.group("coach-model")
def coach_model():
    """The coach model and the shadow models of one person."""


def _row(user: User) -> dict:
    return {
        "email": user.username,
        "model": setting.read(SettingKey.CoachModel, user.id, Unset.Default.value),
        "shadow": list(user.pref(PrefKey.ShadowModels)) or Unset.Off.value,
    }


def _known(aliases: tuple[str, ...], unset: Unset | None) -> None:
    """Every alias names a model, or the word that clears the setting stands alone."""
    if unset and aliases == (unset,):
        return
    unknown = [alias for alias in aliases if alias not in MODEL_ALIASES]
    if unknown:
        alone = f", or {unset} alone" if unset else ""
        raise click.ClickException(
            f"unknown model {', '.join(unknown)}; "
            f"one of {', '.join(MODEL_ALIASES)}{alone}"
        )


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
    _known((alias,), Unset.Default)
    user = find_user(email)
    if alias == Unset.Default:
        setting.clear(SettingKey.CoachModel, user.id)
    else:
        setting.write(SettingKey.CoachModel, alias, user.id)
    return [_row(user)]


@writes
@coach_model.command("backfill")
@click.argument("email")
@click.argument("aliases", nargs=-1, required=True)
@click.option(
    "--yes", is_flag=True, help="Hand the turns over; without it, only the preview."
)
@rows_option
def coach_model_backfill(email, aliases, yes):
    """Run each of this person's past turns again on each model alias given, over
    the record as it stood before each turn. Makes model calls. Without --yes it
    prints, per model, the turns to run, the replies too old to run and what the
    run would cost, and writes nothing."""
    _known(aliases, None)
    user = find_user(email)
    if yes:
        return [
            {"model": alias, "turns_handed_over": shadow.backfill(user, alias)}
            for alias in aliases
        ]
    untraced = shadow.untraced(user)
    rows = []
    for alias in aliases:
        turns = shadow.pending(user, alias)
        usd, unpriced = shadow.estimate(turns, alias)
        rows.append(
            {
                "model": alias,
                "turns_to_run": len(turns),
                "replies_without_turn_id": untraced,
                "turns_without_token_counts": unpriced,
                "estimated_usd": round(usd, 2),
            }
        )
    return rows
