"""The one door an assistant uses: reads run at once, a command that changes
something shows its preview and runs only with --yes."""

import shlex

import click


def writes(command: click.Command) -> click.Command:
    command.writes = True
    return command


def marked(command: click.Command) -> bool:
    return getattr(command, "writes", False)


@click.command(
    "run", context_settings={"ignore_unknown_options": True, "help_option_names": []}
)
@click.argument("words", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(context, words):
    """Run an admin command given after --. One that changes something needs
    --yes; without it the preview is printed and nothing runs."""
    group = context.parent.command
    confirmed = "--yes" in words
    words = [word for word in words if word != "--yes"]
    parent = click.Context(group, info_name="flask admin")
    command, rest = group, words
    path = []
    try:
        while isinstance(command, click.Group) and rest:
            name, command, rest = command.resolve_command(parent, rest)
            path.append(name)
            parent = click.Context(command, parent=parent, info_name=name)
    except click.UsageError as error:
        click.echo(f"error: {error.message}", err=True)
        context.exit(2)
    if command is run:
        click.echo("error: run cannot run itself", err=True)
        context.exit(2)
    params = {param.name for param in command.params}
    if "as_json" in params and "--json" not in rest:
        rest = [*rest, "--json"]
    if "yes" in params and confirmed:
        rest = [*rest, "--yes"]
    args = [*path, *rest]
    if marked(command) and not confirmed:
        click.echo(f"preview: {shlex.join(['flask', 'admin', *args])}")
        click.echo(command.get_help(parent))
        context.exit(3)
    group.main(args, prog_name="flask admin", standalone_mode=False)
