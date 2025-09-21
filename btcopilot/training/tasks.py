import logging
import datetime
import asyncio
from datetime import timedelta

import click
from sqlalchemy import create_engine
from flask import current_app

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.training.routes.discussions import (
    extract_next_statement as _extract_next_statement,
)


_log = logging.getLogger(__name__)


def extract_next_statement():
    """Background task to extract data from the oldest pending Subject statement"""

    _log.info(f"extract_next_statement() called")

    try:
        # Ensure we have a database connection
        try:
            db.session.get_bind()
        except:
            engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
            db.session.bind = engine

        result = _extract_next_statement()

        # If there are more statements to process, schedule another task
        if result:
            # Schedule next extraction with 1 second delay
            from btcopilot.extensions import celery

            celery.send_task("extract_next_statement", countdown=1)

        return result

    except Exception as e:
        _log.error(f"Error in extract_next_statement task: {e}", exc_info=True)
        return False


def extract_discussion_statements(discussion_id: int):
    """Trigger extraction for a specific discussion"""

    try:
        discussion = Discussion.query.get(discussion_id)
        if not discussion:
            _log.error(f"Discussion {discussion_id} not found")
            return False

        discussion.extracting = True
        db.session.commit()

        # Start the extraction process
        from btcopilot.extensions import celery

        celery.send_task("extract_next_statement")

        _log.info(f"Started extraction for discussion {discussion_id}")
        return True

    except Exception as e:
        _log.error(
            f"Error starting extraction for discussion {discussion_id}: {e}",
            exc_info=True,
        )
        return False


@click.command("extract-discussion-data")
def extract_discussion_data():
    _log.info(f"extract_discussion_data() {datetime.datetime.now()}")

    result = extract_next_statement()
    if result:
        _log.info("Discussion data extracted, another triggered")
    else:
        _log.info("All discussions extracted.")
