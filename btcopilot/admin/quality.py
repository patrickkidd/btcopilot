"""The quality dashboard's recorded runs, loaded by every release, and the
replay of a discussion on another model, scored."""

from decimal import Decimal
from pathlib import Path

import click
from flask import current_app

from btcopilot import diagramjson
from btcopilot import quality as runs
from btcopilot import replayscore
from btcopilot.admin.guard import writes
from btcopilot.coachmodel import COACH_EFFORT
from btcopilot.extensions import db
from btcopilot.llmutil import DEFAULT_RESPONSE_MODEL_ALIAS, MODEL_ALIASES, resolve_model
from btcopilot.models import Diagram, Discussion, User
from btcopilot.review.adapter import spoken

THINKING = ("low", "medium", "high")

PRODUCTION = "production"
MODEL_HELP = (
    f"MODEL is a model alias; the coach's own is {DEFAULT_RESPONSE_MODEL_ALIAS}."
)


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
    """What both replays take: a spending cap, a thinking level, alternative
    prompt files, a cap on turns, and leave to run on the box."""
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
                "--prompt-dir",
                type=click.Path(exists=True, file_okay=False, path_type=Path),
                help="A folder holding any of agent.prompty and fragments/*.md; "
                "each file there replaces the same-named prompt for this replay "
                "only, and the rest are read from the usual places.",
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
@quality.command(
    "replay",
    help="Replay a session's words on MODEL onto a scratch record, score it "
    "against the record Patrick corrected, and append one ledger line. It spends "
    f"on the model and writes scratch records. {MODEL_HELP}",
)
@click.argument("discussion_id", type=int)
@click.argument("model", type=click.Choice(sorted(MODEL_ALIASES)))
@click.argument("reference_diagram_id", type=int)
@replay_options
def quality_replay(
    discussion_id,
    model,
    reference_diagram_id,
    cap,
    thinking,
    prompt_dir,
    turns,
    production,
):
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
            prompt=prompt_dir,
            statements=statements,
        )
    )


@writes
@quality.command(
    "replay-person",
    help="Replay the words of the live coach turns one person took, oldest "
    "first, on MODEL onto one scratch record that starts as their record stood "
    "before the first, score it against their record as it stood after the "
    "last, and append one ledger line. A key the ledger already holds is not "
    f"run again. {MODEL_HELP}",
)
@click.argument("user_id", type=int)
@click.argument("model", type=click.Choice(sorted(MODEL_ALIASES)))
@click.option(
    "--reference",
    "reference_diagram_id",
    type=int,
    help="The diagram to score against; the person's record as it stood after "
    "the last replayed turn when left out.",
)
@click.option("--key", "show_key", is_flag=True, help="Print the key and stop.")
@click.option("--again", is_flag=True, help="Run a key the ledger already holds.")
@replay_options
def quality_replay_person(
    user_id,
    model,
    reference_diagram_id,
    show_key,
    again,
    cap,
    thinking,
    prompt_dir,
    turns,
    production,
):
    _allowed(production)
    user = db.session.get(User, user_id)
    if user is None:
        raise click.UsageError("no such user")
    every = replayscore.turned(user.id)
    statements = every[:turns]
    if not statements:
        raise click.UsageError("no turns with a turn id")
    diagram = statements[0].discussion.diagram
    if {s.discussion.diagram_id for s in statements} != {diagram.id}:
        raise click.UsageError("the turns lie on more than one record")
    following = every[len(statements)] if len(every) > len(statements) else None
    if following is not None and following.discussion.diagram_id != diagram.id:
        following = None
    start, before = replayscore.anchor(diagram, statements[0])
    end, after = replayscore.anchor(diagram, following)
    reference = db.session.get(Diagram, reference_diagram_id or diagram.id)
    if reference is None:
        raise click.UsageError("no such reference diagram")
    key = (
        f"person {user.id} turns {statements[0].turn_id}..{statements[-1].turn_id} "
        f"({len(statements)}) record v{before}..v{after} "
        f"prompt {replayscore.prompt_version(prompt_dir)} "
        f"model {resolve_model(model)} thinking {thinking}"
    )
    click.echo(f"key: {key}")
    if show_key:
        return
    if replayscore.kept(key) and not again:
        raise click.UsageError("the ledger already holds this key; --again runs it")
    _report(
        replayscore.replay(
            statements[0].discussion,
            model,
            reference,
            cap=cap,
            thinking=thinking,
            prompt=prompt_dir,
            statements=statements,
            start=start,
            expected=None if reference_diagram_id else diagramjson.loads(end),
            key=key,
        )
    )
