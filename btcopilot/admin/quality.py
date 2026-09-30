"""The quality dashboard's recorded runs, loaded by every release, and the
replay of a discussion on another model, scored."""

from decimal import Decimal
from pathlib import Path

import click
from flask import current_app

from btcopilot import quality as runs
from btcopilot import replayscore
from btcopilot.admin.guard import writes
from btcopilot.coachmodel import COACH_EFFORT
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, User
from btcopilot.review.adapter import spoken

THINKING = ("low", "medium", "high")

PRODUCTION = "production"


@click.group()
def quality():
    """The recorded runs the quality dashboard reads."""


@writes
@quality.command("load")
@click.argument(
    "root", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
def quality_load(root):
    """Load every recorded run under a checkout or the image into the table,
    updating the ones already there."""
    click.echo(f"{runs.load(root)} values loaded")


def replay_options(command):
    """What both replays take: a spending cap, a thinking level, an
    alternative main prompt, a cap on turns, and leave to run on the box."""
    for option in reversed(
        [
            click.option(
                "--cap",
                type=Decimal,
                default=Decimal(5),
                show_default=True,
                help="Dollars; no turn starts past it.",
            ),
            click.option(
                "--thinking",
                type=click.Choice(THINKING),
                default=COACH_EFFORT,
                show_default=True,
                help="How hard the coach thinks, for this replay only.",
            ),
            click.option(
                "--prompt-file",
                type=click.Path(exists=True, dir_okay=False, path_type=Path),
                help="A plain prompty file that replaces the coach's main prompt "
                "for this replay only.",
            ),
            click.option(
                "--turns", type=click.IntRange(min=1), help="At most this many turns."
            ),
            click.option(
                "--production",
                is_flag=True,
                help="Run on the production database: Patrick agreed the spend.",
            ),
        ]
    ):
        command = option(command)
    return command


def _allowed(production: bool):
    if current_app.config["CONFIG"] == PRODUCTION and not production:
        raise click.UsageError(
            "replays run in the sandbox; on production only with --production"
        )


def _report(row: dict):
    turns = row["turns"]
    tokens = row["tokens"]
    click.echo(
        f"{row['requested']} as {row['model']}: {turns} turns, {row['calls']} model calls, "
        f"{row['calls'] / turns if turns else 0:.1f} calls a turn, ${row['cost']:.4f}"
    )
    click.echo(
        f"tokens: {tokens['input']} input, {tokens['cache_creation']} cache write, "
        f"{tokens['cache_read']} cache read, {tokens['output']} output"
    )
    click.echo(
        f"scratch diagram {row['scratch_diagram_id']}, session {row['scratch_discussion_id']}"
    )
    for part in ("scores", "faults"):
        for name, value in row[part].items():
            click.echo(f"  {name:<18} {'-' if value is None else value}")
    click.echo("turn ids, replayed from -> replay:")
    for source, copy in row["pairs"]:
        click.echo(f"  {source or '-'} -> {copy}")


@writes
@quality.command("replay")
@click.argument("discussion_id", type=int)
@click.argument("model")
@click.argument("reference_diagram_id", type=int)
@replay_options
def quality_replay(
    discussion_id,
    model,
    reference_diagram_id,
    cap,
    thinking,
    prompt_file,
    turns,
    production,
):
    """Replay a session's words on MODEL onto a scratch record, score it
    against the record Patrick corrected, and append one ledger line. It spends
    on the model and writes scratch records."""
    _allowed(production)
    discussion = db.session.get(Discussion, discussion_id)
    reference = db.session.get(Diagram, reference_diagram_id)
    if discussion is None or reference is None:
        raise click.UsageError("no such session or reference diagram")
    ordered = sorted(discussion.statements, key=lambda s: (s.order or 0, s.id))
    statements = spoken(ordered)[:turns]
    _report(
        replayscore.replay(
            discussion,
            model,
            reference,
            cap=cap,
            thinking=thinking,
            prompt=prompt_file,
            statements=statements,
        )
    )


@writes
@quality.command("replay-person")
@click.argument("user_id", type=int)
@click.argument("model")
@click.option(
    "--reference",
    "reference_diagram_id",
    type=int,
    help="The diagram to score against; the person's own record when left out.",
)
@replay_options
def quality_replay_person(
    user_id, model, reference_diagram_id, cap, thinking, prompt_file, turns, production
):
    """Replay the words of every live coach turn one person took, oldest
    first, on MODEL onto one scratch record, score it against their record, and
    append one ledger line."""
    _allowed(production)
    user = db.session.get(User, user_id)
    if user is None:
        raise click.UsageError("no such user")
    reference = db.session.get(Diagram, reference_diagram_id or user.diagram_in_use())
    statements = replayscore.turned(user.id, turns)
    if reference is None or not statements:
        raise click.UsageError("no reference diagram or no turns with a turn id")
    _report(
        replayscore.replay(
            statements[0].discussion,
            model,
            reference,
            cap=cap,
            thinking=thinking,
            prompt=prompt_file,
            statements=statements,
        )
    )
