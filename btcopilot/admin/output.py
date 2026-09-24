"""One shape for every admin answer: named columns over rows, printed as a
table a person reads or as JSON an agent reads."""

import datetime
import functools
import json

import click


def rows_option(fn):
    """Adds --json and prints whatever the command returns: a list of rows, or
    a (columns, rows) pair when the column order is not the first row's."""

    @click.option("--json", "as_json", is_flag=True, help="Print JSON, not a table.")
    @functools.wraps(fn)
    def wrapper(*args, as_json: bool = False, **kwargs):
        result = fn(*args, **kwargs)
        columns, rows = result if isinstance(result, tuple) else (None, result)
        emit(rows, columns, as_json)

    return wrapper


def emit(rows: list[dict], columns: list[str] | None, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(rows, indent=2, default=_plain))
        return
    if not rows:
        click.echo("nothing to show")
        return
    columns = columns or list(rows[0])
    cells = [[_text(row.get(name)) for name in columns] for row in rows]
    widths = [
        max(len(name), *(len(cell[i]) for cell in cells))
        for i, name in enumerate(columns)
    ]
    click.echo("  ".join(name.ljust(widths[i]) for i, name in enumerate(columns)))
    click.echo("  ".join("-" * width for width in widths))
    for cell in cells:
        click.echo("  ".join(cell[i].ljust(widths[i]) for i in range(len(columns))))


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(one) for one in value)
    return str(value)


def _plain(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON")
