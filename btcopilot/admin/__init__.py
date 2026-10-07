"""The admin command line. There is no admin web app: an agent runs this on
the engine, and the skill file it reads is generated from the commands
themselves (T-11)."""

import click

from btcopilot.admin.casereport import case_report_group
from btcopilot.admin.catchup import catch_up
from btcopilot.admin.coachmodels import coach_model
from btcopilot.admin.database import database
from btcopilot.admin.dates import dates
from btcopilot.admin.diagrams import diagrams
from btcopilot.admin.guard import run
from btcopilot.admin.imports import imports
from btcopilot.admin.licences import licences
from btcopilot.admin.notices import notice_group
from btcopilot.admin.observations import observations
from btcopilot.admin.proactive import proactive_group
from btcopilot.admin.quality import quality
from btcopilot.admin.questions import impressions_group, questions_group
from btcopilot.admin.regroup import regroup
from btcopilot.admin.reports import report_group
from btcopilot.admin.review import review
from btcopilot.admin.skill import write_skill
from btcopilot.admin.titles import titles_group
from btcopilot.admin.tokens import token_cap
from btcopilot.admin.users import users


@click.group("admin")
def admin():
    """Run the site: accounts, licences, records, imports, caps and the
    coding meeting."""


for group in (
    users,
    licences,
    diagrams,
    observations,
    notice_group,
    proactive_group,
    quality,
    questions_group,
    impressions_group,
    titles_group,
    report_group,
    case_report_group,
    imports,
    token_cap,
    coach_model,
    review,
    database,
    write_skill,
    run,
):
    admin.add_command(group)


questions_group.add_command(catch_up)
diagrams.add_command(regroup)
diagrams.add_command(dates)


def init_app(app):
    app.cli.add_command(admin)
