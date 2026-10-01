"""The quality dashboard's recorded runs, loaded by every release, and the
replay of a discussion on another model, scored."""

import datetime
from decimal import Decimal
from pathlib import Path

import click
from flask import current_app
from sqlalchemy import func

from btcopilot import diagramjson
from btcopilot import quality as runs
from btcopilot import replayscore
from btcopilot.admin.guard import writes
from btcopilot.coachmodel import COACH_EFFORT
from btcopilot.extensions import db
from btcopilot.llmutil import DEFAULT_RESPONSE_MODEL_ALIAS, MODEL_ALIASES, resolve_model
from btcopilot.models import Diagram, Discussion, ReplayPass, User
from btcopilot.models.qualityrun import Source
from btcopilot.models.replaypass import PARTS
from btcopilot.review.adapter import spoken

THINKING = ("low", "medium", "high")

# The replays of Patrick's first eight turns kept before the replay passes
# table existed, from the summaries the replay printed; their release was not
# recorded, and the Sonnet pass ran on a copy of the database.
KEPT_2026_09_30 = (
    (
        "claude-opus-5-5",
        "low",
        "406f08b6a3e2",
        19,
        (54, 36388, 417194, 6951),
        "0.4046",
        (1.0, 0.75, 1.0, 1.0, 0.49),
        71,
    ),
    (
        "claude-opus-5-5",
        "medium",
        "bb63094b9366",
        22,
        (62, 60037, 475849, 10226),
        "0.6001",
        (1.0, 0.55, 1.0, 1.0, 0.70),
        72,
    ),
    (
        "gemini-3.1-pro-preview",
        "medium",
        "406f08b6a3e2",
        24,
        (107615, 0, 335346, 10669),
        "0.4103",
        (1.0, 0.60, 1.0, 1.0, 1.0),
        73,
    ),
    (
        "claude-opus-5-5",
        "medium",
        "406f08b6a3e2",
        23,
        (64, 57869, 494852, 8993),
        "0.568431",
        (1.0, 0.55, 1.0, 1.0, 0.60),
        76,
    ),
    (
        "claude-sonnet-5-5",
        "medium",
        "87a9f0968e1b",
        26,
        (8286, 38466, 487374, 11393),
        "0.2757",
        (1.0, 0.57, 1.0, 1.0, 1.0),
        None,
    ),
)
KEPT_CASE = "person 1 statements 6..28 (8) record v1..v13"

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


@writes
@quality.command("keep-passes")
def quality_keep_passes():
    """Keep the replays of 2026-09-30 in the replay passes table."""
    for (
        model,
        thinking,
        prompt,
        calls,
        tokens,
        cost,
        scores,
        scratch,
    ) in KEPT_2026_09_30:
        parts = dict(zip(PARTS, scores))
        db.session.add(
            ReplayPass(
                model=model,
                thinking=thinking,
                prompt=prompt,
                case=KEPT_CASE,
                turns=8,
                calls=calls,
                input_tokens=tokens[0],
                cache_creation_tokens=tokens[1],
                cache_read_tokens=tokens[2],
                output_tokens=tokens[3],
                cost_usd=Decimal(cost),
                **parts,
                overall=ReplayPass.overall_of(parts),
                source=Source.Api,
                scratch_diagram_id=scratch,
                created_at=datetime.datetime(2026, 9, 30),
            )
        )
    db.session.commit()
    click.echo(f"{len(KEPT_2026_09_30)} passes kept")


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
                "--turns", type=click.IntRange(min=1), help="The last turn replayed."
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
    "last, keep the pass and append one ledger line. A key a kept pass already "
    f"holds is not run again. {MODEL_HELP}",
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
@click.option(
    "--key",
    "show_key",
    is_flag=True,
    help="Print the key and the passes kept under it, and stop.",
)
@click.option("--again", is_flag=True, help="Run a key a kept pass already holds.")
@click.option(
    "--start",
    type=click.IntRange(min=2),
    help="Begin at this turn, going on in the scratch session and record of "
    "the kept pass --after names, which replayed every turn before it.",
)
@click.option("--after", "after_id", type=int, help="The kept pass to go on from.")
@replay_options
def quality_replay_person(
    user_id,
    model,
    reference_diagram_id,
    show_key,
    again,
    start,
    after_id,
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
    prior = db.session.get(ReplayPass, after_id) if after_id else None
    if (start is None) != (prior is None):
        raise click.UsageError("--start and --after go together, on a kept pass")
    if prior is not None:
        done = (
            db.session.query(func.sum(ReplayPass.turns))
            .filter(
                ReplayPass.scratch_diagram_id == prior.scratch_diagram_id,
                ReplayPass.id <= prior.id,
            )
            .scalar()
        )
        if done != start - 1:
            raise click.UsageError(
                f"pass {prior.id} and those before it on its record replayed "
                f"{done} turns, not {start - 1}"
            )
    statements = every[(start or 1) - 1 : turns]
    if not statements:
        raise click.UsageError("no turns with a turn id")
    diagram = statements[0].discussion.diagram
    if {s.discussion.diagram_id for s in statements} != {diagram.id}:
        raise click.UsageError("the turns lie on more than one record")
    following = every[len(statements)] if len(every) > len(statements) else None
    if following is not None and following.discussion.diagram_id != diagram.id:
        following = None
    begun, before = replayscore.anchor(diagram, statements[0])
    end, after = replayscore.anchor(diagram, following)
    reference = db.session.get(Diagram, reference_diagram_id or diagram.id)
    if reference is None:
        raise click.UsageError("no such reference diagram")
    case = (
        f"person {user.id} statements {statements[0].id}..{statements[-1].id} "
        f"({len(statements)}) record v{before}..v{after}"
    )
    key = (case, replayscore.prompt_version(prompt_dir), resolve_model(model), thinking)
    found = replayscore.kept(*key)
    click.echo(f"key: {ReplayPass.key_of(*key)}")
    if show_key:
        for one in found:
            click.echo(
                f"  kept {one.created_at:%Y-%m-%d} release {one.release or '-'}: "
                f"{one.turns} turns, {one.calls} calls, ${one.cost_usd:.4f}, "
                f"overall {'-' if one.overall is None else one.overall}"
            )
        return
    if found and not again:
        raise click.UsageError("a pass is already kept under this key; --again runs it")
    _report(
        replayscore.replay(
            statements[0].discussion,
            model,
            reference,
            cap=cap,
            thinking=thinking,
            prompt=prompt_dir,
            statements=statements,
            start=begun,
            after=prior,
            expected=None if reference_diagram_id else diagramjson.loads(end),
            case=case,
        )
    )
