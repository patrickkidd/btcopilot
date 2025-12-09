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
from btcopilot.tests.personal.synthetic import ConversationSimulator, PERSONAS
from btcopilot.personal.chat import ask


_log = logging.getLogger(__name__)


def extract_next_statement():
    _log.info(f"extract_next_statement() called")

    try:
        # Ensure we have a database connection
        try:
            db.session.get_bind()
        except RuntimeError:
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

        _log.info(f"Celery extraction task started - discussion_id: {discussion_id}")
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


def generate_synthetic_discussion(
    persona_name: str, username: str, max_turns: int, skip_extraction: bool
):
    _log.info(
        f"generate_synthetic_discussion() persona={persona_name}, user={username}, "
        f"max_turns={max_turns}, skip_extraction={skip_extraction}"
    )

    try:
        persona = next((p for p in PERSONAS if p.name == persona_name), None)
        if not persona:
            raise ValueError(f"Persona not found: {persona_name}")

        simulator = ConversationSimulator(
            max_turns=max_turns,
            persist=True,
            username=username,
            skip_extraction=skip_extraction,
        )

        result = simulator.run(persona, ask)
        db.session.commit()

        _log.info(
            f"Synthetic discussion {result.discussionId} generated "
            f"({len(result.turns)} turns)"
        )

        return {
            "success": True,
            "discussion_id": result.discussionId,
            "turn_count": len(result.turns),
            "quality_score": result.quality.score if result.quality else None,
            "coverage_rate": result.coverage.rate if result.coverage else None,
        }

    except Exception as e:
        _log.error(f"Error generating synthetic discussion: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
