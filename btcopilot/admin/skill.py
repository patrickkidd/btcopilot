"""The skill file an agent reads before running this command line, written
from the commands' own declarations so the two can never drift."""

import pathlib

import click

PATH = pathlib.Path(__file__).parents[2] / ".claude/skills/fd-admin/SKILL.md"

HEADER = """---
name: fd-admin
description: Run the Family Diagram site from the command line — accounts, licences, family records, the one-time import of the old Pro database, monthly coach caps, and the coding meeting. Use when asked to look up or change anything on the running site.
---

# Running the site from the command line

There is no admin web page. Everything below is run on the engine, from the
repository, as `flask admin ...`.

Every command prints a table. Add `--json` to any of them to get the same rows
as JSON, which is what to use when the answer is going to be read by a program.
A command that changes something prints the row it changed.

This file is generated from the commands themselves by `flask admin skill`. Do
not edit it by hand; change the commands and generate it again.

## The commands
"""


def render(group: click.Group, name: str = "flask admin") -> str:
    """The whole file, the same bytes every time for the same commands."""
    return HEADER + "".join(_section(*one) for one in _walk(group, name))


def _walk(group: click.Group, path: str):
    context = click.Context(group, info_name=path)
    for command_name in sorted(group.commands):
        command = group.commands[command_name]
        line = f"{path} {command_name}"
        if isinstance(command, click.Group):
            yield line, command, context
            yield from _walk(command, line)
        else:
            yield line, command, context


def _section(path: str, command: click.Command, parent: click.Context) -> str:
    context = click.Context(command, parent=parent, info_name=path)
    heading = f"{path} {_usage(command)}".rstrip()
    lines = [f"\n### `{heading}`\n"]
    lines.append(f"\n{_help(command)}\n")
    rows = [_param(param) for param in command.get_params(context) if _named(param)]
    if rows:
        lines.append("\n| Argument | What it is |\n|---|---|\n")
        lines.extend(f"| `{name}` | {text} |\n" for name, text in rows)
    return "".join(lines)


def _usage(command: click.Command) -> str:
    parts = []
    for param in command.get_params(click.Context(command)):
        if isinstance(param, click.Argument):
            parts.append(
                f"<{param.name}>" if param.required else f"[{param.name}]"
            )
    return " ".join(parts)


def _named(param: click.Parameter) -> bool:
    return param.name not in ("help", "yes")


def _help(command: click.Command) -> str:
    text = (command.help or command.short_help or "").strip()
    return " ".join(text.split())


def _param(param: click.Parameter) -> tuple[str, str]:
    if isinstance(param, click.Argument):
        return param.name, "required" if param.required else "optional"
    return (
        ", ".join(param.opts),
        " ".join((param.help or "").split()) or "flag",
    )


@click.command("skill")
@click.option(
    "--check",
    is_flag=True,
    help="Fail if the file on disk is not what the commands say.",
)
@click.option("--out", type=click.Path(dir_okay=False), help="Write somewhere else.")
def write_skill(check, out):
    """Write the skill file an agent reads before running these commands."""
    from btcopilot.admin import admin

    text = render(admin)
    path = pathlib.Path(out) if out else PATH
    if check:
        if not path.exists() or path.read_text() != text:
            raise click.ClickException(
                f"{path} is not what the commands say; run: flask admin skill"
            )
        click.echo(f"{path} is current")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    click.echo(f"wrote {path}")
