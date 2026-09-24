"""The admin command line. There is no admin web app: an agent runs this on
the engine, and the skill file it reads is generated from the commands
themselves (T-11)."""

import click

from btcopilot.admin.database import database
from btcopilot.admin.diagrams import diagrams
from btcopilot.admin.guard import run
from btcopilot.admin.imports import imports
from btcopilot.admin.licences import licences
from btcopilot.admin.observations import observations
from btcopilot.admin.review import review
from btcopilot.admin.skill import write_skill
from btcopilot.admin.tokens import token_cap
from btcopilot.admin.users import users


@click.group("admin")
def admin():
    """Run the site: accounts, licences, records, imports, caps and the
    coding meeting."""


for group in (users, licences, diagrams, observations, imports, token_cap, review, database, write_skill, run):
    admin.add_command(group)


def init_app(app):
    app.cli.add_command(admin)
